from enum import Enum
from enum import IntEnum



# モーター制御のレジスタアドレス (例: AZD_KREN の場合)
SET_OP_ID = 0x0105                  # 目標位置のレジスタ (仮)
START_COMMAND_REGISTER = 0x0106     # 動作開始コマンド
START_COMMAND_VALUE = 0x0001        # 動作開始信号

ADDR_ALARM_MON = 0x011F
ADDR_STATIC_IO_IN = 0x0106
ADDR_POS = 0x0120
ADDR_VEL = 0x0122
ADDR_TARGET_POS = 0x0124
ADDR_STATIC_IO_OUT = 0x011E
ADDR_TRIG_MODE = 0x0106
ADDR_DIRECT_DATA = 0x0058  # Direct operation data area (AZ series)

# Alternative addresses to try for operation number
ADDR_OP_NO_ALT1 = 0x0001
ADDR_OP_NO_ALT2 = 0x0400
ADDR_OP_NO_ALT3 = 0x0480

# CVD Series Register Addresses
ADDR_DRIVE_INPUT_CMD = 0x007D  # Drive Input Command Register
ADDR_OPERATION_NO = 0x007C  # Operation data number selection (try this)

# CVD Drive Input Command Values
CMD_STOP = 0
CMD_START = 3
CMD_M0_START = 7       # Start with M0 rotation
CMD_M1_START = 5       # Start with M1 rotation
CVD_CMD_JOG_FWD = 4096       # 0x1000
CVD_CMD_JOG_REV = 8192       # 0x2000
CVD_CMD_MANUAL_FWD = 16384   # 0x4000
CVD_CMD_MANUAL_REV = 32768   # 0x8000
CVD_CMD_RESET_FAULT = 256    # 0x0100
CVD_CMD_HOME = 64

ADDR_READ_PARAM_ID_R = 0x012B
ADDR_READ_WRITE_STATUS = 0x012C
ADDR_WRITE_PARAM_ID_R = 0x012D
ADDR_READ_DATA_LOW = 0x012E
ADDR_READ_DATA_HIGH = 0x012F

ADDR_READ_PARAM_ID = 0x0113
ADDR_WRITE_REQ = 0x0114
ADDR_WRITE_PARAM_ID = 0x0115
        

ADDR_SOFT_LIMIT_MIN = 0x01C5
ADDR_SOFT_LIMIT_MAX = 0x01C4



class AZAlarm(Enum):
    """
    Oriental Motor AZシリーズのアラームコードを Enum で管理
    """
    POSITION_DEVIATION_OVER = 0x10      # 位置偏差過大
    OVERCURRENT = 0x20                  # 過電流
    MAIN_CIRCUIT_OVERHEAT = 0x21        # 主回路過熱
    OVERVOLTAGE = 0x22                  # 過電圧
    MAIN_POWER_OFF = 0x23               # 主電源オフ
    LOW_VOLTAGE = 0x25                  # 不低電圧
    MOTOR_OVERHEAT = 0x26               # モーター過熱
    SENSOR_ERROR = 0x28                 # センサ異常
    CPU_CIRCUIT_ERROR = 0x29            # CPU周辺回路異常
    ABZO_SENSOR_COMM_ERROR = 0x2A       # ABZOセンサ通信異常
    OVERLOAD = 0x30                     # 過負荷
    OVERSPEED = 0x31                    # 過速度
    ABSOLUTE_POSITION_ERROR = 0x33      # 絶対位置異常
    COMMAND_PULSE_ERROR = 0x34          # 指令パルス異常
    EEPROM_ERROR = 0x41                 # EEPROM異常
    INITIAL_SENSOR_ERROR = 0x42         # 初期時センサ異常
    INITIAL_ROTATION_ERROR = 0x43       # 初期時回転異常
    ENCODER_EEPROM_ERROR = 0x44         # エンコーダEEPROM異常
    MOTOR_COMBINATION_ERROR = 0x45      # モーター組合せ異常
    HOMING_INCOMPLETE = 0x4A            # 原点復帰未完了
    SIMULTANEOUS_LS_INPUT = 0x60            # ±LS同時入力
    LS_REVERSE_CONNECTION = 0x61        # ±LS逆接続
    HOMING_OPERATION_ERROR = 0x62       # 原点復帰運転異常
    HOME_SENSOR_NOT_DETECTED = 0x63  # HOMES未検出
    TIM_ZSG_SLIT_SIGNAL_ERROR = 0x64  # TIM, ZSG, SLIT信号異常
    HARDWARE_OVERRUN = 0x66  # ハードウェアオーバートラベル
    SOFTWARE_OVERRUN = 0x67  # ソフトウェアオーバートラベル
    HOMING_OFFSET_ERROR = 0x6A  # 原点復帰時オフセット異常
    MECHANICAL_OVERRUN = 0x6D  # メカオーバートラベル
    OPERATION_DATA_ERROR = 0x70  # 運転データ異常
    ELECTRONIC_GEAR_SETTING_ERROR = 0x71  # 電子ギヤ設定異常
    ROUND_SETTING_ERROR = 0x72  # ラウンド設定異常
    NETWORK_PASS_ERROR = 0x81  # ネットワークパス異常
    NETWORK_MODULE_ERROR = 0x82  # ネットワークモジュール異常
    CPU_ERROR = 0xF0  # CPU異常

    @staticmethod
    def get_alarm_message(code):
        """
        アラームコードに対応するアラームメッセージを取得する。

        :param code: アラームコード (int)
        :return: アラーム名 (str)
        """
        for alarm in AZAlarm:
            if alarm.value == code:
                return alarm.name.replace("_", " ").title()
        return "不明なアラームコード"



