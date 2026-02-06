from enum import Enum
from enum import IntEnum
from enum import IntFlag



ADDR_DIRECT_OPERATION = 0x0058






class InfomationCode(IntFlag):
    # Information name (English) = Information code (hex)

    DRIVER_TEMPERATURE = 0x00000004          # ドライバ温度
    OVERVOLTAGE = 0x00000010                 # 過電圧
    UNDERVOLTAGE = 0x00000020                # 不足電圧
    STARTUP_FAILURE = 0x00000200             # 運転起動失敗
    PRESET_REQUEST = 0x00000800              # プリセット要求中
    MOTOR_SETTING_ABNORMAL = 0x00001000      # モーター設定異常
    RS485_COMMUNICATION_ABNORMAL = 0x00008000 # RS-485通信異常
    FORWARD_OPERATION_PROHIBITED = 0x00010000 # 正転方向運転禁止状態
    REVERSE_OPERATION_PROHIBITED = 0x00020000 # 逆転方向運転禁止状態
    TRIP_METER = 0x00100000                  # TRIPメーター
    ODO_METER = 0x00200000                   # ODOメーター
    START_INHIBIT_MODE = 0x10000000          # 運転起動制限モード
    TEST_MODE = 0x20000000                   # I/Oテストモード
    CONFIG_REQUEST = 0x40000000              # コンフィグ要求
    RESTART_REQUEST = 0x80000000             # 再起動要求

    def get_alarm_message(code: int) -> str:
        """
        アラームコード（インフォメーションコード）に対応するメッセージを取得する。

        :param code: インフォメーションコード (int, 32bit)
        :return: アラーム名 / インフォメーション名 (str)
        """

        if code == 0:
            return "NO_INFORMATION"

        messages = []
        remaining = code

        for info in InfomationCode:
            if code & info:
                messages.append(info.name)
                remaining &= ~info

        if remaining != 0:
            messages.append(f"UNKNOWN(0x{remaining:08X})")

        return " | ".join(messages)


class OpMode(IntEnum):
     ABS_POS = 1
     REL_POS = 2

# class ReadWriteStatusBitAssign(IntEnum):
#     RD_ERR = 7 # 読み込みエラー
#     WR_END = 8 # 書き込み終了
#     SYS_BSY = 9 # システムビジー
#     WR_SET_ERR = 10 # 書き込み設定エラー
#     WR_IF_ERR = 11 # 書き込みIFエラー
#     WR_NV_ERR = 12 # 書き込みNVエラー
#     WR_EXE_ERR = 13 # 書き込み実行エラー
#     WR_ERR = 14 # 書き込みエラー

# class StaticIOInBitAssign(IntEnum):
#     FW_JOG = 0       # FWD方向のJOG運転を実行します。
#     RV_JOG = 1       # RVS方向のJOG運転を実行します。
#     RESERVED_2 = 2   # 予約（値は無視される）
#     START = 3        # ストアードデータ（SD）運転を実行します。
#     ZHOME = 4        # 高速原点復帰運転を実行します。
#     STOP = 5         # モーターを停止させます。
#     FREE = 6         # モーターの電流を遮断して無励磁にします。
#     ALM_RST = 7      # 発生中のアラームを解除します。
#     TRIG = 8         # ダイレクトデータ運転を実行します。
#     TRIG_MODE = 9    # TRIGの判定基準を設定（0: ONエッジ、1: ONレベル）
#     RESERVED_10 = 10 # 予約（値は無視される）
#     RESERVED_11 = 11 # 予約（値は無視される）
#     FW_JOG_P = 12    # FWD方向のインチング運転を実行します。
#     RV_JOG_P = 13    # RVS方向のインチング運転を実行します。
#     FW_POS = 14      # FWD方向の連続運転を実行します。
#     RV_POS = 15      # RVS方向の連続運転を実行します。

