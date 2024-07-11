import asyncio
import json
import re
import time
from os import walk, remove
from logging import getLogger, config
from typing import List
from soft_config import SoftConfig
from can_communication import CanCommunication
from enum import Enum, Flag, auto
from datetime import datetime
from gpiozero import LED

class PvswMaster:
    """Pvsw Master"""
    class SlaveStatus(Enum):
        """Slaveの状態"""
        STOP = auto()
        NORMAL = auto()
        ALARM = auto()

    class SlaveBase:
        """
        Slaveの情報
        """

        def __init__(self,
                    can_communication,
                    address=0x00,
                    slave_type='',
                    status=None,
                    version=0x00):
            self.can_communication = can_communication
            self.address = address
            self.slave_type = slave_type
            self.status: PvswMaster.SlaveStatus = status
            self.version = version
            #上位層からのcontrolファイルによる変更があるか否か
            #これを見て通信を行うか判断する。
            self.control_flag = False
        def get_system_dict(self):
            """
            スレーブのデータを渡す。
            """
            system_dict = {
                'address': self.address,
                'type': self.slave_type,
                'status': self.status,
                'version': self.version,
            }
            return system_dict

        async def refresh(self):
            """
            スレーブを最新情報に更新する。
            """
            #todo canの通信
            #dummy とりあえずステータスを交互に切り替える。
            #self.status = PvswMaster.SlaveStatus.STOP if self.status == PvswMaster.SlaveStatus.NORMAL else PvswMaster.SlaveStatus.NORMAL
            self.status = 'NORMAL'
            await asyncio.sleep(0.01)
        
        async def control(self):
            """
            スレーブへ通信で送信し、制御を行う
            """
            #Baseは何もしない
            pass

        async def sync(self):
            """
            スレーブの状態を同期させる。
            つまりrefreshとcontrolを同時に行う。
            """
            await self.control()
            await self.refresh()
            
        
    class SlaveRsd(SlaveBase):
        """
        Slaveの情報
        """
        def __init__(self,
                    can_communication,
                    address=0x10,
                    slave_type='rsd',
                    status= None,
                    version=0x00,
                    pv_volt=0.0,
                    pv_current=0.0,
                    pv_sw=0x00):
            super().__init__(can_communication, address, slave_type, status, version)
            self.pv_volt = pv_volt
            self.pv_current = pv_current
            self.pv_sw = pv_sw
            self.pv_sw_set = 0
        
        def get_system_dict(self):
            """
            スレーブのデータを渡す。
            """
            #更新したクラス内の変数をdict型にして返す。
            system_dict = super().get_system_dict()
            system_dict.update({
                'pv_volt': self.pv_volt,
                'pv_current': self.pv_current,
                'pv_sw': self.pv_sw,
            })
            #継承元とは異なり、一塊のDictキーに集約して上位に渡す。
            system_dict = {f'slave_{self.address:04x}': system_dict}
            return system_dict
        
        async def refresh(self):
            await super().refresh()
            #todo canの通信
            #dummy とりあえず電圧、電流値を0.01づつ上昇させる。
            self.pv_volt += 0.01
            self.pv_current += 0.01
            #pv_swの制御値を反映させる。
            self.pv_sw = self.pv_sw_set
            await asyncio.sleep(0.01)
        
        async def control(self):
            if self.control_flag:
                await super().control()
                #todo canの通信
                await asyncio.sleep(0.01)
                self.control_flag = False
        
        async def sync(self):
            await self.control()
            await self.refresh()
        
        def set_control_json(self, json_data):
            """
            上位のjsonデータからスレーブの制御信号を受け取る。
            """
            for key, value in json_data.items():
                if 'pv_sw' in key:
                    self.set_pv_sw(value)
                    #フラグをセットする。
                    self.control_flag = True
        
        def set_pv_sw(self, pvsw_control):
            """
            スレーブのPVSWを制御する。
            """
            self.control_flag = True
            self.pv_sw_set = pvsw_control

    DC24V_EN_GPIO = 12

    def __init__(self):
        """
        Masterを起動。設定ファイル等を読み込む。
        """
        self.logger = getLogger(__name__)
        #can parameter
        self.soft_config = SoftConfig()
        self.address = self.soft_config.j1939_config.master_address
        self.bitrate = self.soft_config.can_config.bitrate
        self.bustype = self.soft_config.can_config.bustype
        self.channel = self.soft_config.can_config.channel
        self.master_interval_time = self.soft_config.pvsw_config.master_interval_time
        self.control_filecheck_interval_time = self.soft_config.pvsw_config.control_filecheck_interval_time
        self.system_data_len = self.soft_config.file_config.system_data_len
        #master内のステータスデータを設定する。
        self.temperature = 25.0
        self.is_ac_in = False
        self.is_24V_en = False
        self.is_wet = False
        self.task_enable = False
        self.slaves = []
        #gpioの設定
        self.dc24V_en = LED(self.DC24V_EN_GPIO)
        self.dc24V_en.off()
        #CAN通信を行う。
        #self.can_communication = CanCommunication(self.soft_config.can_config ,self.soft_config.j1939_config)
        self.can_communication = None
        #試験用:スレーブを追加する。
        self.slaves.append(PvswMaster.SlaveRsd(can_communication=self.can_communication))

    async def start(self, expire_time=0.0):
        """Masterの動作を開始する。"""
        #周期タスクを実行する。(並列実行)
        self.task_enable = True
        task = asyncio.gather(
            self.task_system_data_cyclic(),
            self.task_control_file_check_cyclic()
            )
        if expire_time > 0.0:
            await asyncio.sleep(expire_time)
            self.task_enable = False
        await task
        self.logger.info('task finished')
    
    def stop(self):
        self.task_enable = False
    
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
        if onoff :
            self.dc24V_en.on()
        else:
            self.dc24V_en.off()
        self.is_24V_en = onoff #todo 実際のものに変更する。
            
    def __get_file_name(self):
        """
        周期的に保存するpythonデータの保存先ファイル名を返す。
        """
        #ディレクトリ内のファイルを検索、ソート
        file_names = []
        for _, _, files in walk(self.soft_config.file_config.system_data_path):
            for name in files:
                if self.soft_config.file_config.system_data_name in name:
                    file_names.append(name)
        file_names = sorted(file_names)

        if len(file_names) <= 0:
        #ファイルが存在しない場合、作成する。
            file_name = datetime.now().strftime('%Y%m%d%H%M%S') + '_' + self.soft_config.file_config.system_data_name
            file_names.append(file_name)
        elif len(file_names) > self.soft_config.file_config.system_data_file_num:
        #ファイル数が上限を超えた場合、最も数字の若いファイルを削除。
            remove(self.soft_config.file_config.system_data_path + '/' + file_names.pop(0))
        
        return self.soft_config.file_config.system_data_path + '/' + file_names[-1]

    def __save_system_data(self, master_dict):
        self.logger.info('save data.json')
        try:
            system_file_name = self.__get_file_name()
            #json.loadを行うためには'r+'で開く必要がある。
            with open(system_file_name, 'r+', encoding='utf-8') as file:
                try:
                    #jsonデータをDict型で読み込む。(最後尾にデータを追加するため。)
                    json_data = json.load(file)
                except json.JSONDecodeError:
                    #読み込むjsonデータがおかしいときは、全てクリアする。
                    self.logger.warning('json decode error. File cleared.')
                    json_data = {}
                file.seek(0)
                file.truncate()
                key = ''
                #最後尾を検索する。
                for i in range(self.system_data_len):
                    key = f'master_data_{i:08x}'
                    if key not in json_data:
                        break
                #最後尾の場合は次の更新のため、新しいファイルを生成する。
                if key in f'master_data_{(self.system_data_len - 1):08x}':
                    new_file_name = datetime.now().strftime('%Y%m%d%H%M%S') + '_' + self.soft_config.file_config.system_data_name
                    with open(new_file_name, 'r+', encoding='utf-8') as file:
                        #空のjsonデータを格納
                        json.dump({}, new_file_name, indent=4)
                #一旦ファイル内容を消去し、その後追加したデータを格納する。
                json_data.update({key: master_dict})
                self.logger.info('dict add.')
                json.dump(json_data, file, indent=4)
        except FileNotFoundError:
            #ファイルが見つからない場合は作成する。
            self.logger.info('create system_data.json')
            with open(system_file_name, 'w', encoding='utf-8') as file:
                json_data = {}
                json.dump(json_data, file, indent=4)
        except Exception as e:
            #その他のエラーを記録する。
            self.logger.error('%s', e)
    
    def __set_control(self, json_data):
        self.__set_control_master(json_data['master'])
        self.__set_control_slaves(json_data['slave'])

    def __set_control_master(self, json_data):
        for key, value in json_data.items():
            if '24V_en' in key:
                self.set_24V_en(value)

    def __set_control_slaves(self, json_data):
        for slave_key, slave_value in json_data.items():
            #slave_keyからアドレスデータを読み出す。（正規表現で_(アンダーバ)以降の文字列を抽出）
            key_number = re.search('(?<=_)[0-9a-bA-B]+', slave_key)
            slave_address = int(key_number.group(), 16)
            #指定されたアドレスのslaveに制御データを導入する。
            slave_found_flg = False
            for slave in self.slaves:
                if slave.address == slave_address:
                    slave_found_flg = True
                    slave.set_control_json(slave_value)
                    break
            #もし指定アドレスのslaveが見つからない場合は、ログを残す。
            if slave_found_flg == False:
                self.logger.warning('In control.json, ' + slave_key + ' not found')
    
    async def __apply_control_to_slaves(self):
        """
        __set_control_slavesで反映したcontrolをslaveに通信で反映させる。
        """
        for slave in self.slaves:
            await slave.control()
          
    def __load_control_file(self):
        file_names = []
        #ディレクトリ内のファイルを検索、ソート
        for _, _, files in walk(self.soft_config.file_config.control_path):
            for name in files:
                if self.soft_config.file_config.control_name in name:
                    file_names.append(name)
        file_names = sorted(file_names)

        if len(file_names) > 0:
            try:
                for file_name in file_names:
                    file_name_with_path = self.soft_config.file_config.control_path + '/' + file_name
                    with open(file_name_with_path, 'r', encoding='utf-8') as file:
                        self.logger.info('load ' + file_name)
                        self.__set_control(json.load(file))
                    #読み込んだら該当ファイルを消去する。
                    remove(file_name_with_path)
            except json.JSONDecodeError:
                #読み込むjsonデータがおかしいときは、ログのみ残し無視する。
                self.logger.warning('control.json decode error. File ignored.')
            except KeyError:
                #読み込むjsonデータのキーが見つからない場合は、ログのみ残し無視する。
                self.logger.warning('control.json key error.')
            except Exception as e:
                #その他のエラーを記録する。
                self.logger.error('%s', e)

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
            'time': datetime.now().astimezone().isoformat(),
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
        while self.task_enable:
            slp_interval = asyncio.sleep(self.master_interval_time)
            self.__save_system_data(await self.__get_system_dict())
            self.logger.info('cyclic done.')
            await slp_interval
    
    async def task_control_file_check_cyclic(self):
        """
        control_fileを監視するタスク。
        """
        while self.task_enable:
            slp_interval = asyncio.sleep(self.control_filecheck_interval_time)
            self.__load_control_file()
            await self.__apply_control_to_slaves()
            await slp_interval