class OpMode(IntEnum):
    ABS_POS = 1
    REL_POS_CMD = 2
    REL_POS_DET = 3
    CONT_POS_CTRL = 7
    ROUND_ABS_POS = 8
    ROUND_NEAR_POS = 9
    ROUND_FWD_ABS = 10
    ROUND_RVS_ABS = 11
    ROUND_ABS_PUSH = 12
    ROUND_NEAR_PUSH = 13
    ROUND_FWD_PUSH = 14
    ROUND_RVS_PUSH = 15
    CONT_SPEED_CTRL = 16
    CONT_PUSH = 17
    CONT_TORQUE = 18
    ABS_POS_PUSH = 20
    REL_POS_CMD_PUSH = 21
    REL_POS_DET_PUSH = 22    

class ReadWriteStatusBitAssign(IntEnum):
    RD_ERR = 7 # 読み込みエラー
    WR_END = 8 # 書き込み終了
    SYS_BSY = 9 # システムビジー
    WR_SET_ERR = 10 # 書き込み設定エラー
    WR_IF_ERR = 11 # 書き込みIFエラー
    WR_NV_ERR = 12 # 書き込みNVエラー
    WR_EXE_ERR = 13 # 書き込み実行エラー
    WR_ERR = 14 # 書き込みエラー

class StaticIOInBitAssign(IntEnum):
    FW_JOG = 0       # FWD方向のJOG運転を実行します。
    RV_JOG = 1       # RVS方向のJOG運転を実行します。
    RESERVED_2 = 2   # 予約（値は無視される）
    START = 3        # ストアードデータ（SD）運転を実行します。
    ZHOME = 4        # 高速原点復帰運転を実行します。
    STOP = 5         # モーターを停止させます。
    FREE = 6         # モーターの電流を遮断して無励磁にします。
    ALM_RST = 7      # 発生中のアラームを解除します。
    TRIG = 8         # ダイレクトデータ運転を実行します。
    TRIG_MODE = 9    # TRIGの判定基準を設定（0: ONエッジ、1: ONレベル）
    RESERVED_10 = 10 # 予約（値は無視される）
    RESERVED_11 = 11 # 予約（値は無視される）
    FW_JOG_P = 12    # FWD方向のインチング運転を実行します。
    RV_JOG_P = 13    # RVS方向のインチング運転を実行します。
    FW_POS = 14      # FWD方向の連続運転を実行します。
    RV_POS = 15      # RVS方向の連続運転を実行します。

class StaticIOOutBitAssign(IntEnum):
    SEQ_BSY = 0         # ストアードデータ（SD）運転が行なわれているときに出力されます。
    MOVE = 1            # モーターが動作中のときに出力されます。
    IN_POS = 2          # 位置決め運転が完了したときに出力されます。
    START_R = 3         # 入力信号に対する応答を出力します。
    HOME_END = 4        # 原点復帰運転の終了時、および位置プリセットの実行時に出力されます。
    READY = 5           # ドライバの運転準備が完了したときに出力されます。
    DCMD_RDY = 6        # ダイレクトデータ運転の準備が完了したときに出力されます。
    ALM_A = 7           # ドライバのアラーム状態を出力します。（A接点）
    TRIG_R = 8          # 入力信号に対する応答を出力します。
    TRIG_MODE_R = 9     # 入力信号に対する応答を出力します。
    SET_ERR = 10        # ダイレクトデータ運転の設定エラーがあるときに出力されます。
    EXE_ERR = 11        # ダイレクトデータ運転の実行に失敗したときに出力されます。
    DCMD_FULL = 12      # ダイレクトデータのバッファ領域にデータが書き込まれているときに出力されます。
    STOP_R = 13         # 入力信号に対する応答を出力します。
    RESERVED = 14       # 予約（0が返ります）
    TLC = 15            # 出力トルクが上限値に到達すると出力されます。


class MentainanceCommand(IntEnum):
    ALARM_RESET = 0x00C0       # 192 - アラームのリセット
    ALARM_HISTORY_CLEAR = 0x00C2  # 194 - アラーム履歴のクリア
    P_PRESET_EXECUTE = 0x00C5  # 197 - P-PRESET実行
    CONFIGURATION = 0x00C6     # 198 - Configuration
    DATA_INITIALIZE = 0x00C7   # 199 - データ一括初期化 (通信用パラメータ除く)
    NV_MEMORY_READ = 0x00C8    # 200 - NVメモリ一括読み出し
    NV_MEMORY_WRITE = 0x00C9   # 201 - NVメモリ一括書き込み
    FULL_DATA_INITIALIZE = 0x00CA  # 202 - 全データ一括初期化 (通信用パラメータ含む)
    BACKUP_LOAD = 0x00CB       # 203 - バックアップデータ読み出し
    BACKUP_SAVE = 0x00CC       # 204 - バックアップデータ書き込み
    LATCH_INFO_CLEAR = 0x00CD  # 205 - ラッチ情報のクリア
    SEQUENCE_HISTORY_CLEAR = 0x00CE  # 206 - シーケンス履歴のクリア
    TRIP_METER_CLEAR = 0x00CF  # 207 - TRIPメーターのクリア
    ZSG_PRESET = 0x00D1        # 209 - ZSG-PRESET
    ZSG_PRESET_CLEAR = 0x00D2  # 210 - ZSG-PRESETクリア
    INFO_CLEAR = 0x00D3        # 211 - インフォメーションのクリア
    INFO_HISTORY_CLEAR = 0x00D4  # 212 - インフォメーション履歴のクリア
    ALARM_HISTORY_EXPAND = 0x00D5  # 213 - アラーム履歴詳細展開