# class StaticIOOutBitAssign(IntEnum):
#     SEQ_BSY = 0         # ストアードデータ（SD）運転が行なわれているときに出力されます。
#     MOVE = 1            # モーターが動作中のときに出力されます。
#     IN_POS = 2          # 位置決め運転が完了したときに出力されます。
#     START_R = 3         # 入力信号に対する応答を出力します。
#     HOME_END = 4        # 原点復帰運転の終了時、および位置プリセットの実行時に出力されます。
#     READY = 5           # ドライバの運転準備が完了したときに出力されます。
#     DCMD_RDY = 6        # ダイレクトデータ運転の準備が完了したときに出力されます。
#     ALM_A = 7           # ドライバのアラーム状態を出力します。（A接点）
#     TRIG_R = 8          # 入力信号に対する応答を出力します。
#     TRIG_MODE_R = 9     # 入力信号に対する応答を出力します。
#     SET_ERR = 10        # ダイレクトデータ運転の設定エラーがあるときに出力されます。
#     EXE_ERR = 11        # ダイレクトデータ運転の実行に失敗したときに出力されます。
#     DCMD_FULL = 12      # ダイレクトデータのバッファ領域にデータが書き込まれているときに出力されます。
#     STOP_R = 13         # 入力信号に対する応答を出力します。
#     RESERVED = 14       # 予約（0が返ります）
#     TLC = 15            # 出力トルクが上限値に到達すると出力されます。

class MaintenanceCommand(IntEnum):
    # 0180h - 01AFh メンテナンスコマンド（上位アドレスのみ）

    ALARM_RESET = 0x0180                 # (384) アラームのリセット
    ALARM_HISTORY_CLEAR = 0x0184         # (388) アラーム履歴のクリア
    COMM_ERROR_HISTORY_CLEAR = 0x0188    # (392) 通信エラー履歴のクリア
    P_PRESET_EXECUTE = 0x018A            # (394) P-PRESET実行
    CONFIGURATION = 0x018C               # (396) Configuration
    DATA_INITIALIZE = 0x018E             # (398) データ一括初期化（通信用パラメータ除く）
    NV_MEMORY_READ = 0x0190              # (400) NVメモリー一括読み出し
    NV_MEMORY_WRITE = 0x0192             # (402) NVメモリー一括書き込み
    FULL_DATA_INITIALIZE = 0x0194        # (404) 全データ一括初期化（通信用パラメータ含む）
    LATCH_INFO_CLEAR = 0x019A            # (410) ラッチ情報のクリア
    SEQUENCE_HISTORY_CLEAR = 0x019C      # (412) シーケンス履歴のクリア
    TRIP_METER_CLEAR = 0x019E            # (414) TRIPメーターのクリア
    INFO_CLEAR = 0x01A6                  # (422) インフォメーションのクリア
    INFO_HISTORY_CLEAR = 0x01A8          # (424) インフォメーション履歴のクリア
    ALARM_HISTORY_EXPAND = 0x01AA        # (426) アラーム履歴詳細展開


