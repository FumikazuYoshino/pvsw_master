from logging import getLogger
from gpiozero import LED
from soft_config import SoftConfig

class CanDevice:
    """
    j1939によるcanのスレーブと交信する。
    """
    SLAVE_EN_GPIO = 24
    def __init__(self, SoftConfig.CanConfig can_config, SoftConfig.J1939Config j1939_config):
        self.logger = getLogger(__name__)
        self.slave_en = LED(self.SLAVE_EN_GPIO)
        self.slave_en.on()
        #
