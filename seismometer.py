from logging import getLogger
from lis2dh12 import LIS2DH12
import numpy as np


class Seismometer:
    """
    加速度センサより震度を計算するアルゴリズム
    気象庁の公開しているアルゴリズムを参考
    https://www.data.jma.go.jp/eqev/data/kyoshin/kaisetsu/calc_sindo.html
    """
    SCALE_MIN = 2.5  # 実用的なscaleの値の最小値。これ以下はノイズで埋もれる。

    def __init__(self, fs, window_sec):
        """
        :param fs: サンプリング周波数(Hz)
        :window_sec: 震度を判定するとき、使用するデータ長(sec)
        """
        self.logger = getLogger(__name__)
        self.lis2dh12 = LIS2DH12()
        self.x_axis = []
        self.y_axis = []
        self.z_axis = []
        self.scale = 0.0
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

    def set_accel_data_from_lis2dh12(self):
        """
        IC(LIS2DH12)より加速度データを取得する。
        """
        (x, y, z) = self.lis2dh12.get_accel_array()
        if len(x) <= 0:
            return
        # 取得と同時に加速度の単位変換(m/s^2->gal)を行う。
        self.x_axis.extend(map(lambda i: i * 100.0, x))
        self.y_axis.extend(map(lambda i: i * 100.0, y))
        self.z_axis.extend(map(lambda i: i * 100.0, z))
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
        self.logger.info(f'scale: {self.scale:0}')
        return (self.axis_data_len <= len(self.x_axis), self.scale)

    def __filter(self, in_data, fs):
        """
        気象庁の公開アルゴリズムに則り計算する。
        """
        # fft
        ns = len(in_data)
        self.logger.debug(f'NS:{ns:0}')
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