class MonitorCommand(IntEnum):
    """
    CVDシリーズ RS-485通信タイプ モニタコマンド レジスタアドレス(上位)一覧
    すべてREAD専用。32bitデータのため、このアドレスから2レジスタを一括で読み出します。
    """
    
    # --- アラーム履歴 [1, 2] ---
    PRESENT_ALARM = 0x0080          # 現在のアラーム
    ALARM_HISTORY_1 = 0x0082        # アラーム履歴1（最新）
    ALARM_HISTORY_2 = 0x0084
    ALARM_HISTORY_3 = 0x0086
    ALARM_HISTORY_4 = 0x0088
    ALARM_HISTORY_5 = 0x008A
    ALARM_HISTORY_6 = 0x008C
    ALARM_HISTORY_7 = 0x008E
    ALARM_HISTORY_8 = 0x0090
    ALARM_HISTORY_9 = 0x0092
    ALARM_HISTORY_10 = 0x0094       # アラーム履歴10（最古）

    # --- 通信エラー履歴 [2, 3] ---
    CURRENT_COMM_ERROR = 0x00AC     # 現在の通信エラー
    COMM_ERROR_HISTORY_1 = 0x00AE   # 通信エラー履歴1（最新）
    COMM_ERROR_HISTORY_2 = 0x00B0
    COMM_ERROR_HISTORY_3 = 0x00B2
    COMM_ERROR_HISTORY_4 = 0x00B4
    COMM_ERROR_HISTORY_5 = 0x00B6
    COMM_ERROR_HISTORY_6 = 0x00B8
    COMM_ERROR_HISTORY_7 = 0x00BA
    COMM_ERROR_HISTORY_8 = 0x00BC
    COMM_ERROR_HISTORY_9 = 0x00BE
    COMM_ERROR_HISTORY_10 = 0x00C0  # 通信エラー履歴10（最古）

    # --- 運転状態 [3-5] ---
    SELECTED_DATA_NO = 0x00C2       # 現在の選択データNo.
    RUNNING_DATA_NO = 0x00C4        # 現在の運転データNo.（停止中は-1）
    COMMAND_POSITION = 0x00C6       # 指令位置 [step]
    COMMAND_SPEED_RPM = 0x00C8      # 指令速度 [r/min]
    COMMAND_SPEED_HZ = 0x00CA       # 指令速度 [Hz]
    DWELL_TIME_LEFT = 0x00D2        # ドウェルの残り時間 [ms]
    DIRECT_IO = 0x00D4              # ダイレクトI/Oの状態
    TARGET_POSITION = 0x00DE        # ターゲット位置（絶対座標）
    NEXT_DATA_NO = 0x00E0           # Next No.（結合先データNo.）
    LOOP_START_NO = 0x00E2          # ループ戻りNo.
    LOOP_COUNT = 0x00E4             # ループカウント（現在の回数）

    # --- 管理・メンテナンス情報 [5, 6] ---
    EVENT_MON_CMD_POS = 0x00F2      # イベントモニタ指令位置（運転停止時）
    PRESENT_INFO = 0x00F6           # 現在のインフォメーションコード
    DRIVER_TEMPERATURE = 0x00F8     # ドライバ温度 (1=0.1℃)
    ODO_METER = 0x00FC              # ODOメーター (積算回転量 1=0.1 kRev)
    TRIP_METER = 0x00FE             # TRIPメーター (総回転量 1=0.1 kRev)

    # --- シーケンス履歴 [6, 7] ---
    SEQ_HISTORY_1 = 0x0100          # シーケンス履歴1（最新）
    SEQ_HISTORY_2 = 0x0102
    SEQ_HISTORY_3 = 0x0104
    SEQ_HISTORY_4 = 0x0106
    SEQ_HISTORY_5 = 0x0108
    SEQ_HISTORY_6 = 0x010A
    SEQ_HISTORY_7 = 0x010C
    SEQ_HISTORY_8 = 0x010E
    SEQ_HISTORY_9 = 0x0110
    SEQ_HISTORY_10 = 0x0112
    SEQ_HISTORY_11 = 0x0114
    SEQ_HISTORY_12 = 0x0116
    SEQ_HISTORY_13 = 0x0118
    SEQ_HISTORY_14 = 0x011A
    SEQ_HISTORY_15 = 0x011C
    SEQ_HISTORY_16 = 0x011E         # シーケンス履歴16（最古）

    # --- ハードウェア・通信統計 [7-9] ---
    LOOP_COUNT_BUFFER = 0x0126      # ループカウントバッファ
    MAIN_POWER_COUNT = 0x0140       # 主電源投入回数
    MAIN_POWER_TIME = 0x0142        # 主電源通電時間 [分]
    INVERTER_VOLTAGE = 0x0146       # インバータ電圧 (1=0.1V)
    MAIN_POWER_VOLTAGE = 0x0148     # 電源電圧 (1=0.1V)
    ROT_SW_STATUS = 0x014C          # モーター設定スイッチ(SW1)状態
    RS485_RECV_FRAME_COUNT = 0x0150 # RS-485受信フレームカウンタ
    BOOT_ELAPSED_TIME = 0x0152      # BOOTからの経過時間
    RS485_RECV_BYTE_COUNT = 0x0154  # RS-485受信Byteカウンタ
    RS485_SEND_BYTE_COUNT = 0x0156  # RS-485送信Byteカウンタ
    RS485_OK_RECV_ALL = 0x0158      # 正常受信フレームカウンタ（すべて）
    RS485_OK_RECV_SELF = 0x015A     # 正常受信フレームカウンタ（自局宛）
    RS485_ERR_RECV_ALL = 0x015C     # 異常受信フレームカウンタ（すべて）
    RS485_SEND_FRAME_COUNT = 0x015E # RS-485送信フレームカウンタ
    RS485_REG_WRITE_ERR = 0x0160    # RS-485レジスタ書込異常カウンタ

    # --- 内部I/Oステータス [9, 10] ---
    IO_STATUS_1 = 0x0170            # 内部I/Oステータス1
    IO_STATUS_2 = 0x0172
    IO_STATUS_3 = 0x0174
    IO_STATUS_4 = 0x0176
    IO_STATUS_5 = 0x0178
    IO_STATUS_6 = 0x017A
    IO_STATUS_7 = 0x017C
    IO_STATUS_8 = 0x017E

    # --- アラーム履歴詳細（展開時のみ有効） [10, 11] ---
    ALM_DETAIL_CODE = 0x0A00        # アラームコード
    ALM_DETAIL_SUB = 0x0A02         # サブコード
    ALM_DETAIL_TEMP = 0x0A04        # ドライバ温度
    ALM_DETAIL_INV_VOLT = 0x0A08    # インバータ電圧
    ALM_DETAIL_PHYS_IO = 0x0A0A     # 物理I/O入力
    ALM_DETAIL_RI_OUT = 0x0A0C      # R-I/O出力
    ALM_DETAIL_OP_INFO_0 = 0x0A0E   # 運転情報0
    ALM_DETAIL_OP_INFO_1 = 0x0A10   # 運転情報1
    ALM_DETAIL_CMD_POS = 0x0A12     # 指令位置
    ALM_DETAIL_BOOT_TIME = 0x0A14   # BOOTからの経過時間
    ALM_DETAIL_START_TIME = 0x0A16  # 運転開始からの経過時間
    ALM_DETAIL_POWER_TIME = 0x0A18  # 主電源通電時間

    # --- インフォメーション履歴 [11-13] ---
    INFO_HISTORY_1 = 0x0A20         # インフォメーション履歴1（最新）
    # ... (2～15省略不可のため全記述)
    INFO_HISTORY_2 = 0x0A22
    INFO_HISTORY_3 = 0x0A24
    INFO_HISTORY_4 = 0x0A26
    INFO_HISTORY_5 = 0x0A28
    INFO_HISTORY_6 = 0x0A2A
    INFO_HISTORY_7 = 0x0A2C
    INFO_HISTORY_8 = 0x0A2E
    INFO_HISTORY_9 = 0x0A30
    INFO_HISTORY_10 = 0x0A32
    INFO_HISTORY_11 = 0x0A34
    INFO_HISTORY_12 = 0x0A36
    INFO_HISTORY_13 = 0x0A38
    INFO_HISTORY_14 = 0x0A3A
    INFO_HISTORY_15 = 0x0A3C
    INFO_HISTORY_16 = 0x0A3E        # インフォメーション履歴16（最古）

    # --- インフォメーション発生時間履歴 [13, 14] ---
    INFO_TIME_1 = 0x0A40            # インフォメーション発生時間履歴1
    INFO_TIME_2 = 0x0A42
    INFO_TIME_3 = 0x0A44
    INFO_TIME_4 = 0x0A46
    INFO_TIME_5 = 0x0A48
    INFO_TIME_6 = 0x0A4A
    INFO_TIME_7 = 0x0A4C
    INFO_TIME_8 = 0x0A4E
    INFO_TIME_9 = 0x0A50
    INFO_TIME_10 = 0x0A52
    INFO_TIME_11 = 0x0A54
    INFO_TIME_12 = 0x0A56
    INFO_TIME_13 = 0x0A58
    INFO_TIME_14 = 0x0A5A
    INFO_TIME_15 = 0x0A5C
    INFO_TIME_16 = 0x0A5E

    # --- ラッチモニタ（運転停止時） [14, 15] ---
    LATCH_STATUS = 0x0BB0           # ラッチモニタ 状態
    LATCH_CMD_POS = 0x0BB2          # ラッチモニタ 指令位置
    LATCH_TARGET_POS = 0x0BB6       # ラッチモニタ 目標位置
    LATCH_DATA_NO = 0x0BB8          # ラッチモニタ 運転番号
    LATCH_LOOP_COUNT = 0x0BBA       # ラッチモニタ ループ回数

