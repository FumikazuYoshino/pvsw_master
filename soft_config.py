from logging import getLogger, config
import json

class SoftConfig(object):
    """
    ソフト全体で共有する各種パラメータを格納
    上位層との受け口であるファイルの読込・書込も制御
    """
    class FileConfig:
        """
        各種Fileのパラメータ
        """
        def __init__(self,
                    config_path='./Config',
                    control_path='./Control',
                    data_path='./Data',
                    config_name='config.json',
                    control_name='control.json',
                    system_data_name='data.json',
                    system_data_len=1024,
                    system_data_file_num=10):
            self.config_path = config_path
            self.control_path = control_path
            self.system_data_path = data_path,
            self.config_name = config_name
            self.control_name = control_name
            self.system_data_name = system_data_name,
            self.system_data_len = system_data_len
            self.system_data_file_num = system_data_file_num
        
        def get_from_file(self, json_data):
            """
            上位のJSONファイルから設定を読み込む
            """
            self.config_path = json_data['config_path']
            self.control_path = json_data['control_path']
            self.system_data_path = json_data['data_path']
            self.config_name = json_data['config_name']
            self.control_name = json_data['control_name']
            self.system_data_name = json_data['system_data_name']
            self.system_data_len = json_data['system_data_len']
            self.system_data_file_num = json_data['system_data_file_num']
            

    class CanConfig:
        """
        CAN通信関連パラメータの格納
        """
        def __init__(self, bitrate=125000, bustype='socketcan', channel='can0'):
            self.bitrate = bitrate
            self.bustype = bustype
            self.channel = channel
            
        def get_from_file(self, json_data):
            """
            JSONデータから設定を格納する。
            """
            self.bitrate = json_data['bitrate']
            self.bustype = json_data['bustype']
            self.channel = json_data['channel']

    class J1939Config:
        """
        J1939設定
        """
        def __init__(self, master_address=0x01, industry_group='Industrial', manufacture_code=0x100, identity_number=0x10):
            self.master_address = master_address
            self.industry_group = industry_group
            self.manufacture_code = manufacture_code
            self.identity_number = identity_number
        
        def get_from_file(self, json_data):
            """
            JSONデータから設定を格納する。
            """
            self.master_address = int(json_data['master_address'], 0)
            self.industry_group = json_data['industry_group']
            self.manufacture_code = int(json_data['manufacture_code'], 0)
            self.identity_number = int(json_data['identity_number'], 0)


    class PvswConfig:
        """
        Pvswの設定
        """
        def __init__(self):
            self.master_interval_time = 5
            self.control_filecheck_interval_time = 0.25
        
        def get_from_file(self, json_data):
            """
            JSONデータから設定を格納する。
            """
            self.master_interval_time = json_data['master_interval_time']
            self.control_filecheck_interval_time = json_data['control_filecheck_interval_time']


    #Configファイルの読込
    CONFIG_JSON_PATH = './Config/config.json'

    def __new__(cls):
        if not hasattr(cls, '_instance'):
            cls._instance = super().__new__(cls)
            return cls._instance
        
    def __init__(self):
        self.logger = getLogger(__name__)
        self.file_config = SoftConfig.FileConfig()
        self.can_config = SoftConfig.CanConfig()
        self.j1939_config = SoftConfig.J1939Config()
        self.pvsw_config = SoftConfig.PvswConfig()
        self.read_file(self.CONFIG_JSON_PATH)
    
    def __read_config(self, json_data):
        """
        設定ファイルのデータを格納する。
        """
        self.logger.info('read config file.')
        try:
            self.file_config.get_from_file(json_data['file_config'])
            self.can_config.get_from_file(json_data['can_config'])
            self.j1939_config.get_from_file(json_data['j1939_config'])
            self.pvsw_config.get_from_file(json_data['pvsw_config'])
        except Exception as e:
            self.logger.error('error on '+ e)

    
    def read_file(self, config_path=CONFIG_JSON_PATH):
        """
        設定ファイルを読み込む。
        """
        with open(config_path, 'r', encoding='utf-8') as file:
            json_load = json.load(file)
        self.__read_config(json_load)
