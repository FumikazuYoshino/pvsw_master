import asyncio
import sys
import json
from logging import getLogger, config
from pvsw_master import PvswMaster

def set_logger(name=None):
    """set logger from external config file."""
    with open('./log_config.json', 'r', encoding='utf-8') as f:
        log_conf = json.load(f)

    config.dictConfig(log_conf)
    getLogger('j1939')

if __name__ == "__main__":
    #コンソールの標準入力より、停止時間を定めることが出来る。
    args = sys.argv
    set_logger()
    pvsw = PvswMaster()
    asyncio.run(pvsw.start(float(args[1])))
    #can_device = CanDevice()
    #time.sleep(10)
    #del can_device