class BasicParameter(IntEnum):
    """
    CVDシリーズ RS-485通信タイプ (p3)基本設定パラメータ
    各アドレスは32bitデータの上位(High)レジスタアドレスです。
    """
    # --- ダイレクトデータ運転関連 ---
    DIRECT_DATA_ZERO_SPEED_ACTION = 0x0220  # ゼロ速度動作 (0:減速停止, 1:速度0指令)
    DIRECT_DATA_TRIGGER_INIT = 0x0222       # トリガ初期値 (-7～0)
    DIRECT_DATA_DEST_INIT = 0x0224          # 転送先初期値 (0:実行メモリ, 1:バッファメモリ)
    DIRECT_DATA_DATA_NO_INIT = 0x0226       # 運転初期値参照データNo. (0～255)

    # --- 電流・フィルタ関連 ---
    BASE_CURRENT = 0x024C                   # 基本電流 (0～1,000 / 1=0.1%)
    STOP_CURRENT = 0x0250                   # 停止電流 (0～500 / 1=0.1%)
    COMMAND_FILTER_SELECT = 0x0252          # 指令フィルタ選択 (1:LPF, 2:移動平均)
    COMMAND_FILTER_TIME_CONSTANT = 0x0254   # 指令フィルタ時定数 (0～200 ms)
    SMOOTH_DRIVE = 0x0258                   # スムースドライブ (0:無効, 1:有効)
    AUTO_CURRENT_DOWN_TIME = 0x0266         # オートカレントダウン判定時間 (0～1,000 ms)

    # --- 速度・加減速・座標関連 ---
    STARTING_SPEED = 0x0284                 # 起動速度 (0～4,000,000 Hz)
    ACC_DEC_UNIT = 0x028E                   # 加減速単位 (0:kHz/s, 1:s, 2:ms/kHz)
    ABS_POS_UNSETTLED_PERMIT = 0x0290       # 座標未確定時絶対位置決め運転許可 (0:不許可, 1:許可)

    # --- オーバートラベル・リミット関連 ---
    SOFTWARE_OVERTRAVEL = 0x0386            # ソフトウェアオーバートラベル (動作設定)
    SOFT_LIMIT_PLUS = 0x0388                # ＋ソフトウェアリミット (step)
    SOFT_LIMIT_MINUS = 0x038A               # －ソフトウェアリミット (step)
    PRESET_POSITION = 0x038C                # プリセット位置 (step)


