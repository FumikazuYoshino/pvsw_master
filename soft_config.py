from logging import getLogger
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
        def __init__(self, config_path='./Config', control_path='./Control',
                     data_path='./Data', config_name='config.json',
                     control_name='control.json', system_data_name='data.json',
                     parameter_list_master_name="parameterListMaster.json",
                     parameter_list_slave_name='parameterListSlave',
                     system_data_len=1024, system_data_file_num=10):
            self.config_path = config_path
            self.control_path = control_path
            self.system_data_path = data_path
            self.config_name = config_name
            self.control_name = control_name
            self.system_data_name = system_data_name
            self.system_data_len = system_data_len
            self.system_data_file_num = system_data_file_num
            self.parameter_list_master_name = parameter_list_master_name
            # slaveの種類は複数に渡るため、共通するbasenameを指定する。
            self.parameter_list_slave_name = parameter_list_slave_name

        def get_from_file(self, json_data):
            """
            上位のJSONファイルから設定を読み込む
            """
            self.control_path = json_data['control_path']
            self.system_data_path = json_data['data_path']
            self.script_path = json_data['script_path']
            self.control_name = json_data['control_name']
            self.system_data_name = json_data['system_data_name']
            self.system_data_len = json_data['system_data_len']
            self.system_data_file_num = json_data['system_data_file_num']
            self.script_name = json_data['script_name']
            self.parameter_list_master_name = json_data['parameter_list_master_name']
            self.parameter_list_slave_name = json_data['parameter_list_slave_name']

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
        def __init__(self, master_address=0x01, industry_group='Industrial', manufacture_code=0x100, identity_number=0x10, max_cmdt_packets=10):
            self.master_address = master_address
            self.industry_group = industry_group
            self.manufacture_code = manufacture_code
            self.identity_number = identity_number
            self.max_cmdt_packets = max_cmdt_packets
        
        def get_from_file(self, json_data):
            """
            JSONデータから設定を格納する。
            """
            self.master_address = json_data['master_address']
            self.industry_group = json_data['industry_group']
            self.manufacture_code = json_data['manufacture_code']
            self.identity_number = json_data['identity_number']
            self.max_cmdt_packets = json_data['max_cmdt_packets']

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
            # Slaveからのデータを読み込む周期
            self.master_interval_time = json_data['master_interval_time']
            # controlファイルの更新チェック周期
            self.control_filecheck_interval_time = json_data['control_filecheck_interval_time']
            # accelセンサのデータ取得周期
            self.accel_sensor_interval_time = json_data['accel_sensor_interval_time']

    # Configファイルの読込
    CONFIG_PATH = '/home/pi/App/Config/'
    CONFIG_NAME = 'config.json'
    # Configファイル読み込み失敗対策としてdefault_config.jsonを設ける。
    DEF_CONFIG_NAME = 'default_config.json'

    def __new__(cls):
        if not hasattr(cls, '_instance'):
            cls._instance = super().__new__(cls)
            return cls._instance
        
    def __init__(self):
        self.logger = getLogger(__name__)
        # config.jsonの名前と場所は固定する。
        self.file_config = SoftConfig.FileConfig(config_path=self.CONFIG_PATH, config_name=self.CONFIG_NAME)
        self.can_config = SoftConfig.CanConfig()
        self.j1939_config = SoftConfig.J1939Config()
        self.pvsw_config = SoftConfig.PvswConfig()
        self.read_file(self.CONFIG_PATH + self.CONFIG_NAME)
    
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
            self.logger.error('error on %s', e)
            self.logger.info('read ' + self.CONFIG_PATH + self.DEF_CONFIG_NAME)
            # DEF_CONFIG_JSON_PATHで再設定する。
            self.read_file(self.CONFIG_PATH + self.DEF_CONFIG_NAME)

    def read_file(self, config_path=CONFIG_PATH + CONFIG_NAME):
        """
        設定ファイルを読み込む。
        """
        try:
            with open(config_path, 'r', encoding='utf-8') as file:
                json_load = json.load(file)
            self.__read_config(json_load)
        except Exception as e:
            self.logger.error('error on %s', e)
            self.logger.info('read ' + self.CONFIG_PATH + self.DEF_CONFIG_NAME)
            # DEF_CONFIG_JSON_PATHで再設定する。
            self.read_file(self.CONFIG_PATH + self.DEF_CONFIG_NAME)
