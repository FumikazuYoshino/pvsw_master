import os
import time
import asyncio
from logging import getLogger, config
import j1939
from enum import IntEnum
from soft_config import SoftConfig
from gpiozero import LED

class CAListenAddressClaimed(j1939.ControllerApplication):
    """
    ControllerApplicationを継承するクラス。
    address_claimが他機から送信された際、そのアドレスを
    取得するために追加した。
    """
    def __init__(self, name, device_address_preferred=None, bypass_address_claim=False):
        self.__listeners = []
        super().__init__(name, device_address_preferred, bypass_address_claim)

    def add_listener(self, listener):
        """
        address_claimを受信したときに実行する関数。
        """
        self.__listeners.append(listener)

    def _process_addressclaim(self, mid, data, timestamp):
        """
        親関数をオーバーライドする。
        ここでaddress_claimを受信したときの処理を記述する。
        """
        for fn in self.__listeners:
            fn(mid, data, timestamp)
        super()._process_addressclaim(mid, data, timestamp)

class CanCommunication:
    """j1939の通信を行う"""
    # 一番目のSlaveを有効にするためのGPIO
    SLAVE_EN_GPIO = 24

    class PGN(IntEnum):
        """J1939のParameterGroupNumber"""
        Acknowledgement = 0x00E800
        ProprietaryA    = 0x00EF00

    def __init__(self, can_config : SoftConfig.CanConfig, j1939_config : SoftConfig.J1939Config):
        self.logger = getLogger(__name__)
        # gpioの設定
        self.slave_en = LED(self.SLAVE_EN_GPIO)
        self.slave_en.on()
        # CANとJ1939の設定
        os.system('sudo ip link set can0 up type can bitrate ' + f'{can_config.bitrate}' )
        name = j1939.Name(
            arbitrary_address_capable=0,
            industry_group=j1939.Name.IndustryGroup.Industrial, #Industrialに固定
            vehicle_system_instance=1,
            vehicle_system=1,
            function=1,
            function_instance=1,
            ecu_instance=1,
            manufacture_code=j1939_config.manufacture_code,
            identity_number=j1939_config.identity_number,
        )
        self.ca = CAListenAddressClaimed(name, j1939_config.master_address)
        self.ecu = j1939.ElectronicControlUnit(max_cmdt_packets=j1939_config.max_cmdt_packets)
        self.ecu.connect(bustype=can_config.bustype , channel=can_config.channel, bitrate=can_config.bitrate)
        self.ecu.add_ca(controller_application=self.ca)
        self.ca.subscribe(self.__on_ca_receive)
        self.ca.add_listener(self.__listener)
        # self.ca.add_timer(2, self.__ca_timer_callback)
        self.slave_list = []
        self.ca.start()
        self.__fn_received = []
        self.logger.info('can start')
        time.sleep(5)
        # self.slave_en.off()
        # self.ca.send_request(0, self.PGN.ACKNOWLEDGEMENT, 0xFF)
        # self.ca.send_pgn(0, 0xEF, 0x08, 6, list(range(0,64,1)))
    
    def __listener(self, mid, data, timestamp):
        self.logger.info(f'id:{mid.source_address:07x}')
        # 1番目:アドレス、2番目:製品コード(仮に0を格納している。)
        self.slave_list.append([mid.source_address, 0])

    def __ca_timer_callback(self, cookie):
        self.logger.info('callback')
        if self.ca.state != j1939.ControllerApplication.State.NORMAL:
            return True
        for list in self.slave_list:
            data = [0x43, 0x52, 0x01, 0x00]
            self.ca.send_pgn(0, self.PGN.ProprietaryA >> 8, list[0], 6, data)
            self.logger.info('send')
        return True
    
    def __on_ca_receive(self, priority, pgn, sa, timestamp, data):
        """process receive"""
        self.logger.info(f'PGN {pgn:06x} length {len(data)} sa {sa:02x}')
        self.logger.info(''.join([chr(value) for value in data]))
        match pgn:
            case self.PGN.Acknowledgement:
                # register slave address from ack
                if sa not in self.slave_list:
                    self.slave_list.append(sa)
                    self.logger.info('add slave %d', sa)
            case self.PGN.ProprietaryA:
                for fn in self.__fn_received:
                    fn(sa, data)
            case _:
                return

    def set_on_ca_received(self, fn):
        self.__fn_received.append(fn)

    def del_on_ca_received(self, fn):
        self.__fn_received.remove(fn)

    def __del__(self):
        self.ca.stop()
        self.ecu.disconnect()
        self.logger('can end')