class IORegister(IntEnum):
    """125ページ I/Oコマンド レジスタアドレス(上位)"""
    # 運転データNo.選択と入力指令をセットで送信するレジスタ群
    NET_SEL_DATA_2ND = 0x0072       # NET選択番号 + ドライバ入力指令(2nd)
    NET_SEL_DATA_AUTO_OFF = 0x0076  # NET選択番号 + ドライバ入力指令(自動OFF)
    NET_SEL_DATA_BASE = 0x007A      # NET選択番号 + ドライバ入力指令(基準)
    
    # 指令および状態取得の基本レジスタ
    DRIVER_INPUT_COMMAND = 0x007C   # ドライバ入力指令(基準) [3, 4]
    DRIVER_OUTPUT_STATUS = 0x007E   # ドライバ出力状態 [5, 6]

class InputSignal(IntFlag):
    OFF      = 0
    """ドライバ入力指令(下位:007Dh)のビット配置 [初期値]"""
    M0       = 1 << 0   # 運転データNo.選択 bit0
    M1       = 1 << 1   # 運転データNo.選択 bit1
    M2       = 1 << 2   # 運転データNo.選択 bit2
    START    = 1 << 3   # 位置決めSD運転開始
    HOME     = 1 << 4   # 原点復帰運転開始
    STOP     = 1 << 5   # 運転停止
    AWO      = 1 << 6   # 励磁切替(FREE)
    ALM_RST  = 1 << 7   # アラームリセット
    # R-IN8～10 は初期値「未使用」
    SSTART   = 1 << 11  # 位置決めSD運転開始(順送用)
    FW_JOG_P = 1 << 12  # FWD方向インチング
    RV_JOG_P = 1 << 13  # RVS方向インチング
    FW_POS   = 1 << 14  # FWD方向連続運転
    RV_POS   = 1 << 15  # RVS方向連続運転

