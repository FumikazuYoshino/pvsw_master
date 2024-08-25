import asyncio
from datetime import datetime
import json
from logging import getLogger
from soft_config import SoftConfig
from os import walk, remove
from pathlib import Path


class FileProcess:
    """
    入出力ファイルを制御する。
    """

    def __init__(self, file_config: SoftConfig.FileConfig):
        """
        fileの設定情報をインスタンスに取り込む。
        """
        self.logger = getLogger(__name__)
        self.file_config = file_config
        self.last_control_updatetime = None

    def __get_system_data_file_name(self):
        """
        周期的に保存するpythonデータの保存先ファイル名を返す。
        """
        # ディレクトリ内のファイルを検索、ソート
        file_names = []
        for _, _, files in walk(self.file_config.system_data_path):
            for name in files:
                if self.file_config.system_data_name in name:
                    file_names.append(name)
        file_names = sorted(file_names)

        if len(file_names) <= 0:
            # ファイルが存在しない場合、作成する。
            file_name = datetime.now().strftime('%Y%m%d%H%M%S') + '_' + \
                self.file_config.system_data_name
            file_names.append(file_name)
        elif len(file_names) > \
                self.file_config.system_data_file_num:
            # ファイル数が上限を超えた場合、最も数字の若いファイルを削除。
            remove(self.file_config.system_data_path +
                   file_names.pop(0))
        return self.file_config.system_data_path + file_names[-1]

    async def __do_script(self, direction, local_dir_path, server_dir_path):
        """
        上位のサーバとの通信を司るbashスクリプトの設定と起動
        """
        cmd = 'bash ' + self.file_config.script_path + self.file_config.script_name + ' '
        # 1番目の引数 -U:サーバへupload -D:サーバからdownload
        cmd += direction + ' '
        # 2番目の引数 local directoryのパス
        cmd += local_dir_path + '/ '
        # 3番目の引数 server directoryのパス(一部)
        cmd += server_dir_path + '/'
        await asyncio.create_subprocess_shell(cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)

    async def save_system_data(self, master_dict):
        self.logger.info('save data.json')
        try:
            system_file_name = self.__get_system_data_file_name()
            # json.loadを行うためには'r+'で開く必要がある。
            with open(system_file_name, 'r+', encoding='utf-8') as file:
                try:
                    # jsonデータをDict型で読み込む。(最後尾にデータを追加するため。)
                    json_data = json.load(file)
                except json.JSONDecodeError:
                    # 読み込むjsonデータがおかしいときは、全てクリアする。
                    self.logger.warning('json decode error. File cleared.')
                    json_data = {}
                file.seek(0)
                file.truncate()
                key = ''
                # 最後尾を検索する。
                for i in range(self.file_config.system_data_len):
                    key = f'master_data_{i:08x}'
                    if key not in json_data:
                        break
                # 最後尾の場合は次の更新のため、新しいファイルを生成する。
                if key in f'master_data_{(self.file_config.system_data_len - 1):08x}':
                    new_file_name = datetime.now().strftime('%Y%m%d%H%M%S') + \
                        '_' + self.file_config.system_data_name
                    with open(new_file_name, 'r+', encoding='utf-8') as file:
                        # 空のjsonデータを格納
                        json.dump({}, new_file_name, indent=4)
                # 一旦ファイル内容を消去し、その後追加したデータを格納する。
                json_data.update({key: master_dict})
                self.logger.info('dict add.')
                json.dump(json_data, file, indent=4)
            # スレーブとサーバのファイルを同期させる。
            await self.__do_script('-U', self.file_config.system_data_path, 'Data')
        except FileNotFoundError:
            # ファイルが見つからない場合は作成する。
            self.logger.info('create system_data.json')
            with open(system_file_name, 'w', encoding='utf-8') as file:
                json_data = {}
                json.dump(json_data, file, indent=4)
        except Exception as e:
            # その他のエラーを記録する。
            self.logger.error('%s', e)
          
    async def load_control_file(self):
        """
        config.jsonで指定されたものに年月日時秒を付与したファイルが存在したとき、
        そのファイルの命令に従い操作を実行する。
        """
        await self.__do_script('-D', self.file_config.control_path, 'Control')
        file_names = []
        # ディレクトリ内のファイルを検索
        for _, _, files in walk(self.file_config.control_path):
            for name in files:
                if self.file_config.control_name in name:
                    file_names.append(name)
        # 一致するファイルがない場合は、何もしない。
        if len(file_names) <= 0:
            return

        # 最も新しい時間(=数値の大きい)ものを取得
        file_names = sorted(file_names)
        file_name = file_names[-1]

        try:
            file_name_with_path = self.file_config.control_path + file_name
            mtime = datetime.fromtimestamp(Path(file_name_with_path).stat().st_mtime)
            if self.last_control_updatetime == mtime:
                # タイムスタンプの更新日が前回読み込んだものと同じ場合は無視する。
                return
            self.last_control_updatetime = mtime

            with open(file_name_with_path, 'r', encoding='utf-8') as file:
                self.logger.info('load ' + file_name)
                return json.load(file)
            # 読み込んでも該当ファイルはそのまま保持する。
        except json.JSONDecodeError:
            # 読み込むjsonデータがおかしいときは、ログのみ残し無視する。
            self.logger.warning('control.json decode error. File ignored.')
            return None
        except KeyError:
            # 読み込むjsonデータのキーが見つからない場合は、ログのみ残し無視する。
            self.logger.warning('control.json key error.')
            return None
        except Exception as e:
            # その他のエラーを記録する。
            self.logger.error('%s', e)
            return None

    async def load_config_file(self):
        """
        サーバ上にあるconfig.jsonをダウンロードする。
        ただし、本ソフト内の設定には同期せず、次回起動時に設定を反映する。
        """
        await self.__do_script('-D', self.file_config.config_path, 'Config')
