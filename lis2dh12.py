from logging import getLogger, config
from enum import Enum, Flag, auto
import spidev

class LIS2DH12:
    """
    加速度センサLIS2DH12の制御を行う。
    """
    
    class REG(Enum):
        """
        LIS2DH12のレジスタ
        """
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


    def __init__(self):
        self.logger = getLogger(__name__)
        self.spi = spidev.SpiDev()
        self.spi.open(1,0)
        self.spi.max_speed_hz = 500000

    def test_read(self):
        adr = (0xC0 | 0x0F)
        read = self.spi.xfer2([adr, 0x00])
        print(read)

    def __write(self, , write_data):

