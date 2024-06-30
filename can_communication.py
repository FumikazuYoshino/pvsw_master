import os
from logging import getLogger, config
import can
import sys
import time
import j1939
import json
from gpiozero import LED

class CanCommunication:
    """j1939の通信を行う"""
    #一番目のSlaveを有効にするためのGPIO
    SLAVE_EN_GPIO = 24
    class PGN(object):
        """J1939のParameterGroupNumber"""
        ACKNOWLEDGEMENT = 0x00E800

    def __init__(self):
        self.logger = getLogger(__name__)
        #gpioの設定
        self.slave_en = LED(self.SLAVE_EN_GPIO)
        self.slave_en.on()
        #CANとJ1939の設定
        os.system('ip link set can0 up type can bitrate 1000000')
        name = j1939.Name(
            arbitrary_address_capable=0,
            industry_group=j1939.Name.IndustryGroup.Industrial,
            vehicle_system_instance=1,
            vehicle_system=1,
            function=1,
            function_instance=1,
            ecu_instance=1,
            manufacture_code=666,
            identity_number=1234567
        )
        self.ca = j1939.ControllerApplication(name, 0x01)
        self.ecu = j1939.ElectronicControlUnit(max_cmdt_packets=0x03)
        self.ecu.connect(bustype='socketcan', channel='can0', bitrate=1000000)
        #ecu.send_pgn(data_page=0, pdu_format=0xEA, pdu_specific=0xFF, priority=6, src_address=0xFE, data=[0x00, 0xEE, 0x00])
        self.ecu.add_ca(controller_application=self.ca)
        self.ca.subscribe(self.on_ca_receive)
        self.slave_address_list = []
        #self.ca.add_timer(1, self.ca_timer_callback)
        self.ca.start()
        self.logger.info('can start')
        self.slave_en.off()
        time.sleep(1)
        self.ca.send_request(0, self.PGN.ACKNOWLEDGEMENT, 0xFF)
        time.sleep(1)
        #self.ca.send_message(0x06, 0x00EF00, [x for x in range(0,7,1)])
        self.ca.send_pgn(0, 0xEF, 0x08, 6, list(range(0,64,1)))
    
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
