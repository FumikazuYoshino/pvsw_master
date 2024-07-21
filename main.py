import asyncio
import sys
import json
from logging import getLogger, config
from pvsw_master import PvswMaster
from lis2dh12 import LIS2DH12

def set_logger(name=None):
    """set logger from external config file."""
    with open('./log_config.json', 'r', encoding='utf-8') as f:
        log_conf = json.load(f)

    config.dictConfig(log_conf)
    getLogger('j1939')

if __name__ == "__main__":
    ##コンソールの標準入力より、停止時間を定めることが出来る。
    #args = sys.argv
    #set_logger()
    #pvsw = PvswMaster()
    ##標準入力にデータが入っている場合のみ入力する。
    #time = float(args[1]) if len(args) == 2 else 0.0
    #asyncio.run(pvsw.start(time))
      
    acc_ic = LIS2DH12()
    acc_ic.test_read()
