from .cvd_define import *

from pymodbus.client import ModbusSerialClient
import asyncio
import time
import numpy as np


def clamp(value, min_value, max_value, low_message=None, high_message=None):

    if value < min_value:
        if low_message:
            print(low_message.format(value, min_value, max_value))
        return min_value

    elif value > max_value:
        if high_message:
            print(high_message.format(value, min_value, max_value))
        return max_value

    return value


class OrientalCvdMotor:
    client = None

    PosLimitDefaultMin = -2147483647
    PosLimitDefaultMax = 2147483648

    @property
    def velLimit(self):
        return self._velLimit

    @property
    def accLimit(self):
        return self._accLimit

    # @property
    # def posLimitMin(self):
    #     return self._posLimitMin

    # @property
    # def posLimitMax(self):
    #     return self._posLimitMax

    def __init__(self, port):

        # 通信設定: 115200bps, 8bit, 偶数パリティ, ストップビット1 [4], [5], [6]
        self.client = ModbusSerialClient(
            port=port, baudrate=230400, parity="N", stopbits=1, bytesize=8, timeout=0.1
        )

        # self.initialize_jog_mapping(slave_id=1)

        # self._velLimit = velLimit
        # self._accLimit = accLimit
        # self._posLimitMin = posLimitMin
        # self._posLimitMax = posLimitMax

    def isConnected(self):
        return self.client.is_socket_open()

    def connect(self):
        if self.client.connect():
            print("Connected to CVD Motor")
        else:
            print("Failed to connect to CVD Motor")

    def close(self):
        self.client.close()

    # TODO:
    # def readStaticIoOut(self) -> int:
    #     response = self.client.read_holding_registers(address=ADDR_STATIC_IO_OUT, count=1, device_id=0)

    #     if response.isError():
    #         print(f"エラー発生: {response})")
    #         return False

    #     else:
    #         return response.registers[0]

    # TODO:
    # def readReady(self) -> bool:
    #     res = self.readStaticIoOut()
    #     return (res & (1 << StaticIOOutBitAssign.READY)) != 0

    # TODO:
    # def readMove(self) -> bool:
    #     res = self.readStaticIoOut()
    #     return (res & (1 << StaticIOOutBitAssign.MOVE)) != 0

    
    
    

    # def checkAlarm(self):
    #     return self.checkRegister(address=ADDR_ALARM_MON)[0]

    def uint32_to_int32(self, value):
        value = np.uint32(value)  # 符号なし32ビットにする
        value = value.astype(np.int32)
        return int(value)

    
    # TODO:
    # def resetAlarm(self):
    #     # Pass a value (0) when issuing the alarm reset command
    #     self.writeParameter(MentainanceCommand.ALARM_RESET, 0)
    #     print("Reset Alarm")

    # TODO:
    # def execPPreset(self):
    #     # Pass a value (0) when executing P-preset command
    #     self.writeParameter(MentainanceCommand.P_PRESET_EXECUTE, 0)
    #     print("Execute P-Preset")

    # TODO:
    # def setTorque(self, onoff):
    #     ret = self.checkRegister(ADDR_STATIC_IO_IN)

    #     if onoff:
    #         self.client.write_registers(ADDR_STATIC_IO_IN, [0], device_id=0)
    #     else:
    #         self.client.write_registers(ADDR_STATIC_IO_IN, [1 << int(StaticIOInBitAssign.FREE)], device_id=0)

    
    

    """2つの16bitレジスタを1つの符号付き32bit整数に結合する [1]"""

    def _combine_32bit(self, registers):
        high = registers
        low = registers[7]
        value = (high << 16) | low
        # 符号付き(32bit 2の補数)の処理
        if value & 0x80000000:
            value -= 0x100000000
        return value

    """32bit整数を2つの16bitレジスタ用に分割する [2]"""

    def _split_32bit(self, value):

        if value < 0:
            value += 0x100000000
        high = (value >> 16) & 0xFFFF
        low = value & 0xFFFF
        return [high, low]

    """モニタ値を読み出す (FC03: 保持レジスタの読み出し) [8], [1]"""

    def read_monitor(self, command: MonitorCommand, slave_id=1):
        # 指定した上位アドレスから2レジスタ分を読み出す
        result = self.client.read_holding_registers(
            address=command, count=2, slave=slave_id
        )

        if not result.isError():
            return self._combine_32bit(result.registers)
        else:
            print(f"Error reading {command.name}")
            return None

    """32bitパラメータを書き込む (FC10: 複数保持レジスタへの書き込み) [8], [2]"""

    def write_parameter(self, address, value, slave_id=1):
        registers = self._split_32bit(value)
        # 上位・下位を同時に書き込むことが推奨されている [2]
        result = self.client.write_registers(
            address=address, values=registers, slave=slave_id
        )
        return not result.isError()

    """
    (P228) 運転データNo.の基準アドレスを取得する
    :param data_no: 運転データNo. (0 ～ 255)
    :return: 基準アドレス (16進数整数)
    """

    def get_operation_data_base_address(self, data_no: int) -> int:

        if not (0 <= data_no <= 255):
            raise ValueError("運転データNo.は0から255の範囲で指定してください。")

        # 基準アドレス = 1800h + (データNo. × 40h)
        base_address = 0x1800 + (data_no * 0x40)
        return base_address

    """
        モーターの無励磁(FREE/AWO)状態を切り替える
        IORegister.DRIVER_INPUT_COMMAND の下位レジスタ (007Dh) の AWO ビットを操作する
        """

    def set_free_mode(self, enable: bool, slave_id=1):

        # IORegister.DRIVER_INPUT_COMMANDは上位アドレス(007Ch)なので、下位は+1
        address = IORegister.DRIVER_INPUT_COMMAND + 1  # 007Dh

        # InputSignal.AWO ビットを使用
        value = int(InputSignal.AWO) if enable else 0x0000

        print(
            f"Setting free mode to {'enabled' if enable else 'disabled'} for slave {slave_id}"
        )

        # 単一レジスタ書き込み (FC06)
        result = self.client.write_register(
            address=address, value=value, device_id=slave_id
        )

        if result.isError():
            print(f"Error setting free mode for slave {slave_id}")
            return False

        else:
            print(
                f"Set free mode to {'enabled' if enable else 'disabled'} for slave {slave_id}"
            )

        return True


    # FIXME: 要修正
    # """
    #     手順2: リモートI/OにJOG信号を割り付け、有効化する [6, 7]
    #     初期値で未使用の R-IN8 に FW-JOG(48)、R-IN9 に RV-JOG(49) を割り付けます。
    # """
    # def initialize_jog_mapping(self, slave_id=1):

    #     # R-IN8機能選択 (上位 1210h) に 48 (FW-JOG) を書き込み
    #     fw_jog_map = self._split_32bit(InputAssignment.FW_JOG)
    #     self.client.write_registers(
    #         address=RemoteIOParameter.R_IN8_FUNC, values=fw_jog_map, device_id=slave_id
    #     )

    #     # R-IN9機能選択 (上位 1212h) に 49 (RV-JOG) を書き込み
    #     rv_jog_map = self._split_32bit(InputAssignment.RV_JOG)
    #     self.client.write_registers(
    #         address=RemoteIOParameter.R_IN9_FUNC, values=rv_jog_map, device_id=slave_id
    #     )

    #     # 設定を反映させるため MaintenanceCommand.CONFIGURATION を実行
    #     # 1を書き込むと実行される
    #     self.client.write_register(
    #         address=MaintenanceCommand.CONFIGURATION, value=1, device_id=slave_id
    #     )

    # def drive_jog(self, direction, slave_id=1):
    #     """
    #     手順3: JOG運転を実行/停止する [4]
    #     :param direction: 1=正転(FW-JOG), -1=逆転(RV-JOG), 0=停止
    #     """
    #     signal = None
    #     if direction == 1:
    #         signal = InputSignal.FW_POS  # FW-JOG ON
    #     elif direction == -1:
    #         signal = InputSignal.RV_POS  # RV-JOG ON
    #     else:
    #         signal = InputSignal.OFF  # 停止
        
    #     self.send_input_signal(signal=signal, slave_id=slave_id)



    def send_input_signal(self, signal:InputSignal, slave_id=1)-> bool:
        """
        IORegister.DRIVER_INPUT_COMMAND の下位レジスタ (007Dh) を操作する
        :param signal: InputSignal Enum
        """

        address = IORegister.DRIVER_INPUT_COMMAND + 1  # 007Dh
        value = int(signal)
        #print(f"Sending input signal {signal.name} with value {value:#06x} to slave {slave_id}")

        # 単一レジスタ書き込み (FC06)
        result = self.client.write_register(address=address, value=value, device_id=slave_id)

        if result.isError():
            print(f"Error sending input signal {signal.name} to slave {slave_id}")
            return False

        else:
            #print(f"Sent input signal {signal.name} to slave {slave_id}")
            pass

        return True

    # def drive_jog_h(self, direction, slave_id=1):


    # direction: 1=正転(FW-JOG), -1=逆転(RV-JOG), 0=停止
    def start_continous_macro(self, direction, slave_id=1):
        """
        手順3: JOG運転を実行/停止する [4]
        :param direction: 1=正転(FW-JOG), -1=逆転(RV-JOG), 0=停止
        """
        signal = None
        if direction == 1:
            signal = InputSignal.FW_POS  # FW-JOG ON
        elif direction == -1:
            signal = InputSignal.RV_POS  # RV-JOG ON
        else:
            signal = InputSignal.OFF  # 停止
        
        self.send_input_signal(signal=signal, slave_id=slave_id)

    def send_start_signal(self, slave_id=1):
        self.send_input_signal(signal=InputSignal.START, slave_id=slave_id)

    def send_stop_signal(self, slave_id=1):
        self.send_input_signal(signal=InputSignal.STOP, slave_id=slave_id)

    def send_signal_reset(self, slave_id=1):
        self.send_input_signal(signal=InputSignal.OFF, slave_id=slave_id)
    
    
    def set_operation_no(self, data_no=0, slave_id=1):
        # 運転データNo.の選択 (NET選択番号 007Ah) [10, 11]
        self.client.write_registers(address=IORegister.NET_SEL_DATA_BASE, values=self._split_32bit(data_no), device_id=slave_id)
    
    def make_operation_data(self, position=0, velocity=2000, startRate=1000, stopRate=1000, mode:OPMode=OPMode.ABSOLUTE, current=1.0) -> list:
        # Check Args
        current = clamp(current, 0, 1.0)
        current_int = int(current * 1000)

        # 運転データの設定
        vals = []
        vals += self._split_32bit(int(mode)) # mode
        vals += self._split_32bit(position) # position
        vals += self._split_32bit(velocity) # velocity
        vals += self._split_32bit(startRate) # startRate
        vals += self._split_32bit(stopRate) # stopRate
        vals += self._split_32bit(current_int) # current

        return vals


    def set_operation_data(self, data_no=0, position=0, velocity=2000, startRate=1000, stopRate=1000, mode:OPMode=OPMode.ABSOLUTE, current=1.0, slave_id=1):
        
        # 運転データNo.の選択
        self.set_operation_no(data_no=data_no, slave_id=slave_id)

        data = self.make_operation_data(position=position, velocity=velocity, startRate=startRate, stopRate=stopRate, mode=mode, current=current)
        
        self.client.write_registers(
            address=self.get_operation_data_base_address(data_no),
            values=data,
            device_id=slave_id,
        )
    
    def start_direct_operation(self, data_no=0, position=0, velocity=2000, startRate=1000, stopRate=1000, mode:OPMode=OPMode.ABSOLUTE, current=1.0, slave_id=1):
            
        data = self.make_operation_data(position=position, velocity=velocity, startRate=startRate, stopRate=stopRate, mode=mode, current=current)
        
        data = self._split_32bit(data_no) + data
        data += self._split_32bit(1)  # 反映トリガー=1:全データ反映

        self.client.write_registers(
            address=ADDR_DIRECT_OPERATION,
            values=data,
            device_id=slave_id,
        )
    

    def read_output_signal(self, slave_id=1) -> int:
        """
        IORegister.DRIVER_OUTPUT_STATUS の下位レジスタ (007Eh) を読み取る
        :return: 出力信号ステータスの整数値
        """

        address = IORegister.DRIVER_OUTPUT_STATUS + 1  # 007Eh

        #print(f"Reading output signal status from slave {slave_id}")

        # 単一レジスタ読み取り (FC03)
        result = self.client.read_holding_registers(address=address, count=1, device_id=slave_id)

        if result.isError():
            print(f"Error reading output signal status from slave {slave_id}")
            return None

        else:
            status = result.registers[0]
            #print(f"Output signal status from slave {slave_id}: {status:#06x}")
            return status
    
    def checkReadyFlag(self, slave_id=1) -> bool:
        status = self.read_output_signal(slave_id=slave_id)
        if status is None:
            return False
        
        ready_flag = (status & OutputSignal.READY) != 0
        return ready_flag
    
    def checkHomeEndFlag(self, slave_id=1) -> bool:
        status = self.read_output_signal(slave_id=slave_id)
        if status is None:
            return False
        
        ready_flag = (status & OutputSignal.HOME_END) != 0
        return ready_flag

    async def _wait_homing_complete(self, slave_id=1):
        b = False
        startTime = time.time()
        while True:
            b = self.checkHomeEndFlag(slave_id=slave_id)
            elapsed = time.time() - startTime
            print(f"elapsed: {elapsed:.1f}s", end='\r', flush=True)

            #print(f"HomeEnd Flag: {'ON' if b else 'OFF'}")
            if b:
                break

            await asyncio.sleep(0.2)  # 他のタスクに処理権を譲る


    """
    ホーミング運転を開始する
    """
    async def start_homing_async(self, timeout=100, slave_id=1):
        print("Homing started...")
        self.send_input_signal(signal=InputSignal.HOME, slave_id=slave_id)

        try:
            await asyncio.wait_for(self._wait_homing_complete(slave_id=slave_id), timeout=timeout)
            print("\r\nHoming completed successfully.")
            self.send_input_signal(signal=InputSignal.OFF, slave_id=slave_id)

        except asyncio.TimeoutError:
            print("Homing operation timed out.")
            self.send_input_signal(signal=InputSignal.OFF, slave_id=slave_id)
        
        except Exception as e:
            print(f"Error during homing operation: {e}")


            
