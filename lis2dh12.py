from logging import getLogger
from enum import Enum
import spidev
import numpy as np


class Seismometer:

    def __init__(self, fs=100.0, window_sec=10):
        """
        加速度センサより震度を計算するアルゴリズム
        気象庁の公開しているアルゴリズムを参考
        https://www.data.jma.go.jp/eqev/data/kyoshin/kaisetsu/calc_sindo.html
        :param fs: サンプリング周波数(Hz)
        :window_sec: 震度を判定するとき、使用するデータ長(sec)
        """
        self.logger = getLogger(__name__)
        self.x_axis = []
        self.y_axis = []
        self.z_axis = []
        self.fs = fs
        self.axis_data_len = int(fs * window_sec)  # 判定に使用するデータを設定

    def set_accel_data(self, x, y, z):
        """
        加速度センサの値を設定する。
        :param x y z: 加速度(gal)
        """
        self.x_axis.append(x)
        self.y_axis.append(y)
        self.z_axis.append(z)
        diff_len = len(self.x_axis) - self.axis_data_len
        if diff_len >= 0:
            # 古いデータを削除する。
            self.x_axis = self.x_axis[diff_len:]
            self.y_axis = self.y_axis[diff_len:]
            self.z_axis = self.z_axis[diff_len:]

    async def get_scale(self) -> (bool, float):
        """
        計測震度の計算
        計測震度は三軸のデータにフィルタを掛けて合成したうえで、
        計算データの中で0.3sec続いた加速度を取得する。
        計算が若干重い(defaultで150ms)ので、非同期処理推奨
        :return: (bool float)
            bool: データがaxis_data_len分あるか
            float: 計測震度
        """
        if len(self.x_axis) == 0:
            return (False, 0.0)
        mix = self.__mix_filtered_3axis()
        p = int(0.3 * self.fs - 1)  # データを降順にソートした中での0.3秒のポイント
        sorted_data = sorted(mix, reverse=True)
        if p < len(self.x_axis):
            self.scale = 2.0 * np.log10(sorted_data[p]) + 0.94
        else:
            self.scale = 0.0
        self.logger.info(f"scale {self.scale:0}")
        return (self.axis_data_len <= len(self.x_axis), self.scale)

    def __filter(self, in_data, fs):
        """
        気象庁の公開アルゴリズムに則り計算する。
        """
        # fft
        ns = len(in_data)
        fft_data = np.fft.fft(in_data)
        freq = np.fft.fftfreq(ns, 1/fs)
        # filter
        filtered_fft_data = []
        for i in range(ns):
            # 負の周波数に対しても計算するため、絶対値を取り計算。
            f = abs(freq[i])
            # lcf
            calc = ((1.0 - np.exp(-(f/0.5)**3))**0.5) * fft_data[i]
            # hcf
            y = f * 0.1
            calc *= (1.0 + 0.694*y**2 + 0.241*y**4 + 0.0557*y**6 +
                     0.009664*y**8 + 0.00134*y**10 + 0.000155*y**12)**-0.5
            # all
            if f < 0.0001:
                calc = 0.0
            else:
                calc *= (1.0 / f)**0.5
            filtered_fft_data.append(calc)
        # invert fft
        return np.fft.ifft(filtered_fft_data).real

    def __mix_filtered_3axis(self):
        x_tmp = self.__filter(self.x_axis, self.fs)
        y_tmp = self.__filter(self.y_axis, self.fs)
        z_tmp = self.__filter(self.z_axis, self.fs)
        mix = [(x**2 + y**2 + z**2)**0.5
               for x, y, z in zip(x_tmp, y_tmp, z_tmp)]
        return mix


class LIS2DH12:
    """
    加速度センサLIS2DH12の制御を行う。
    """
    READ    = 0x80
    MS      = 0x40
    TEMP_MIN= -40.0
    TEMP_MAX= 85.0

    class REG(Enum):
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

    def __init__(self):
        self.logger = getLogger(__name__)
        self.spi = spidev.SpiDev()
        self.spi.open(1, 0)
        self.spi.max_speed_hz = 500000
        # 400Hz, enable XYZ
        self.__write(self.REG.CTRL_REG1, [0x77])
        # HR, +-2g, set BDU for temp
        self.max_g = 2.0
        self.__write(self.REG.CTRL_REG4, [0x88])
        # TEMP enable
        self.__write(self.REG.TEMP_CFG_REG, [0xC0])

    def test_read(self):
        self.__read(self.REG.CTRL_REG1, 4)

    def __write(self, reg: REG, data: bytearray):
        # 先頭レジスタにアドレスと各種フラグを格納する。
        reg = (reg.value | self.MS)
        reg &= ~self.READ
        data.insert(0, reg)
        self.spi.xfer2(data)

    def __read(self, reg: REG, len: int):
        # 先頭レジスタにアドレスと各種フラグを格納する。
        reg = (reg.value | self.READ | self.MS)
        # ダミーwrite用に0x00を読み出すバイト分用意する。
        data = bytearray(len)
        data.insert(0, reg)
        read = self.spi.xfer2(data)
        # 先頭はダミーなので削除する。
        return read[1:]

    def __conv_accel(self, data):
        s_data = (-1) * ((0xFFFF ^ data) + 1) if (data & 0x8000) > 0 else data
        return (float)(s_data / 0x7FFF) * self.max_g

    def __conv_temp(self, data):
        s_data = (-1) * ((0xFFFF ^ data) + 1) if (data & 0x8000) > 0 else data
        return s_data / 2**8 + 25.0

    def get_accel(self):
        data = self.__read(self.REG.OUT_X_L, 6)
        x_data = data[0] | (data[1] << 8)
        y_data = data[2] | (data[3] << 8)
        z_data = data[4] | (data[5] << 8)
        x_data = self.__conv_accel(x_data)
        y_data = self.__conv_accel(y_data)
        z_data = self.__conv_accel(z_data)
        self.logger.info(f'X:{x_data:.3f} Y:{y_data:.3f} Z:{z_data:.3f}')

    def get_temp(self):
        """
        温度を取得する。ただし、10度ほどずれるので、
        絶対値はあまり当てにならない。
        """
        data = self.__read(self.REG.OUT_TEMP_L, 2)
        temp_data = (data[0] | (data[1] << 8))
        temp_data = self.__conv_temp(temp_data)
        # self.logger.info(''.join(f'0x{i:02X} ' for i in data))
        self.logger.info(f'TEMP:{temp_data:.2f}')
