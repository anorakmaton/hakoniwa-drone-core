import ctypes
import os
import time
import sys
import math

# --- 1. 設定項目 ---
DLL_PATH = "C:/Users/e20317naga/hakoniwa/hakoniwa-drone-core/Spidar/Spidar.dll"
SERIAL_NUMBER = 230922017
MODEL_ID = 0

# --- 2. データ構造の定義 ---
class Vector3(ctypes.Structure):
    _fields_ = [("x", ctypes.c_float), ("y", ctypes.c_float), ("z", ctypes.c_float)]

class Quaternion(ctypes.Structure):
    _fields_ = [("x", ctypes.c_float), ("y", ctypes.c_float), ("z", ctypes.c_float), ("w", ctypes.c_float)]

def quaternion_to_yaw(q: Quaternion):
    siny_cosp = 2 * (q.w * q.z + q.x * q.y)
    cosy_cosp = 1 - 2 * (q.y * q.y + q.z * q.z)
    return ctypes.c_float(math.atan2(siny_cosp, cosy_cosp))

# --- 3. Spidar.dllのロードと関数プロトタイプの設定 ---
try:
    if sys.platform == 'win32':
        dll_dir = os.path.dirname(os.path.abspath(DLL_PATH))
        os.add_dll_directory(dll_dir)
    spidar_dll = ctypes.WinDLL(DLL_PATH)
    print(f"✅ DLL '{DLL_PATH}' のロードに成功しました。")
except (OSError, FileNotFoundError) as e:
    print(f"❌ DLL '{DLL_PATH}' のロードに失敗しました。\n   エラー詳細: {e}")
    sys.exit(1)

try:
    # --- 関数プロトタイプの定義 ---
    spidar_dll.SpidarInitialize.argtypes = [ctypes.c_uint, ctypes.c_int]
    spidar_dll.SpidarInitialize.restype = ctypes.c_bool
    spidar_dll.SpidarStart.argtypes = [ctypes.c_uint]
    spidar_dll.SpidarStart.restype = ctypes.c_bool
    spidar_dll.SpidarStop.argtypes = [ctypes.c_uint]
    spidar_dll.SpidarStop.restype = ctypes.c_bool
    spidar_dll.SpidarTerminate.argtypes = [ctypes.c_uint]
    spidar_dll.SpidarTerminate.restype = ctypes.c_bool
    spidar_dll.SpidarCalibrate.argtypes = [ctypes.c_uint]
    spidar_dll.SpidarCalibrate.restype = ctypes.c_bool
    spidar_dll.SpidarGetPose.argtypes = [ctypes.c_uint, ctypes.POINTER(Vector3), ctypes.POINTER(Quaternion), ctypes.POINTER(Vector3), ctypes.POINTER(Vector3)]
    spidar_dll.SpidarGetPose.restype = ctypes.c_bool
    spidar_dll.SpidarSetForce.argtypes = [ctypes.c_uint, ctypes.POINTER(Vector3), ctypes.c_float, ctypes.c_float, ctypes.POINTER(Vector3), ctypes.c_float, ctypes.c_float, ctypes.c_bool, ctypes.c_bool]
    spidar_dll.SpidarSetForce.restype = ctypes.c_bool
    spidar_dll.SpidarSetHaptics.argtypes = [ctypes.c_uint, ctypes.c_bool]
    spidar_dll.SpidarSetHaptics.restype = ctypes.c_bool
    
    # ★★ GPIO値取得関数のプロトタイプを追加 ★★
    spidar_dll.SpidarGetGpioValue.argtypes = [ctypes.c_uint, ctypes.POINTER(ctypes.c_uint)]
    spidar_dll.SpidarGetGpioValue.restype = ctypes.c_bool
    
    print("✅ DLL関数のプロトタイプ設定が完了しました。")
except AttributeError as e:
    print(f"❌ DLL関数のプロトタイプ設定に失敗しました。\n   関数が見つからないか、DLLが正しくロードされていません: {e}")
    sys.exit(1)

