from logging import getLogger
from soft_config import SoftConfig
import json

    
class PvswParam:
    """
    Pvswの各種パラメータを格納する。
    """
    def __init__(self, file_config: SoftConfig.FileConfig):
        """
        paramのdict型はnullにする。
        """
        self.name = ''
        self.version = ''
        self.__logger = getLogger(__name__)
        self.__file_config = file_config
        self.param = self.__get_from_master_file()

    def __get_from_master_file(self):
        """
        指定されたmasterファイルからパラメータ類を生成する。
        """
        self.__logger.info('param set start.')
        try:
            file_path = self.__file_config.config_path + \
                self.__file_config.parameter_list_master_name
            with open(file_path, 'r', encoding='utf-8') as file:
                json_load = json.load(file)
                param = json_load
            file_path = self.__file_config.config_path + \
                self.__file_config.parameter_list_slave_name
            with open(file_path, 'r', encoding='utf-8') as file:
                json_load = json.load(file)
                param['parameters']['slave_0001'] = json_load
            return param
        except Exception as e:
            self.__logger.error('error on %s', e)

    def __get_dict_top(self, param_dict):
        """
        parameterの先頭を示す。
        """
        dict = {}
        for key, value in param_dict.items():
            match key:
                case 'parameters':
                    dict[key] = self.__get_dict_child(value)
                case _:
                    pass
        return dict

    def __get_dict_child(self, param_dict):
        """
        parameterの子要素を示す。
        """
        dict = {}
        for key, value in param_dict.items():
            for i_key, i_value in value.items():
                if i_key == 'parameters':
                    dict[key] = self.__get_dict_child(i_value)
                elif (i_key == 'type') and (i_value['writeEnable'] is False):
                    # writeEnableは書き込み専用なのでサーバに送信しない.
                    dict[key] = i_value['value']
        return dict

    def __set_param(self, set_dict, param):
        """
        set_dictのkey,valueの構造からデータを格納する。
        """
        for key, value in set_dict.items():
            if key in param:
                if isinstance(value, dict):
                    self.__set_param(value, param[key]['parameters'])
                else:
                    param[key]['type']['value'] = value

    def get_system_data_dict(self):
        """
        外部にsystem_dataとして出力するためのDictを生成する。
        """
        return self.__get_dict_top(self.param)

    def set_param_write_value(self, set_dict):
        """
        外部からの書き込みデータを反映させる。
        Slaveはこの他に通信処理が必要
        """
        self.__set_param(set_dict['parameters'], self.param['parameters'])

    def add_write_action(self, name, command):
        pass
