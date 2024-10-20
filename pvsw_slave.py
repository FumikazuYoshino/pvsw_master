import asyncio
import struct
from can_communication import CanCommunication
from enum import IntFlag
from pvsw_parameter import PvswParam
from logging import getLogger

class PvswSlave:
    """
    Slaveの情報
    """
    def __init__(self, can_communication, param):
        self.__can_communication = can_communication
        self.__param = param
        self.__j1939_address = 8
        self.__logger = getLogger(__name__)

    async def set_control(self, control):
        """
        スレーブへ通信で送信し、制御を行う
        """
        for con_key, con_value in control.items():
            for para_key, para_value in self.__param['parameters'].items():
                if con_key == para_key:
                    para_value[para_key]['value'] = con_value
                    await self.send(['C', 'W'], para_value[para_key])

    async def get_system_data(self):
        """
        テスト用に簡略化している。todo汎化
        """
        self.__logger.info('can comm start!')
        await self.send(['C', 'R'], self.__param['parameters']['programName'])
        await self.send(['C', 'R'], self.__param['parameters']['volt'])

    async def send(self, pre_command, para_value):
        """
        can通信を実行する。
        """
        data = [ord(char) for char in pre_command]
        data.extend(byte for byte in struct.pack('<H', int(para_value['command'], 16)))
        if pre_command == ['C', 'W']:
            match para_value.type:
                case 'uint':
                    byte_string = struct.pack('<I', para_value['value'])
                case 'int':
                    byte_string = struct.pack('<i', para_value['value'])
                case 'float':
                    byte_string = struct.pack('<f', para_value['value'])
                case _:
                    return
            data.extend(byte for byte in byte_string)
        self.__logger.info(f'data {data}')
        self.__can_communication.ca.send_pgn(0, CanCommunication.PGN.ProprietaryA >> 8, self.__j1939_address, 6, data)
        (sa, data) = await self.recv()
        # フォーマットを整える。
        match para_value['type']['type']:
            case 'uint':
                value = struct.unpack('<I', bytes(data))[0]
            case 'int':
                value = struct.unpack('<i', bytes(data))[0]
            case 'float':
                value = struct.unpack('<f', bytes(data))[0]
            case 'str' | 'string':
                value = bytes(data).decode('ascii')
            case _:
                return
        para_value['type']['value'] = value

    async def recv(self):
        """
        can通信の受信を行う。
        受信が完了するまでawaitで待機する。
        """
        future = asyncio.get_event_loop().create_future()

        def on_recv(sa, data):
            future.set_result((sa, data))

        self.__can_communication.set_on_ca_received(on_recv)

        result = await future
        self.__can_communication.del_on_ca_received(on_recv)
        return result