# --- 4. メイン処理 ---
def main():
    """SPIDARを制御するメイン関数"""
    serial_number_to_use = ctypes.c_uint(SERIAL_NUMBER)

    print("-" * 50)
    print(f"SPIDAR (S/N: {SERIAL_NUMBER}, Model: {MODEL_ID}) の初期化を開始します...")
    
    if not spidar_dll.SpidarInitialize(serial_number_to_use, ctypes.c_int(MODEL_ID)):
        print("❌ SpidarInitializeに失敗しました。")
        return

    print(f"✅ 初期化成功！")

    if not spidar_dll.SpidarStart(serial_number_to_use):
        print("❌ SpidarStartに失敗しました。")
        spidar_dll.SpidarTerminate(serial_number_to_use)
        return
        
    print("✅ SPIDARのメインループを開始しました。")
    input("👉 グリップを中心に置いてEnterでキャリブレーション...")
    spidar_dll.SpidarCalibrate(serial_number_to_use)
    print("✅ キャリブレーション完了。")
    spidar_dll.SpidarSetHaptics(serial_number_to_use, True)
    print("✅ 力覚フィードバック有効。")
    print("-" * 50)

    # ★★ ボタンの状態を記憶するための変数を初期化 ★★
    previous_gpio_value = 0

    try:
        print("🔄 メインループ開始 (Ctrl+Cで終了)")
        while True:
            # --- 姿勢取得 (既存の処理) ---
            position = Vector3()
            rotation = Quaternion()
            spidar_dll.SpidarGetPose(serial_number_to_use, ctypes.byref(position), ctypes.byref(rotation), ctypes.byref(Vector3()), ctypes.byref(Vector3()))

            print(f"\rPosition: X={position.x: .3f}, Y={position.y: .3f}, Z={position.z: .3f}, Yaw={quaternion_to_yaw(rotation).value:.3f}", end="")

            # --- 力覚フィードバック (既存の処理) ---
            spring_force = Vector3(-position.x * 60.0, -position.y * 60.0, -position.z * 60.0)
            torque = Vector3(0, 0, 0)
            spidar_dll.SpidarSetForce(serial_number_to_use, ctypes.byref(spring_force), 1.0, 0.1, ctypes.byref(torque), 0.0, 0.0, True, False)
            
            # --- ★★ GPIO (ボタン) 入力処理 ★★ ---
            current_gpio_value = ctypes.c_uint(0)
            if spidar_dll.SpidarGetGpioValue(serial_number_to_use, ctypes.byref(current_gpio_value)):
                # 値が変化した瞬間にのみチェック
                if current_gpio_value.value != previous_gpio_value:
                    # 最初の8ボタン（ビット0から7）をチェック
                    for i in range(8):
                        button_mask = 1 << i  # i番目のビットに対応するマスクを作成 (例: 1, 2, 4, 8...)
                        
                        # 現在ON かつ 以前はOFF の場合 = 押された瞬間
                        if (current_gpio_value.value & button_mask) and not (previous_gpio_value & button_mask):
                            print(f"\n✨ Button {i} PRESSED!")
                        
                        # 現在OFF かつ 以前はON の場合 = 離された瞬間
                        # elif not (current_gpio_value.value & button_mask) and (previous_gpio_value & button_mask):
                        #     print(f"\nReleased Button {i}")

                    # 現在の状態を保存
                    previous_gpio_value = current_gpio_value.value

            time.sleep(0.01)

    except KeyboardInterrupt:
        print("\n\nプログラムを終了します...")
    finally:
        # --- 終了処理 ---
        print("🔴 力覚フィードバックを無効化...")
        spidar_dll.SpidarSetHaptics(serial_number_to_use, False)
        
        print("🔴 SPIDARのメインループを停止...")
        spidar_dll.SpidarStop(serial_number_to_use)

        print("🔴 SPIDARの終了処理...")
        spidar_dll.SpidarTerminate(serial_number_to_use)
        
        print("✅ 正常に終了しました。")

if __name__ == "__main__":
    main()