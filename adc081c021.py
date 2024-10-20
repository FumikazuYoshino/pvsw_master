from logging import getLogger
from enum import IntEnum
import smbus
import time


class ADC081C021:
    """
    ADC081C021の制御を行う。
    """
    ADDR = 0x54
    CONV_ADC_TO_VOLT = 3.3 / 2**8
    FILT_PARAM = 0.25

    def __init__(self):
        self.__logger = getLogger(__name__)
        self.__i2c = smbus.SMBus(1)
        self.filtered_data = 0.0
        self.__filt_buf = 0.0

    def set_adc_data(self):
        # adc値をi2cで読み込み、電圧に変換する。
        raw_data = self.__i2c.read_i2c_block_data(self.ADDR, 0, 2)
        data = (raw_data[0] << 4 | raw_data[1] >> 4) * self.CONV_ADC_TO_VOLT
        # 一時遅れフィルタで計算を行う。
        self.__filt_buf += data - self.filtered_data
        self.filtered_data = self.__filt_buf * self.FILT_PARAM
        self.__logger.debug(self.filtered_data)
