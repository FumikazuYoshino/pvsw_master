import asyncio
from enum import IntFlag

class SlaveBase:
    """
    Slaveの情報
    """

    class SlaveStatus(IntFlag):
        """Slaveの状態"""
        STOP    = 0
        NORMAL  = 1
        ALARM   = 2

    def __init__(self, can_communication, address=0x00, slave_type='',
                 status=None, version=0x00):
        self.can_communication = can_communication
        self.address = address
        self.slave_type = slave_type
        self.status: SlaveBase.SlaveStatus = status
        self.version = version
        # 上位層からのcontrolファイルによる変更があるか否か
        # これを見て通信を行うか判断する。
        self.control_flag = False

    def get_system_dict(self):
        """
        スレーブのデータを渡す。
        """
        system_dict = {
            'address': self.address,
            'type': self.slave_type,
            'status': int(self.status),
            'version': self.version,
        }
        return system_dict

    async def refresh(self):
        """
        スレーブを最新情報に更新する。
        """
        # todo canの通信
        # dummy とりあえずステータスを交互に切り替える。
        self.status = SlaveBase.SlaveStatus.STOP \
            if self.status == SlaveBase.SlaveStatus.NORMAL \
            else SlaveBase.SlaveStatus.NORMAL
        await asyncio.sleep(0.01)

    async def control(self):
        """
        スレーブへ通信で送信し、制御を行う
        """
        # Baseは何もしない
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
    def __init__(self, can_communication, address=0x10, slave_type='rsd',
                 status=None, version=0x00, pv_volt=0.0, pv_current=0.0,
                 pv_sw=0x00):
        super().__init__(can_communication, address, slave_type, status,
                         version)
        self.pv_volt = pv_volt
        self.pv_current = pv_current
        self.pv_sw = pv_sw
        self.pv_sw_set = 0
    
    def get_system_dict(self):
        """
        スレーブのデータを渡す。
        """
        # 更新したクラス内の変数をdict型にして返す。
        system_dict = super().get_system_dict()
        system_dict.update({
            'pv_volt': self.pv_volt,
            'pv_current': self.pv_current,
            'pv_sw': self.pv_sw,
        })
        # 継承元とは異なり、一塊のDictキーに集約して上位に渡す。
        system_dict = {f'slave_{self.address:04x}': system_dict}
        return system_dict
    
    async def refresh(self):
        await super().refresh()
        # todo canの通信
        # dummy とりあえず電圧、電流値を0.01づつ上昇させる。
        self.pv_volt += 0.01
        self.pv_current += 0.01
        #pv_swの制御値を反映させる。
        self.pv_sw = self.pv_sw_set
        await asyncio.sleep(0.01)
    
    async def control(self):
        if self.control_flag:
            await super().control()
            # todo canの通信
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
                # フラグをセットする。
                self.control_flag = True
    
    def set_pv_sw(self, pvsw_control):
        """
        スレーブのPVSWを制御する。
        """
        self.control_flag = True
        self.pv_sw_set = pvsw_control
