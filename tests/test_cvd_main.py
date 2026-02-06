import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import readchar  # キーボード入力用
import time
import math
from pythonosc import dispatcher, osc_server
import threading
from drivers.cvd_define import *
from drivers.oriental_cvd import *
from queue import Queue, Empty
import asyncio
import json

# ロックオブジェクトを作成
comm_lock = threading.Lock()

# 終了フラグ
is_shutting_down = False

# キー入力スレッド
key_reader_thread = None

# ホーミングスレッドの参照
homing_thread = None

# 設定ファイルを読み込む
def load_config():
	config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'config.json')
	try:
		with open(config_path, 'r', encoding='utf-8') as f:
			return json.load(f)
	except FileNotFoundError:
		print(f"設定ファイルが見つかりません: {config_path}")
		print("デフォルト値を使用します")
		return {
			"port": "COM18",
			"osc_target_port": 50000,
			"osc_rec_port": 50002
		}
	except json.JSONDecodeError as e:
		print(f"設定ファイルの読み込みエラー: {e}")
		print("デフォルト値を使用します")
		return {
			"port": "COM18",
			"osc_target_port": 50000,
			"osc_rec_port": 50002
		}


# 設定を読み込む
config = load_config()

OSC_Target_Port = config.get("osc_target_port", 50000)
OSC_Rec_Port = config.get("osc_rec_port", 50002)

# ModbusTCPの接続情報
Port = config.get("port")
#Port = "/dev/tty.usbserial-FT78LMAE"

motorController = None


key_queue = Queue()

def _homing(timeout=100):
	global homing_thread
	try:
		asyncio.run(motorController.start_homing_async(timeout=timeout))
	except Exception as e:
		print(f"Homing thread error: {e}")
	finally:
		print("Homing thread finished.")
		homing_thread = None  # スレッド参照をクリア

def run_homing(timeout=100)->threading.Thread:
	thread = threading.Thread(target=_homing, args=(timeout,), daemon=True)
	thread.start()
	return thread

def process_key(key_str):
	"""キー入力を処理する共通関数"""
	global homing_thread
	
	with comm_lock:
		try:
			if key_str == 'a':
				print("Pressed 'a' key")
				motorController.start_continous_macro(1)

			elif key_str == 'b':
				print("Pressed 'b' key")
				motorController.start_continous_macro(-1)
			
			elif key_str == 'c':
				print("Pressed 'c' key")
				motorController.start_continous_macro(0)
			
			elif key_str == 'h':
				print("Pressed 'h' key")
				homing_thread = run_homing()
			
			elif key_str == 'p':
				print("Pressed 'p' key")
				motorController.start_direct_operation(0, position=222, velocity=2222, startRate=4001, stopRate=4001, mode=OPMode.ABSOLUTE)
				
			elif key_str == 'o':
				print("Pressed 'o' key")
				motorController.start_direct_operation(1, position=3333, velocity=3333, startRate=6002, stopRate=6002, mode=OPMode.ABSOLUTE, current=0.5)

			elif key_str == 'r':
				print("Pressed 'r' key")
				ret = motorController.read_output_signal()
				readyVal = ret & OutputSignal.READY
				moveVal = ret & OutputSignal.MOVE
				print(f"Output Signal: {ret:04X}, READY: {'ON' if readyVal else 'OFF'}, MOVE: {'ON' if moveVal else 'OFF'}")

			elif key_str == 's':
				print("Pressed 's' key")
				motorController.send_input_signal(signal=InputSignal.START)
			
			elif key_str == '1':
				print("Pressed '1' key")
				motorController.send_start_signal()
			
			elif key_str == '2':
				print("Pressed '2' key")
				motorController.send_stop_signal()

			elif key_str == '3':
				motorController.send_signal_off()
				print("Pressed '3' key")
			
			elif key_str == 'q':
				print("Quit command")
				return False
				
		except (OSError, Exception) as e:
			if not is_shutting_down:
				print(f"Error in key handler: {e}")
	
	return True

def key_reader():
	"""readcharでキー入力を読み取るスレッド"""
	global is_shutting_down
	print("キー入力待機中... (qで終了)")
	
	while not is_shutting_down:
		try:
			key = readchar.readchar()
			if not process_key(key):
				# 終了コマンド
				import os
				os.kill(os.getpid(), 2)
				break
		except KeyboardInterrupt:
			break
		except Exception as e:
			if not is_shutting_down:
				print(f"Key reader error: {e}")
			break
	

def closing():
	global is_shutting_down
	is_shutting_down = True
	
	# モーターコントローラーをクリーンアップ
	if motorController is not None:
		try:
			motorController.close()
		except Exception as e:
			print(f"Error closing motor controller: {e}")
	

def main():
	print("Oriental Az Controller Test Program")
	
	# ポート設定をチェック
	if Port is None or Port == "":
		print("エラー: ポートが設定されていません。")
		print("config.jsonファイルで'port'を設定してください。")
		sys.exit(1)
	
	global motorController, key_reader_thread
	motorController = OrientalCvdMotor(port=Port)
	motorController.connect()

	# キー入力リーダーを開始
	key_reader_thread = threading.Thread(target=key_reader, daemon=True)
	key_reader_thread.start()

	while True:
		try:
			time.sleep(0.1)
		except KeyboardInterrupt:
			print("\n終了")
			closing()
			return
		
if __name__ == "__main__":
	main()