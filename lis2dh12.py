from logging import getLogger
from enum import IntEnum
import spidev
import time


class LIS2DH12:
    """
    加速度センサLIS2DH12の制御を行う。
    """
    READ        = 0x80
    MS          = 0x40
    TEMP_MIN    = -40.0
    TEMP_MAX    = 85.0
    INT1_GPIO   = 26
    ACCEL_G     = 9.80665

    class REG(IntEnum):
        """
        LIS2DH12のレジスタ
        """
        STATUS_REG_AUX  = 0x07
        OUT_TEMP_L      = 0x0C
        OUT_TEMP_H      = 0x0D
        WHO_AM_I        = 0x0F
        CTRL_REG0       = 0x1E
        TEMP_CFG_REG    = 0x1F
        CTRL_REG1       = 0x20
        CTRL_REG2       = 0x21
        CTRL_REG3       = 0x22
        CTRL_REG4       = 0x23
        CTRL_REG5       = 0x24
        CTRL_REG6       = 0x25
        STATUS_REG      = 0x27
        OUT_X_L         = 0x28
        OUT_X_H         = 0x29
        OUT_Y_L         = 0x2A
        OUT_Y_H         = 0x2B
        OUT_Z_L         = 0x2C
        OUT_Z_H         = 0x2D
        FIFO_CTRL_REG   = 0x2E
        FIFO_SRC_REG    = 0x2F

    def __init__(self):
        self.logger = getLogger(__name__)
        self.spi = spidev.SpiDev()
        self.spi.open(1, 0)
        self.spi.max_speed_hz = 500000
        # boot device
        self.__write(self.REG.CTRL_REG5, [0x80])
        time.sleep(0.05)
        # FIFO enable
        self.__write(self.REG.CTRL_REG5, [0x40])
        # 100Hz, enable XYZ
        self.__write(self.REG.CTRL_REG1, [0x57])
        # HR, +-2g, set BDU for temp
        self.max_g = 2.0
        self.__write(self.REG.CTRL_REG4, [0x08])
        # TEMP enable
        self.__write(self.REG.TEMP_CFG_REG, [0xC0])
        # Bypas mode (to reset fifo)
        self.__write(self.REG.FIFO_CTRL_REG, [0x00])
        # Stream mode
        self.__write(self.REG.FIFO_CTRL_REG, [0x80])

    def __write(self, reg: REG, data: bytearray):
        # 先頭レジスタにアドレスと各種フラグを格納する。
        reg = (reg.value | self.MS)
        reg &= ~self.READ
        data.insert(0, reg)
        self.spi.xfer2(data)

    def __read(self, reg: REG, len: int = 1):
        # 先頭レジスタにアドレスと各種フラグを格納する。
        reg = (reg.value | self.READ | self.MS)
        # ダミーwrite用に0x00を読み出すバイト分用意する。
        data = bytearray(len)
        data.insert(0, reg)
        read = self.spi.xfer2(data)
        # 先頭はダミーなので削除する。
        return read[1:]

    def __conv_accel(self, data):
        """
        重力加速度(m/s^2)へ変換する。
        """
        s_data = (-1) * ((0xFFFF ^ data) + 1) if (data & 0x8000) > 0 else data
        return (float)(s_data / 0x7FFF) * self.max_g * self.ACCEL_G

    def __conv_temp(self, data):
        s_data = (-1) * ((0xFFFF ^ data) + 1) if (data & 0x8000) > 0 else data
        return s_data / 2**8 + 25.0

    def __fifo_len(self):
        """
        FIFOに溜まっているデータ長を返す。
        """
        data = self.__read(self.REG.FIFO_SRC_REG)
        if (data[0] & 0x40) > 0:
            # ovrnのときは32個のデータがfifoに残留している。
            return 32
        return data[0] & 0x1F

    def get_accel(self):
        data = self.__read(self.REG.OUT_X_L, 6)
        x_data = data[0] | (data[1] << 8)
        y_data = data[2] | (data[3] << 8)
        z_data = data[4] | (data[5] << 8)
        x_data = self.__conv_accel(x_data)
        y_data = self.__conv_accel(y_data)
        z_data = self.__conv_accel(z_data)
        return x_data, y_data, z_data

    def get_accel_array(self) -> ([], [], []):
        """
        FIFOに溜まっているデータを配列状にして返す。
        """
        fifo_len = self.__fifo_len()
        # self.logger.info(f'fifo len is {fifo_len:0}')
        x_array, y_array, z_array = [], [], []
        for i in range(fifo_len):
            (x, y, z) = self.get_accel()
            x_array.append(x)
            y_array.append(y)
            z_array.append(z)
        # self.logger.debug(f'X:{x_array[0]:0} Y:{y_array[0]:0} Z:{z_array[0]:0}')
        self.logger.debug(f'fifo_len:{fifo_len:0}')
        return (x_array, y_array, z_array)

    def get_temp(self):
        """
        温度を取得する。ただし、10度ほどずれるので、
        絶対値はあまり当てにならない。
        """
        data = self.__read(self.REG.OUT_TEMP_L, 2)
        temp_data = (data[0] | (data[1] << 8))
        temp_data = self.__conv_temp(temp_data)
        self.logger.debug(''.join(f'0x{i:02X} ' for i in data))
        self.logger.debug(f'TEMP:{temp_data:.2f}')