class RemoteIOBit(IntFlag):
    """リモートI/Oビット位置 (ドライバ入力指令下位 007Dh での R-IN0～R-IN15 のビット配置)"""
    R_IN0  = 1 << 0
    R_IN1  = 1 << 1
    R_IN2  = 1 << 2
    R_IN3  = 1 << 3
    R_IN4  = 1 << 4
    R_IN5  = 1 << 5
    R_IN6  = 1 << 6
    R_IN7  = 1 << 7
    R_IN8  = 1 << 8   # 初期値: 未使用 (JOG運転用に使用可能)
    R_IN9  = 1 << 9   # 初期値: 未使用 (JOG運転用に使用可能)
    R_IN10 = 1 << 10  # 初期値: 未使用
    R_IN11 = 1 << 11
    R_IN12 = 1 << 12
    R_IN13 = 1 << 13
    R_IN14 = 1 << 14
    R_IN15 = 1 << 15

class OutputSignal(IntFlag):
    """ドライバ出力状態(下位:007Fh)のビット配置 [初期値]"""
    M0_R     = 1 << 0   # M0入力に対するレスポンス
    M1_R     = 1 << 1
    M2_R     = 1 << 2
    START_R  = 1 << 3
    HOME_END = 1 << 4   # 原点復帰完了
    READY    = 1 << 5   # 運転準備完了
    INFO     = 1 << 6   # インフォメーション発生中
    ALM_A    = 1 << 7   # アラーム発生中(A接点)
    SYS_BSY  = 1 << 8   # 内部処理中
    AREA0    = 1 << 9   # エリア出力0
    AREA1    = 1 << 10  # エリア出力1
    # Bit 11 は CONST-OFF (常時OFF)
    TIM      = 1 << 12  # タイミング信号
    MOVE     = 1 << 13  # モーター動作中
    # Bit 14, 15 は CONST-OFF


class RemoteIOParameter(IntEnum):
    """
    CVDシリーズ (p9) Remote-I/O機能選択パラメータ
    各リモートI/Oビットに割り付ける信号(割付No.)を設定するレジスタ（上位アドレス）
    """
    # --- 入力信号の割り付け (R-IN) ---
    R_IN0_FUNC = 0x1200   # 初期値: 64 (M0)
    R_IN1_FUNC = 0x1202   # 初期値: 65 (M1)
    R_IN2_FUNC = 0x1204   # 初期値: 66 (M2)
    R_IN3_FUNC = 0x1206   # 初期値: 32 (START)
    R_IN4_FUNC = 0x1208   # 初期値: 36 (HOME)
    R_IN5_FUNC = 0x120A   # 初期値:  5 (STOP)
    R_IN6_FUNC = 0x120C   # 初期値:  2 (AWO)
    R_IN7_FUNC = 0x120E   # 初期値:  8 (ALM-RST)
    R_IN8_FUNC = 0x1210   # 初期値:  0 (未使用)
    R_IN9_FUNC = 0x1212   # 初期値:  0 (未使用)
    R_IN10_FUNC = 0x1214  # 初期値:  0 (未使用)
    R_IN11_FUNC = 0x1216  # 初期値: 33 (SSTART)
    R_IN12_FUNC = 0x1218  # 初期値: 52 (FW-JOG-P)
    R_IN13_FUNC = 0x121A  # 初期値: 53 (RV-JOG-P)
    R_IN14_FUNC = 0x121C  # 初期値: 56 (FW-POS)
    R_IN15_FUNC = 0x121E  # 初期値: 57 (RV-POS)

    # --- 出力信号の割り付け (R-OUT) ---
    R_OUT0_FUNC = 0x1220  # 初期値: 64 (M0_R)
    R_OUT1_FUNC = 0x1222  # 初期値: 65 (M1_R)
    R_OUT2_FUNC = 0x1224  # 初期値: 66 (M2_R)
    R_OUT3_FUNC = 0x1226  # 初期値: 32 (START_R)
    R_OUT4_FUNC = 0x1228  # 初期値: 144 (HOME-END)
    R_OUT5_FUNC = 0x122A  # 初期値: 132 (READY)
    R_OUT6_FUNC = 0x122C  # 初期値: 135 (INFO)
    R_OUT7_FUNC = 0x122E  # 初期値: 129 (ALM-A)
    R_OUT8_FUNC = 0x1230  # 初期値: 136 (SYS-BSY)
    R_OUT9_FUNC = 0x1232  # 初期値: 160 (AREA0)
    R_OUT10_FUNC = 0x1234 # 初期値: 161 (AREA1)
    R_OUT11_FUNC = 0x1236 # 初期値: 128 (CONST-OFF)
    R_OUT12_FUNC = 0x1238 # 初期値: 157 (TIM)
    R_OUT13_FUNC = 0x123A # 初期値: 134 (MOVE)
    R_OUT14_FUNC = 0x123C # 初期値: 128 (CONST-OFF)
    R_OUT15_FUNC = 0x123E # 初期値: 128 (CONST-OFF)

    # --- 出力信号のOFF遅延時間 (R-OUT) ---
    # R-OUT0〜15それぞれのOFF出力遅延時間 [0〜250 ms]
    R_OUT0_OFF_DELAY = 0x1260
    # ... 中略 ...
    R_OUT15_OFF_DELAY = 0x127E

