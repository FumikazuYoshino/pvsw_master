import os
from logging import getLogger, config
import can
import sys
import time
import j1939
from soft_config import SoftConfig
from gpiozero import LED

class CanCommunication:
    """j1939の通信を行う"""
    #一番目のSlaveを有効にするためのGPIO
    SLAVE_EN_GPIO = 24
    class PGN(object):
        """J1939のParameterGroupNumber"""
        ACKNOWLEDGEMENT = 0x00E800

    def __init__(self, can_config : SoftConfig.CanConfig, j1939_config : SoftConfig.J1939Config):
        self.logger = getLogger(__name__)
        #gpioの設定
        self.slave_en = LED(self.SLAVE_EN_GPIO)
        self.slave_en.on()
        #CANとJ1939の設定
        os.system('ip link set can0 up type can bitrate ' + f'{can_config.bitrate}' )
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
        self.ca = j1939.ControllerApplication(name, j1939_config.master_address)
        self.ecu = j1939.ElectronicControlUnit(max_cmdt_packets=j1939_config.max_cmdt_packets)
        self.ecu.connect(bustype=can_config.bustype , channel=can_config.channel, bitrate=can_config.bitrate)
        self.ecu.add_ca(controller_application=self.ca)
        self.ca.subscribe(self.on_ca_receive)
        self.slave_address_list = []
        #self.ca.start()
        self.logger.info('can start')
        #self.slave_en.off()
        #self.ca.send_request(0, self.PGN.ACKNOWLEDGEMENT, 0xFF)
        #self.ca.send_pgn(0, 0xEF, 0x08, 6, list(range(0,64,1)))

    def ca_timer_callback(self, cookie):
        if self.ca.state != j1939.ControllerApplication.State.NORMAL:
            return True
        data = [j1939.ControllerApplication.FieldValue.NOT_AVAILABLE_8] * 8
        self.ca.send_pgn(0, 0xEF, 0x08, 6, data)
        self.logger.info('send')
        return True
    
    def on_ca_receive(self, priority, pgn, sa, timestamp, data):
        """process receive"""
        self.logger.info('PGN %d length %d sa %d', pgn, len(data), sa)
        if pgn == self.PGN.ACKNOWLEDGEMENT:
            #register slave address from ack
            if sa not in self.slave_address_list:
                self.slave_address_list.append(sa)
                self.logger.info('add slave %d', sa)
        elif pgn == 0x00EF00:
            print(data)

    def __del__(self):
        self.ca.stop()
        self.ecu.disconnect()
        self.logger('can end')
