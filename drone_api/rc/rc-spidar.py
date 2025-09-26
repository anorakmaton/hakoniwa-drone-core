#!/usr/bin/python
# -*- coding: utf-8 -*-

import sys
import libs.hakosim as hakosim
from hakoniwa_pdu.pdu_msgs.hako_msgs.pdu_pytype_GameControllerOperation import GameControllerOperation
import time
import os
import argparse
import ctypes
import math
from return_to_home import DroneController
from rc_utils.rc_utils import RcConfig, StickMonitor
import libs.hakosim_types as hakosim_types

# --- SPIDAR関連の定義 ---
DLL_PATH = "C:/Users/e20317naga/hakoniwa/hakoniwa-drone-core/Spidar/Spidar.dll"
SERIAL_NUMBER = 230922017
MODEL_ID = 0

class Vector3(ctypes.Structure):
    _fields_ = [("x", ctypes.c_float), ("y", ctypes.c_float), ("z", ctypes.c_float)]
class Quaternion(ctypes.Structure):
    _fields_ = [("x", ctypes.c_float), ("y", ctypes.c_float), ("z", ctypes.c_float), ("w", ctypes.c_float)]

try:
    if sys.platform == 'win32':
        dll_dir = os.path.dirname(os.path.abspath(DLL_PATH))
        os.add_dll_directory(dll_dir)
    spidar_dll = ctypes.WinDLL(DLL_PATH)
except (OSError, FileNotFoundError):
    print(f"❌ SPIDAR DLL '{DLL_PATH}' のロードに失敗しました。"); sys.exit(1)
try:
    spidar_dll.SpidarInitialize.argtypes = [ctypes.c_uint, ctypes.c_int]; spidar_dll.SpidarInitialize.restype = ctypes.c_bool
    spidar_dll.SpidarStart.argtypes = [ctypes.c_uint]; spidar_dll.SpidarStart.restype = ctypes.c_bool
    spidar_dll.SpidarStop.argtypes = [ctypes.c_uint]; spidar_dll.SpidarStop.restype = ctypes.c_bool
    spidar_dll.SpidarTerminate.argtypes = [ctypes.c_uint]; spidar_dll.SpidarTerminate.restype = ctypes.c_bool
    spidar_dll.SpidarCalibrate.argtypes = [ctypes.c_uint]; spidar_dll.SpidarCalibrate.restype = ctypes.c_bool
    spidar_dll.SpidarGetPose.argtypes = [ctypes.c_uint, ctypes.POINTER(Vector3), ctypes.POINTER(Quaternion), ctypes.POINTER(Vector3), ctypes.POINTER(Vector3)]; spidar_dll.SpidarGetPose.restype = ctypes.c_bool
    spidar_dll.SpidarSetForce.argtypes = [ctypes.c_uint, ctypes.POINTER(Vector3), ctypes.c_float, ctypes.c_float, ctypes.POINTER(Vector3), ctypes.c_float, ctypes.c_float, ctypes.c_bool, ctypes.c_bool]; spidar_dll.SpidarSetForce.restype = ctypes.c_bool
    spidar_dll.SpidarSetHaptics.argtypes = [ctypes.c_uint, ctypes.c_bool]; spidar_dll.SpidarSetHaptics.restype = ctypes.c_bool
    spidar_dll.SpidarGetGpioValue.argtypes = [ctypes.c_uint, ctypes.POINTER(ctypes.c_uint)]; spidar_dll.SpidarGetGpioValue.restype = ctypes.c_bool
except AttributeError:
    print("❌ SPIDAR DLLの関数プロトタイプ設定に失敗しました。"); sys.exit(1)

def spidar_quaternion_to_yaw(q: Quaternion):
    sinp = 2 * (q.w * q.y - q.z * q.x)
    if abs(sinp) >= 1:
        return ctypes.c_float(math.copysign(math.pi / 2, sinp))
    return ctypes.c_float(math.asin(sinp))

def spidar_quaternion_to_pitch(q: Quaternion):
    siny_cosp = 2 * (q.w * q.z + q.x * q.y)
    cosy_cosp = 1 - 2 * (q.y * q.y + q.z * q.z)
    return ctypes.c_float(math.atan2(siny_cosp, cosy_cosp))