class InputAssignment(IntEnum):
    """(P61) 2-1 入力信号一覧：機能選択パラメータに書き込む割付No."""
    UNUSED = 0          # 未使用
    AWO = 2             # 励磁切替（無励磁にする）
    STOP = 5            # 運転停止
    ALM_RST = 8         # アラームリセット
    P_PRESET = 9        # 位置プリセット
    LAT_CLR = 13        # ラッチ状態解除
    INFO_CLR = 14       # インフォメーション解除
    HMI = 16            # 機能制限解除
    FW_BLK = 26         # 正転運転禁止
    RV_BLK = 27         # 逆転運転禁止
    FW_LS = 28          # 正転リミットセンサ
    RV_LS = 29          # 逆転リミットセンサ
    HOMES = 30          # 機械原点センサ
    SLIT = 31           # スリットセンサ
    START = 32          # 位置決めSD運転開始
    SSTART = 33         # 順送位置決めSD運転開始
    HOME = 36           # 原点復帰運転開始
    FW_JOG = 48         # 正転JOG運転
    RV_JOG = 49         # 逆転JOG運転
    FW_JOG_H = 50       # 正転高速JOG運転
    RV_JOG_H = 51       # 逆転高速JOG運転
    FW_JOG_P = 52       # 正転インチング運転
    RV_JOG_P = 53       # 逆転インチング運転
    FW_POS = 56         # 正転連続運転
    RV_POS = 57         # 逆転連続運転
    # 運転データNo.選択（M0～M7）
    M0 = 64; M1 = 65; M2 = 66; M3 = 67; M4 = 68; M5 = 69; M6 = 70; M7 = 71
    # 汎用信号（R0～R7）
    R0 = 80; R1 = 81; R2 = 82; R3 = 83; R4 = 84; R5 = 85; R6 = 86; R7 = 87

