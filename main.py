import asyncio
import time
import sys
import json
from logging import getLogger, config
from pvsw_master import PvswMaster
from lis2dh12 import LIS2DH12
from seismometer import Seismometer
import pandas as pd


def set_logger(name=None):
    """set logger from external config file."""
    with open('./log_config.json', 'r', encoding='utf-8') as f:
        log_conf = json.load(f)

    config.dictConfig(log_conf)


if __name__ == "__main__":
    # コンソールの標準入力より、停止時間を定めることが出来る。
    args = sys.argv
    set_logger()
    pvsw = PvswMaster()
    # #標準入力にデータが入っている場合のみ入力する。
    delay = float(args[1]) if len(args) == 2 else 0.0
    asyncio.run(pvsw.start(delay))

    # seismometer = Seismometer(fs = 10.0)

    # df = pd.read_csv('./TestData/AA06EA01.csv', skiprows=6,
    #                  skipinitialspace=True)
    # scale_list = []
    # iter = 0
    # start = end = 0.0
    # loop = asyncio.get_event_loop()
    # for x, y, z in zip(df['NS'], df['EW'], df['UD']):
    #     if iter % 5 == 0:
    #         seismometer.set_accel_data(x, y, z)
    #     if iter % 500 == 0:
    #         start = time.time()
    #         is_full, scale = asyncio.run(seismometer.get_scale())
    #         scale_list.append(scale)
    #         end = time.time()
    #         print(f'time: {end - start:0} bool: {is_full:0}')
    #     iter += 1
    # print(max(scale_list))

    # acc_ic = LIS2DH12()
    # while(True):
    #     acc_ic.get_accel()
    #     acc_ic.get_temp()
    #     time.sleep(0.25)
