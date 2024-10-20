import asyncio
import re
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
from enum import IntEnum
from os import remove
from logging import getLogger
from typing import List
from adc081c021 import ADC081C021
from can_communication import CanCommunication
from file_process import FileProcess
from soft_config import SoftConfig
from seismometer import Seismometer
from pvsw_slave import PvswSlave
from pvsw_parameter import PvswParam
from pathlib import Path
from gpiozero import LED, Button


class PvswMaster:
    """
    Pvsw Masterの本体
    """
    DC24V_EN_GPIO   = 12
    DC24V_IN_GPIO   = 13
    J5_GPIO         = 23
    AC_IN_GPIO      = 6
    LED2_GPIO       = 1

    class Status(IntEnum):
        Normal      = 0
        AlmWater    = -1
        AlmSeismic  = -2

    def __init__(self):
        """
        Masterを起動。設定ファイル等を読み込む。
        """
        self.logger = getLogger(__name__)
        # accel ic
        self.__seismometer = Seismometer(fs=100.0, window_sec=5.12)
        # water adc
        self.__wet_sensor = ADC081C021()
        # can parameter
        self.__soft_config = SoftConfig()
        self.__address = self.__soft_config.j1939_config.master_address
        self.__bitrate = self.__soft_config.can_config.bitrate
        self.__bustype = self.__soft_config.can_config.bustype
        self.__channel = self.__soft_config.can_config.channel
        self.__master_interval_time = self.__soft_config.pvsw_config.master_interval_time
        self.__control_filecheck_interval_time = self.__soft_config.pvsw_config.control_filecheck_interval_time
        self.__accel_sensor_interval_time = self.__soft_config.pvsw_config.accel_sensor_interval_time
        self.__system_data_len = self.__soft_config.file_config.system_data_len
        # file操作を司る.
        self.__file_process = FileProcess(self.__soft_config.file_config)
        # parameter類を読み込む
        self.pvsw_param = PvswParam(self.__soft_config.file_config)
        # master内のステータスデータを設定する。
        self.pvsw_param.param['parameters']['mainParameter']['parameters']['temperature']['type']['value'] = 31.5
        self.pvsw_param.param['parameters']['mainParameter']['parameters']['ac_in']['type']['value'] = 1
        self.pvsw_param.param['parameters']['mainParameter']['parameters']['en_24V']['type']['value'] = 0
        self.pvsw_param.param['parameters']['mainParameter']['parameters']['wet']['type']['value'] = 0
        self.__tasks = []
        self.__slaves = []
        # gpioの設定
        self.__dc24V_en = LED(self.DC24V_EN_GPIO)
        self.__dc24V_en.off()
        self.__dc24V_in = Button(self.DC24V_IN_GPIO)
        self.__ac_in = Button(self.AC_IN_GPIO)
        self.__reset_button = Button(self.J5_GPIO)
        self.__led2_gpio = LED(self.LED2_GPIO)
        self.__led2_gpio.off()
        # CAN通信を行う。
        # self.__can_communication = CanCommunication(self.__soft_config.can_config, self.__soft_config.j1939_config)
        self.__can_communication = None 
        # 試験用:スレーブを追加する。
        # self.__slaves.append(PvswSlave(self.__can_communication, self.pvsw_param.param['parameters']['slave_0001']))

    async def start(self, expire_time=0.0):
        """Masterの動作を開始する。"""
        # 周期タスクを実行する。(並列実行)
        # slaveの設定を行う。 todo slaveの数、種類により変更する。
        async with asyncio.TaskGroup() as tg:
            self.__tasks.append(tg.create_task(self.task_sensor_cyclic()))
            self.__tasks.append(tg.create_task(self.task_control_file_check_cyclic()))
            self.__tasks.append(tg.create_task(self.task_system_data_cyclic()))
            if expire_time > 0.0:
                # 終了時間が設定された場合
                await asyncio.sleep(expire_time)
                for task in self.__tasks:
                    task.cancel()
    
    def stop(self):
        for task in self.__tasks:
            task.cancel()
    
    def subscribe(self, callback):
        """slaveから情報を得るごとにcallbackで返す。"""
        self.callback.append(callback)
    
    def download_slave_soft(self, address, binary_data):
        """指定したアドレスにバイナリデータのソフトをダウンロードする。"""
        pass

    async def __set_control(self):
        """
        controlで指定された司令を反映させる。
        """
        json_data = await self.__file_process.load_control_file()
        # None(更新されていない、存在しない)の場合は何もしない。
        if json_data is None:
            return
        # paramを更新する。
        self.pvsw_param.set_param_write_value(json_data)

    def __set_control_slaves(self, json_data):
        for slave_key, slave_value in json_data.items():
            # slave_keyからアドレスデータを読み出す。（正規表現で_(アンダーバ)以降の文字列を抽出）
            key_number = re.search('(?<=_)[0-9a-bA-B]+', slave_key)
            slave_address = int(key_number.group(), 16)
            # 指定されたアドレスのslaveに制御データを導入する。
            slave_found_flg = False
            # for slave in self.__slaves:
            #     if slave.address == slave_address:
            #         slave_found_flg = True
            #         slave.set_control(slave_value)
            #         break
            # もし指定アドレスのslaveが見つからない場合は、ログを残す。
            if slave_found_flg is False:
                self.logger.warning('In control.json, ' + slave_key + ' is not found')

    def __get_parameter(self, master_param):
        """
        masterの各種状態を取得する。
        """
        master_param['parameters']['in_24V']['type']['value'] = 1 if self.__dc24V_in.is_pressed else 0
        master_param['parameters']['ac_in']['type']['value'] = 0 if self.__ac_in.is_pressed else 1  # 負論理
        master_param['parameters']['seismometer']['type']['value'] = self.__seismometer.scale
        master_param['parameters']['wet']['type']['value'] = self.__wet_sensor.filtered_data

    async def __get_system_dict(self):
        """
        slaveも含め、周期的に保存するデータをdictにして返す。
        """
        self.__get_parameter(self.pvsw_param.param['parameters']['mainParameter'])
        for slave in self.__slaves:
            await slave.get_system_data()
        # timeを更新
        self.pvsw_param.param['parameters']['mainParameter']['parameters']['time']['type']['value'] = (datetime.now().astimezone().isoformat(timespec="milliseconds"))
        return self.pvsw_param.get_system_data_dict()

    async def __master_cyclic(self):
        """
        master内の周期処理
        """
        params = self.pvsw_param.param['parameters']['mainParameter']['parameters']
        
        # reset button
        if self.__reset_button.is_pressed is False:
            params['reset']['type']['value'] = 1 

        # reset alarm
        if params['reset']['type']['value'] != 0:
            params['status']['type']['value'] = self.Status.Normal
            # reset書き込み時は0に戻す。
            params['reset']['type']['value'] = 0

        # seismometer
        (is_full, scale) = await self.__seismometer.get_scale()
        if is_full and (params['seismic_threshold']['type']['value'] < scale) and (self.__seismometer.SCALE_MIN) < scale:
            params['status']['type']['value'] = self.Status.AlmSeismic

        # wet sensor
        if params['wet_threshold']['type']['value'] < self.__wet_sensor.filtered_data:
            params['status']['type']['value'] = self.Status.AlmWater

        if self.Status(params['status']['type']['value']) is not self.Status.Normal:
            """Almの場合は、強制的にOFFにする。"""
            self.__dc24V_en.off()
            return
        
        if params['en_24V']['type']['value'] > 0:
            self.__dc24V_en.on()
        else:
            self.__dc24V_en.off()

    async def task_system_data_cyclic(self):
        """
        system_dataの周期的タスクを実行する。
        """
        while True:
            async with asyncio.TaskGroup() as tg:
                tg.create_task(asyncio.sleep(self.__master_interval_time))
                tg.create_task(self.__file_process.save_system_data(await self.__get_system_dict()))
                tg.create_task(self.__file_process.load_config_file())

    async def task_control_file_check_cyclic(self):
        """
        以下のタスクを行う。
        control_fileの監視
        slaveとの通信
        masterの処理
        """
        while True:
            async with asyncio.TaskGroup() as tg:
                tg.create_task(asyncio.sleep(self.__control_filecheck_interval_time))
                tg.create_task(self.__set_control())
                tg.create_task(self.__master_cyclic())

    async def task_sensor_cyclic(self):
        """
        加速度センサのデータを取得する。
        水センサのデータを取得する。
        """
        while True:
            async with asyncio.TaskGroup() as tg:
                tg.create_task(asyncio.sleep(self.__accel_sensor_interval_time))
                self.__seismometer.set_accel_data_from_lis2dh12()
                self.__wet_sensor.set_adc_data()