def spidar_quaternion_to_roll(q: Quaternion):
    sinr_cosp = 2 * (q.w * q.x + q.y * q.z)
    cosr_cosp = 1 - 2 * (q.x * q.x + q.y * q.y)
    return ctypes.c_float(math.atan2(sinr_cosp, cosr_cosp))

def spidar_quaternion_to_euler(q: Quaternion):
    # roll (x-axis rotation)
    sinr_cosp = 2 * (q.w * q.x + q.y * q.z)
    cosr_cosp = 1 - 2 * (q.x * q.x + q.y * q.y)
    roll = math.atan2(sinr_cosp, cosr_cosp)

    # pitch (y-axis rotation)
    sinp = 2 * (q.w * q.y - q.z * q.x)
    if abs(sinp) >= 1:
        pitch = math.copysign(math.pi / 2, sinp)
    else:
        pitch = math.asin(sinp)

    # yaw (z-axis rotation)
    siny_cosp = 2 * (q.w * q.z + q.x * q.y)
    cosy_cosp = 1 - 2 * (q.y * q.y + q.z * q.z)
    yaw = math.atan2(siny_cosp, cosy_cosp)

    return roll, pitch, yaw

def apply_deadzone(value, deadzone_threshold=0.1):
    """
    デッドゾーンを適用する関数
    Args:
        value: 入力値
        deadzone_threshold: デッドゾーンの閾値（絶対値）
    Returns:
        デッドゾーンを適用した値
    """
    if abs(value) < deadzone_threshold:
        return 0.0
    else:
        # デッドゾーン外の値を0-1の範囲に正規化
        sign = 1 if value > 0 else -1
        normalized = (abs(value) - deadzone_threshold) / (1.0 - deadzone_threshold)
        return sign * normalized

# -----------------------------------------------------------------
# 修正部分
# -----------------------------------------------------------------

