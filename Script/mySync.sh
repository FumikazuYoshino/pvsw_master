#!/bin/bash

# 転送先のサーバー設定
DESTINATION_USER=dev
DESTINATION_HOST=118.27.68.72
DESTINATION_PATH=/home/dev/sigmaenergy-powerquality/datastore/sync_app/

#第一引数:0(Upload)の場合
if [ "$1" = "-U" ]; then
	# rsyncを使用してデータを転送
	rsync -avz -e "ssh -p 1919" --partial --progress $2 $DESTINATION_USER@$DESTINATION_HOST:$DESTINATION_PATH$3
	# rsyncの終了ステータスをチェック
	if [ $? -eq 0 ]; then
	    echo "Data transferred successfully."
	else
	    echo "Data transfer failed."
	fi
#第一引数:0(Download)の場合
elif [ "$1" = "-D" ]; then
	# rsyncを使用してデータを転送
	rsync -avz -e "ssh -p 1919" --partial --progress $DESTINATION_USER@$DESTINATION_HOST:$DESTINATION_PATH$3 $2
	# rsyncの終了ステータスをチェック
	if [ $? -eq 0 ]; then
	    echo "Data transferred successfully."
	else
	    echo "Data transfer failed."
	fi
else
	echo "Invalid arg1 param."
fi
