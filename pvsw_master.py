import asyncio
import re
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
from os import remove
from logging import getLogger
from typing import List
from file_process import FileProcess
from soft_config import SoftConfig
from seismometer import Seismometer
from pvsw_slave import SlaveRsd
from pathlib import Path
from gpiozero import LED


class PvswMaster:
    """
    Pvsw Masterの本体
    """
    DC24V_EN_GPIO   = 12
    LED2_GPIO       = 1

    def __init__(self):
        """
        Masterを起動。設定ファイル等を読み込む。
        """
        self.logger = getLogger(__name__)
        # accel ic
        self.seismometer = Seismometer(fs=100.0, window_sec=5.12)
        # can parameter
        self.soft_config = SoftConfig()
        self.address = self.soft_config.j1939_config.master_address
        self.bitrate = self.soft_config.can_config.bitrate
        self.bustype = self.soft_config.can_config.bustype
        self.channel = self.soft_config.can_config.channel
        self.master_interval_time = self.soft_config.pvsw_config.master_interval_time
        self.control_filecheck_interval_time = self.soft_config.pvsw_config.control_filecheck_interval_time
        self.accel_sensor_interval_time = self.soft_config.pvsw_config.accel_sensor_interval_time
        self.system_data_len = self.soft_config.file_config.system_data_len
        # file操作を司る.
        self.file_process = FileProcess(self.soft_config.file_config)
        # master内のステータスデータを設定する。
        self.temperature = 25.0
        self.is_ac_in = False
        self.is_24V_en = False
        self.is_wet = False
        self.tasks = []
        self.slaves = []
        self.last_control_updatetime = None 
        # gpioの設定
        self.dc24V_en = LED(self.DC24V_EN_GPIO)
        self.dc24V_en.off()
        self.led2_gpio = LED(self.LED2_GPIO)
        self.led2_gpio.off()
        # CAN通信を行う。
        # self.can_communication = CanCommunication(self.soft_config.can_config ,self.soft_config.j1939_config)
        self.can_communication = None
        # 試験用:スレーブを追加する。
        self.slaves.append(SlaveRsd(can_communication=self.can_communication))

    async def start(self, expire_time=0.0):
        """Masterの動作を開始する。"""
        # 周期タスクを実行する。(並列実行)
        async with asyncio.TaskGroup() as tg:
            self.tasks.append(tg.create_task(self.task_accel_cyclic()))
            self.tasks.append(tg.create_task(self.task_control_file_check_cyclic()))
            self.tasks.append(tg.create_task(self.task_system_data_cyclic()))
            if expire_time > 0.0:
                # 終了時間が設定された場合
                await asyncio.sleep(expire_time)
                for task in self.tasks:
                    task.cancel()
    
    def stop(self):
        for task in self.tasks:
            task.cancel()
    
    def subscribe(self, callback):
        """slaveから情報を得るごとにcallbackで返す。"""
        self.callback.append(callback)
    
    def download_slave_soft(self, address, binary_data):
        """指定したアドレスにバイナリデータのソフトをダウンロードする。"""
        pass

    def set_24V_en(self, onoff):
        """
        24V電源の有効・無効を制御する。
        """
        if onoff:
            self.dc24V_en.on()
        else:
            self.dc24V_en.off()
        self.is_24V_en = onoff  # todo 実際のものに変更する。
    
    async def __set_control(self):
        json_data = await self.file_process.load_control_file()
        if json_data is not None:
            self.__set_control_master(json_data['master'])
            self.__set_control_slaves(json_data['slave'])
            await self.__apply_control_to_slaves()

    def __set_control_master(self, json_data):
        for key, value in json_data.items():
            if '24V_en' in key:
                self.set_24V_en(value)

    def __set_control_slaves(self, json_data):
        for slave_key, slave_value in json_data.items():
            # slave_keyからアドレスデータを読み出す。（正規表現で_(アンダーバ)以降の文字列を抽出）
            key_number = re.search('(?<=_)[0-9a-bA-B]+', slave_key)
            slave_address = int(key_number.group(), 16)
            # 指定されたアドレスのslaveに制御データを導入する。
            slave_found_flg = False
            for slave in self.slaves:
                if slave.address == slave_address:
                    slave_found_flg = True
                    slave.set_control_json(slave_value)
                    break
            # もし指定アドレスのslaveが見つからない場合は、ログを残す。
            if slave_found_flg is False:
                self.logger.warning('In control.json, ' + slave_key + ' is not found')
    
    async def __apply_control_to_slaves(self):
        """
        __set_control_slavesで反映したcontrolをslaveに通信で反映させる。
        """
        for slave in self.slaves:
            await slave.control()

    async def __get_system_dict(self):
        """
        slaveも含め、周期的に保存するデータをdictにして返す。
        """
        for slave in self.slaves:
            await slave.refresh()
        slave_dict = {}
        for slave in self.slaves:
            slave_dict.update(slave.get_system_dict())

        master_dict = {
            'time': datetime.now().astimezone().isoformat(timespec="milliseconds"),
            'address': self.address,
            'temperature': self.temperature,
            'is_ac_in': self.is_ac_in,
            'is_24V_en': self.is_24V_en,
            'is_wet': self.is_wet,
            'slave': slave_dict,
        }
        return master_dict

    async def task_system_data_cyclic(self):
        """
        system_dataの周期的タスクを実行する。
        """
        while True:
            async with asyncio.TaskGroup() as tg:
                tg.create_task(asyncio.sleep(self.master_interval_time))
                tg.create_task(self.file_process.save_system_data(await self.__get_system_dict()))
                tg.create_task(self.file_process.load_config_file())
                self.seismometer.get_scale()

    async def task_control_file_check_cyclic(self):
        """
        control_fileを監視するタスク。同時に通信でslaveと通信する。
        """
        while True:
            async with asyncio.TaskGroup() as tg:
                tg.create_task(asyncio.sleep(self.control_filecheck_interval_time))
                tg.create_task(self.__set_control())
                tg.create_task(self.__apply_control_to_slaves())

    async def task_accel_cyclic(self):
        """
        加速度センサのデータを取得する。
        """
        while True:
            async with asyncio.TaskGroup() as tg:
                tg.create_task(asyncio.sleep(self.accel_sensor_interval_time))
                self.seismometer.set_accel_data_from_lis2dh12()