class OutputAssignment(IntEnum):
    """(P62) 2-2 出力信号一覧：機能選択パラメータに書き込む割付No."""
    UNUSED = 0          # 未使用
    # レスポンス出力 (入力信号に対する応答 割付No.2～87)
    AWO_R = 2; STOP_R = 5; ALM_RST_R = 8; HOME_R = 36; FW_JOG_R = 48
    # ...（中略：入力信号に対応する各レスポンス信号が定義されています）

    # ステータス出力
    CONST_OFF = 128     # 常時OFF
    ALM_A = 129         # アラーム（A接点）
    ALM_B = 130         # アラーム（B接点）
    SYS_RDY = 131       # システムレディ
    READY = 132         # 運転準備完了
    MOVE = 134          # モーター動作中
    INFO = 135          # インフォメーション発生中
    SYS_BSY = 136       # 内部処理中
    VA = 141            # 速度到達
    CRNT = 142          # モーター励磁中
    AUTO_CD = 143       # オートカレントダウン中
    HOME_END = 144      # 原点復帰完了
    ABSPEN = 145        # 座標確定
    PLS_OUT = 147       # パルス出力（1回転50回）
    FW_SLS = 153        # 正転ソフトウェアリミット到達
    RV_SLS = 154        # 逆転ソフトウェアリミット到達
    TIM = 157           # タイミング信号（7.2°回転ごと）
    AREA0 = 160         # エリア出力0
    AREA1 = 161         # エリア出力1
    SEQ_BSY = 198       # 位置決めSD運転中
    DELAY_BSY = 199     # 運転終了遅延中
    DCMD_RDY = 204      # ダイレクトデータ運転準備完了
    DCMD_FULL = 205     # ダイレクトデータ運転バッファフル

    # ドライバ状態・エラー関連インフォメーション
    INFO_DRVTMP = 226   # ドライバ温度：ドライバ内部温度が設定値を超えた [1, 2]
    INFO_OVOLT  = 228   # 過電圧：電源電圧が上限を超えた [1, 3]
    INFO_UVOLT  = 229   # 不足電圧：電源電圧が下限を下回った [1, 3]
    
    # 運転・操作関連インフォメーション
    INFO_START  = 233   # 運転起動失敗：条件を満たさない状態で運転を開始しようとした [1, 3]
    INFO_PR_REQ = 235   # プリセット要求中：絶対位置決め運転の前に位置プリセットが必要 [1, 3]
    INFO_MSET_E = 236   # モーター設定異常：モーター設定スイッチ(SW1)が正しくない [1, 3]
    INFO_NET_E  = 239   # RS-485通信異常：通信エラーが発生した [1, 4]
    
    # 禁止・制限関連インフォメーション
    INFO_FW_OT  = 240   # 正転方向運転禁止状態：FW-BLK入力がONになった [1, 5]
    INFO_RV_OT  = 241   # 逆転方向運転禁止状態：RV-BLK入力がONになった [1, 5]
    
    # 装置保守関連インフォメーション
    INFO_TRIP   = 244   # TRIPメーター：総回転量が設定値に達した [1, 6]
    INFO_ODO    = 245   # ODOメーター：積算回転量が設定値に達した [1, 6]
    
    # システム状態関連インフォメーション
    INFO_DSLMTD = 252   # 運転起動制限モード：機能制限中のため運転できない [1, 3]
    INFO_IOTEST = 253   # I/Oテストモード：MEXE02などでI/Oテスト中 [1, 3]
    INFO_CFG    = 254   # コンフィグ要求：パラメータ反映にConfigurationが必要 [1, 3]
    INFO_RBT    = 255   # 再起動要求：パラメータ反映に電源再投入が必要 [1, 3]

class SDDataOffset(IntEnum):
    """
    (P142) 運転データ設定項目のオフセット値 (上位アドレス用)
    各運転データNo.の基準アドレスにこの値を加算して使用します。
    """
    MODE        = 0x00  # 方式 (1:絶対 / 2:相対)
    POSITION    = 0x02  # 位置 [step]
    SPEED       = 0x04  # 速度 [Hz]
    ACCEL       = 0x06  # 起動・変速レート [1=0.001 kHz/s 等]
    DECEL       = 0x08  # 停止レート [1=0.001 kHz/s 等]
    CURRENT     = 0x0A  # 運転電流 [1=0.1 %]
    DELAY       = 0x0C  # 運転終了遅延 [1=0.001 s]
    LINK        = 0x0E  # 結合 (0:結合無 / 1:手動 / 2:自動 / 3:形状)
    LINK_DEST   = 0x10  # 結合先 (-1:次番号 / -256:停止 / 0-255:データNo)
    LOOP_COUNT  = 0x16  # カウント(Loop) (2-255回)
    LOOP_OFFSET = 0x18  # 位置オフセット(Loop) [step]
    LOOP_END    = 0x1A  # 終了(Loop) (0:無 / 1:L-End)


class OPMode(IntEnum):
    """(P28) 運転方式"""
    ABSOLUTE = 1  # 絶対位置決め
    RELATIVE = 2  # 相対位置決め

class SDLink(IntEnum):
    """(P29) 結合方法"""
    NONE       = 0  # 結合無
    MANUAL     = 1  # 手動順送
    AUTO       = 2  # 自動順送
    CONTINUOUS = 3  # 形状接続

