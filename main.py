from pynput import keyboard  # キーボード入力用
import time
import math
from pythonosc import dispatcher, osc_server
import threading
from az_define import *
from oriental_az import *
import sys
from queue import Queue, Empty

from pythonosc.udp_client import SimpleUDPClient

listener: keyboard.Listener = None

OSC_Target_Port = 50000
OSC_Rec_Port = 50002

# Modbus RTU (RS-485) の接続情報
COM_PORT = 'COM4'
SLAVE_ID = 1  # Check your driver's DIP switch settings

motorList = []


key_queue = Queue()

def on_press(key):
    try:
        key_str = key.char  # 通常キーa
        if key_str == 'a':
            print("Pressed 'a' key")
            motorList[0].moveTo(pos=6000, vel=12000, startAcc=100, stopAcc=100)
            # motorList[0].move(vel=6000, startAcc=10, stopAcc=10)

        if key_str == 'b':
            print("Pressed 'b' key")
            motorList[0].moveTo(pos=4000, vel=8000, startAcc=100, stopAcc=100)
            # motorList[0].move(vel=-3000, startAcc=10, stopAcc=10)
        
        if key_str == 'c':
            print("Pressed 'c' key")
            # motorList[0].moveTo(pos=4000, vel=8000, startAcc=100, stopAcc=100)
            motorList[0].move(vel=0, startAcc=10, stopAcc=10)
        
        if key_str == 'p':
            print("Pressed 'p' key")
            # motorList[0].moveTo(pos=4000, vel=8000, startAcc=100, stopAcc=100)
            motorList[0].execPPreset()

        if key_str == 'r':
            print("Pressed 'r' key")
            # motorList[0].moveTo(pos=4000, vel=8000, startAcc=100, stopAcc=100)
            motorList[0].resetAlarm()
        
        if key_str == 't':
            print("Pressed 't' key")
            # motorList[0].moveTo(pos=4000, vel=8000, startAcc=100, stopAcc=100)
            print(f"pos: {motorList[0].readPosition()}")
            
    except AttributeError:
        key_str = str(key)  # 特殊キー（Key.enter など）
        key_queue.put(('press', key_str))


def on_release(key):
    try:
        key_str = key.char
    except AttributeError:
        key_str = str(key)
    key_queue.put(('release', key_str))
    # 例: Escでリスナー停止（必要なら）
    if key == keyboard.Key.esc:
        return False
    

def closing():
    for motor in motorList:
        motor.close()
    

def main():
    print("Oriental Az Controller Test Program")
    motorList.append(OrientalMotor(com_port=COM_PORT, slave_id=SLAVE_ID, velLimit=10000, accLimit=100))

    for motor in motorList:
        motor.connect()

    pos = motor.readPosition()
    print(f"Current Position: {pos}")

    vel = motor.readVelocity()
    print(f"Current Velocity: {vel}")


    # リスナーを開始（非ブロッキング）
    listener = keyboard.Listener(on_press=on_press, on_release=on_release)
    listener.start()

    while True:
        try:
            #checkMotionCompRoutine()
            
            time.sleep(0.1)
            
            
            
        except KeyboardInterrupt:
            print("終了")
            closing()
            
            return
        
if __name__ == "__main__":
    main()