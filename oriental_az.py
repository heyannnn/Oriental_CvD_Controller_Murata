
from az_define import *
# from pymodbus.client import ModbusTcpClient
from pymodbus.client import ModbusSerialClient

import numpy as np

def clamp(value, min_value, max_value, low_message=None, high_message=None):
    """
    Clamps a value between a minimum and maximum value, optionally printing messages if the value is out of bounds.

    Args:
        value (float): The value to be clamped.
        min_value (float): The minimum allowable value.
        max_value (float): The maximum allowable value.
        low_message (str, optional): A message to print if the value is below the minimum. The message can contain
                                    placeholders for the value, min_value, and max_value, in that order.
        high_message (str, optional): A message to print if the value is above the maximum. The message can contain
                                    placeholders for the value, min_value, and max_value, in that order.

    Message Format:
        {0} = value
        {1} = min
        {2} = max

    Returns:
        float: The clamped value.
    """

    if value < min_value:
        if low_message:
            print(low_message.format(value, min_value, max_value))
        return min_value
    
    elif value > max_value:
        if high_message:
            print(high_message.format(value, min_value, max_value))
        return max_value
    
    return value


class OrientalMotor:
    client = None

    _azPosLimit = {
        "Min": 0, 
        "Max": 0
    }
    
    
    PosLimitDefaultMin = -2147483647
    PosLimitDefaultMax = 2147483648

    @property
    def velLimit(self):
        return self._velLimit
    
    @property
    def accLimit(self):
        return self._accLimit
    
    @property
    def posLimitMin(self):
        return self._posLimitMin
    
    @property
    def posLimitMax(self):
        return self._posLimitMax


    def __init__(self, com_port='COM4', slave_id=1, velLimit=10000, accLimit=100, posLimitMin=PosLimitDefaultMin, posLimitMax=PosLimitDefaultMax):
        self.client = ModbusSerialClient(
            port=com_port,
            baudrate=230400,
            parity='N',
            stopbits=1,
            bytesize=8,
            timeout=1
        )
        self.slave_id = slave_id
        self._velLimit = velLimit
        self._accLimit = accLimit
        self._posLimitMin = posLimitMin
        self._posLimitMax = posLimitMax


    def isConnected(self):
        return self.client.is_socket_open()
    
    def connect(self):
        port = self.client.comm_params.port
        print(f"接続中 to {port}")
        if not self.client.connect():
            print("Modbus接続失敗")

        else:
            print("Modbus接続成功")

            # check Limit
            ret = self.readLimit()
            print(f"Limit: {ret}")
    
    def close(self):
        self.client.close()    
    
    def readStaticIoOut(self) -> int:
        response = self.client.read_holding_registers(address=ADDR_STATIC_IO_OUT, count=1, device_id=self.slave_id)

        if response.isError():
            print(f"エラー発生: {response})")
            return False
        
        else:
            return response.registers[0]
    
    def readReady(self) -> bool:
        res = self.readStaticIoOut()
        return (res & (1 << StaticIOOutBitAssign.READY)) != 0
           
    def readMove(self) -> bool:
        res = self.readStaticIoOut()
        return (res & (1 << StaticIOOutBitAssign.MOVE)) != 0


    # 位置、速度、加速度、減速度のデータを生成する
    # pos: 目標位置
    # vel: 速度
    # acc: 加速度
    # dec: 減速度
    def makeDirectOperationData(self, pos, vel, opMode=OpMode.ABS_POS, startRate=10.0, stopRate=10.0, current=1.0):

        if type(opMode) != OpMode:
            raise TypeError("opMode must be OpMode Enum")

        clamp(current, 0, 1.0)

        current = int(current * 1000)
        startRate = int(startRate * 1000)
        stopRate = int(stopRate * 1000)

        # Convert signed integers to unsigned 32-bit representation
        if pos < 0:
            pos = pos & 0xFFFFFFFF
        if vel < 0:
            vel = vel & 0xFFFFFFFF

        data = [0] * 12
        data[1] = opMode                     # 運転方式
        data[2] = pos & 0xFFFF               # 目標位置
        data[3] = (pos >> 16) & 0xFFFF
        data[4] = vel & 0xFFFF               # 速度
        data[5] = (vel >> 16) & 0xFFFF
        data[6] = startRate & 0xFFFF         # 開始レート
        data[7] = (startRate >> 16) & 0xFFFF
        data[8] = stopRate & 0xFFFF          # 停止レート
        data[9] = (stopRate >> 16) & 0xFFFF
        data[10] = current & 0xFFFF          # 運転電流
        data[11] = (current >> 16) & 0xFFFF

        return data


    def moveTo(self, pos:int, vel:int = 1000, startAcc:float = 100, stopAcc:float = 100):
        # DCMD_RDYがONか確認
        #response = client.read_holding_registers(address=0x011F, count=1, device_id=self.slave_id)
        #if response.isError():
        #    print(f"エラー発生: {response}")
        #elif :

        if type(pos) != int:
            pos = int(pos)
        
        if type(vel) != int:
            vel = int(vel)
            
        if type(startAcc) != float:
            startAcc = float(startAcc)
        
        if type(stopAcc) != float:
            stopAcc = float(stopAcc)
        
         # posをLimitの範囲内に収める
        lowMsg = f"Position is over the limit: {0} > {2}"
        highMsg = f"Position is under the limit: {0} < {1}"
        clamp(pos, self._posLimitMin, self._posLimitMax, low_message=lowMsg, high_message=highMsg)
            
            
        # velをLimitの範囲内に収める
        lowMsg = f"Velocity is over the limit: {0} > {2}"
        highMsg = f"Velocity is under the limit: {0} < {1}"
        clamp(vel, 0, self._velLimit, low_message="Velocity is under the limit: {0} < 0", high_message="Velocity is over the limit: {0} > {1}")
        
    
        # startAcc, stopAccをLimitの範囲内に収める
        lowMsg = f"Start Acceleration is over the limit: {0} > {2}"
        highMsg = f"Start Acceleration is under the limit: {0} < {1}"
        clamp(startAcc, 0, self._accLimit, low_message=lowMsg, high_message=highMsg)
        
        lowMsg = f"Stop Acceleration is over the limit: {0} > {2}"
        highMsg = f"Stop Acceleration is under the limit: {0} < {1}"
        clamp(startAcc, 0, self._accLimit, low_message=lowMsg, high_message=highMsg)
        
        # データ生成
        data = self.makeDirectOperationData(pos, vel, OpMode.ABS_POS, startAcc, stopAcc)

        # データ書き込み - Write to direct data area, then trigger
        self.client.write_registers(ADDR_DIRECT_DATA, data, device_id=self.slave_id)
        self.client.write_registers(ADDR_STATIC_IO_IN, [0x0100], device_id=self.slave_id)  # TRIG bit to start

        print(f"moveTo: pos: {pos}, vel: {vel}, startAcc: {startAcc}, stopAcc: {stopAcc}")
    

    def move(self, vel:int = 1000, startAcc:float = 100, stopAcc:float = 100):
        # DCMD_RDYがONか確認
        #response = client.read_holding_registers(address=0x011F, count=1, device_id=self.slave_id)
        #if response.isError():
        #    print(f"エラー発生: {response}")
        #elif :

        if type(vel) != int:
            vel = int(vel)
            
        if type(startAcc) != float:
            startAcc = float(startAcc)
        
        if type(stopAcc) != float:
            stopAcc = float(stopAcc)
        
        # velをLimitの範囲内に収める
        lowMsg = f"Velocity is over the limit: {0} > {2}"
        highMsg = f"Velocity is under the limit: {0} < {1}"
        clamp(vel, 0, self._velLimit, low_message="Velocity is under the limit: {0} < 0", high_message="Velocity is over the limit: {0} > {1}")
        
    
        # startAcc, stopAccをLimitの範囲内に収める
        lowMsg = f"Start Acceleration is over the limit: {0} > {2}"
        highMsg = f"Start Acceleration is under the limit: {0} < {1}"
        clamp(startAcc, 0, self._accLimit, low_message=lowMsg, high_message=highMsg)
        
        lowMsg = f"Stop Acceleration is over the limit: {0} > {2}"
        highMsg = f"Stop Acceleration is under the limit: {0} < {1}"
        clamp(startAcc, 0, self._accLimit, low_message=lowMsg, high_message=highMsg)
        
        # データ生成
        data = self.makeDirectOperationData(0, vel, OpMode.CONT_SPEED_CTRL, startAcc, stopAcc)

        # データ書き込み - Write to direct data area, then trigger
        self.client.write_registers(ADDR_DIRECT_DATA, data, device_id=self.slave_id)
        self.client.write_registers(ADDR_STATIC_IO_IN, [0x0100], device_id=self.slave_id)  # TRIG bit to start

        print(f"move: vel: {vel}, startAcc: {startAcc}, stopAcc: {stopAcc}")
        

    def checkRegister(self, address, count=1):
        if self.client.is_socket_open() == False:
            print("Socket is not open")
            return None
        
        response = self.client.read_holding_registers(address=address, count=count, device_id=self.slave_id)
        
        if response.isError():
            print(f"エラー発生: {response}")
        
        else:
            return response.registers
    

    def checkAlarm(self):
        return self.checkRegister(address=ADDR_ALARM_MON)[0]


    def uint32_to_int32(self, value):
        value = np.uint32(value)  # 符号なし32ビットにする
        value = value.astype(np.int32)
        return int(value)


    def readParameter(self, param_id):
        ret = self.client.write_registers(ADDR_READ_PARAM_ID, [param_id], device_id=self.slave_id)

        ret = self.checkRegister(ADDR_READ_PARAM_ID_R)
        if ret is None:
            return None
        if ret[0] == param_id:
            ret = self.checkRegister(ADDR_READ_DATA_LOW, count=2)
            if ret is None:
                return None
            data = (ret[1] << 16) | ret[0]
            return data
        return None
        

    def writeParameter(self, param_id, value=0):
        # Use module-level constant (from az_define) not an attribute on self
        ret = self.checkRegister(ADDR_READ_WRITE_STATUS)

        if ret is None:
            print("writeParameter: failed to read status")
            return None

        if ret[0] == 0:
            ret = self.client.write_registers(ADDR_WRITE_PARAM_ID, [param_id], device_id=self.slave_id)
            ret = self.client.write_registers(ADDR_WRITE_REQ, [1], device_id=self.slave_id)
            ret = self.client.write_registers(ADDR_WRITE_REQ, [0], device_id=self.slave_id)
        else:
            print(f"writeParameter: device busy or error, status={ret[0]}")
        

    def resetAlarm(self):
        # Pass a value (0) when issuing the alarm reset command
        self.writeParameter(MentainanceCommand.ALARM_RESET, 0)
        print("Reset Alarm")

    def execPPreset(self):
        # Pass a value (0) when executing P-preset command
        self.writeParameter(MentainanceCommand.P_PRESET_EXECUTE, 0)
        print("Execute P-Preset")


    def setTorque(self, onoff):
        ret = self.checkRegister(ADDR_STATIC_IO_IN)

        if onoff:
            self.client.write_registers(ADDR_STATIC_IO_IN, [0], device_id=self.slave_id)
        else:
            self.client.write_registers(ADDR_STATIC_IO_IN, [1 << int(StaticIOInBitAssign.FREE)], device_id=self.slave_id)
            
        

    def readLimit(self) -> tuple:
        min_limit = self.readParameter(ADDR_SOFT_LIMIT_MIN)
        max_limit = self.readParameter(ADDR_SOFT_LIMIT_MAX)

        if min_limit is None or max_limit is None:
            return (None, None)

        min_limit = self.uint32_to_int32(min_limit)
        max_limit = self.uint32_to_int32(max_limit)

        return min_limit, max_limit


    def readInt32(self, address):
        ret = self.checkRegister(address=address, count=2)
        
        if ret is None:
            return None
        
        if len(ret) == 2:
            low = ret[0]
            high = ret[1]
            value = high << 16 | low
            value = self.uint32_to_int32(value)

            return value
        
        return 0        

    def readPosition(self):
        return self.readInt32(address=ADDR_POS)

    def readVelocity(self):
        return self.readInt32(address=ADDR_VEL)
        