def spidar_control(client: hakosim.MultirotorClient, stick_monitor: StickMonitor):
    serial_number = ctypes.c_uint(SERIAL_NUMBER)
    
    try:
        if not spidar_dll.SpidarInitialize(serial_number, ctypes.c_int(MODEL_ID)):
            print("❌ SpidarInitializeに失敗。"); return
        print(f"✅ SPIDAR初期化成功 (S/N: {serial_number.value})")

        spidar_dll.SpidarStart(serial_number)
        input("👉 グリップを中心に置いてEnterでキャリブレーション...")
        spidar_dll.SpidarCalibrate(serial_number)
        spidar_dll.SpidarSetHaptics(serial_number, True)
        print("✅ SPIDAR制御開始。")
        
        initial_gpio_value = ctypes.c_uint(0)
        spidar_dll.SpidarGetGpioValue(serial_number, ctypes.byref(initial_gpio_value))
        previous_gpio_value = initial_gpio_value.value
        while True:
            client.run_nowait()
            position = Vector3()
            rotation = Quaternion()
            spidar_dll.SpidarGetPose(serial_number, ctypes.byref(position), ctypes.byref(rotation), ctypes.byref(Vector3()), ctypes.byref(Vector3()))
            drone_pose: hakosim_types.Pose = client.simGetVehiclePose()
            #print(f"Drone Position: x={drone_pose.position.x_val}, y={drone_pose.position.y_val}, z={drone_pose.position.z_val}")
            drone_roll, drone_pitch, drone_yaw = hakosim_types.Quaternionr.quaternion_to_euler(drone_pose.orientation)
            #print(f"Drone Orientation: roll={math.degrees(drone_roll):.2f}, pitch={math.degrees(drone_pitch):.2f}, yaw={math.degrees(drone_yaw):.2f}")
            data: GameControllerOperation = client.getGameJoystickData()
            data.axis = [0.0] * 6
                
            data.button = list(data.button)
            
            current_gpio_value = ctypes.c_uint(0)
            if spidar_dll.SpidarGetGpioValue(serial_number, ctypes.byref(current_gpio_value)):
                if current_gpio_value.value != previous_gpio_value:
                    for i in range(8):
                        # デフォルト1（未押下）→0（押下）でTrue
                        is_pressed_now = not bool(current_gpio_value.value & (1 << i))
                        was_pressed_before = not bool(previous_gpio_value & (1 << i))
                        
                        if is_pressed_now != was_pressed_before:
                            event_op_index = stick_monitor.rc_config.get_event_op_index(i)
                            if event_op_index is not None:
                                print(f"is_pressed_now: {is_pressed_now} event_op_index: {event_op_index}")
                                event_triggered = stick_monitor.switch_event(i, is_pressed_now)
                                data.button[event_op_index] = event_triggered
                                
                            # if i == 3 and is_pressed_now:
                            #     print(f"\n✨ Button 3 PRESSED! -> Recalibrating SPIDAR...")
                            #     spidar_dll.SpidarCalibrate(serial_number)

                    previous_gpio_value = current_gpio_value.value
            
            # 選択肢1: 位置ベースの制御
            raw_yaw = spidar_quaternion_to_yaw(rotation).value
            processed_yaw = apply_deadzone(raw_yaw)
            data.axis[0] = processed_yaw * -2.0
            data.axis[1] = position.y * 5.0
            data.axis[2] = position.x * 1.0
            data.axis[3] = position.z * 1.0

            # 選択肢2: 姿勢ベースの制御
            # data.axis[0] = quaternion_to_yaw(rotation).value * 2.0    # ヨー（SPIDARの回転）
            # data.axis[1] = quaternion_to_pitch(rotation).value * 3.0  # ピッチ（SPIDARの前後傾斜）
            # data.axis[2] = quaternion_to_roll(rotation).value * 3.0   # ロール（SPIDARの左右傾斜）
            # data.axis[3] = position.z * 1.0
            client.putGameJoystickData(data)
            # デバッグ用：全ての角度を表示
            #_, _, yaw = spidar_quaternion_to_euler(rotation)
            # pitch = spidar_quaternion_to_pitch(rotation).value
            # roll = spidar_quaternion_to_roll(rotation).value
            # print(f"\rYaw: {yaw:.3f}, Pitch: {pitch:.3f}, Roll: {roll:.3f} | "f"Pos X: {position.x:.3f}, Y: {position.y:.3f}, Z: {position.z:.3f}", end="")
            #print(f"\rRaw Yaw: {raw_yaw:.3f} -> Processed: {processed_yaw:.3f} | ", end="")
            #print(f"data.axis: [0]: {data.axis[0]:.3f}, [1]: {data.axis[1]:.3f}, [2]: {data.axis[2]:.3f}, [3]: {data.axis[3]:.3f}", end="")
            #print(f"Drone yaw: {drone_yaw:.2f} | SPIDAR yaw: {yaw:.2f}")
            spring_force = Vector3(-position.x * 30.0, -position.y * 30.0, -position.z * 30.0)
            spidar_dll.SpidarSetForce(serial_number, ctypes.byref(spring_force), 1.0, 0.1, ctypes.byref(Vector3()), 0.0, 0.0, True, False)

            time.sleep(0.01)
    except KeyboardInterrupt:
        print("\n🛑 操縦を中断します...")
    finally:
        print("🔴 SPIDARを終了処理中...")
        spidar_dll.SpidarSetHaptics(serial_number, False)
        spidar_dll.SpidarStop(serial_number)
        spidar_dll.SpidarTerminate(serial_number)
        print("✅ SPIDARを終了しました。")

def main():
    # (main関数は変更なし)
    parser = argparse.ArgumentParser(description="Drone RC with SPIDAR")
    parser.add_argument("config_path", help="Path to the hakoniwa custom.json file")
    parser.add_argument("rc_config_path", help="Path to the SPIDAR RC config file")
    parser.add_argument("--name", type=str, help="Optional name for the drone")
    args = parser.parse_args()

    if not os.path.exists(args.config_path):
        print(f"ERROR: Config file not found at '{args.config_path}'"); return 1
    if not os.path.exists(args.rc_config_path):
        print(f"ERROR: RC Config file not found at '{args.rc_config_path}'"); return 1
    
    rc_config = RcConfig(args.rc_config_path)
    stick_monitor = StickMonitor(rc_config)

    client = hakosim.MultirotorClient(args.config_path)
    client.default_drone_name = args.name if args.name else "Drone"
    client.confirmConnection()
    client.enableApiControl(True)
    client.armDisarm(True)
    print("✅ Drone armed.")
    
    # DroneControllerは元のコードでは直接使われていなかったため、ここでは一旦コメントアウト
    # drone_controller = DroneController(client) 
    
    spidar_control(client, stick_monitor)
    return 0

if __name__ == "__main__":
    sys.exit(main())