import serial
import struct
import time
import threading
import sys

# ==================== 配置区（根据实际情况修改） ====================
SERIAL_PORT = 'COM10'  # 改成你设备管理器里 CH340 对应的 COM 号
BAUD_RATE = 115200
# ====================================================================

# 全局变量，用于键盘控制
running = True
left_speed = 0
right_speed = 0
cmd_lock = threading.Lock()

def send_command(ser, cmd, left, right):
    """
    发送控制指令
    cmd: 0x01前进, 0x02后退, 0x03左转, 0x04右转, 0x05停止
    left, right: 左右轮目标转速（RPM），int16，正数为正转，负数为反转
    """
    frame = bytearray([0xAA, cmd])           # 帧头 + 指令
    frame += struct.pack('>h', left)         # 左轮速度，大端字节序
    frame += struct.pack('>h', right)        # 右轮速度
    checksum = 0
    for b in frame:
        checksum ^= b
    frame.append(checksum)
    ser.write(frame)


def auto_test(ser):
    """自动测试：前进、停止、左转、停止"""
    print("=== 自动测试开始 ===")

    print("前进 2 秒")
    send_command(ser, 0x01, 100, 100)
    time.sleep(2)

    print("停止 1 秒")
    send_command(ser, 0x05, 0, 0)
    time.sleep(1)

    print("左转 2 秒")
    send_command(ser, 0x03, 80, 80)
    time.sleep(2)

    print("停止")
    send_command(ser, 0x05, 0, 0)

    print("=== 自动测试完成 ===")


def keyboard_listener():
    """键盘输入线程：读取按键，更新目标速度"""
    global left_speed, right_speed, running

    print("\n键盘控制说明：")
    print("  W / S : 前进 / 后退")
    print("  A / D : 左转 / 右转")
    print("  空格   : 停止")
    print("  Q     : 退出")
    print("  速度范围: 0 ~ 200 RPM\n")

    while running:
        try:
            key = input().lower().strip()
        except (EOFError, KeyboardInterrupt):
            running = False
            break

        with cmd_lock:
            if key == 'w':        # 前进
                left_speed = 150
                right_speed = 150
            elif key == 's':      # 后退
                left_speed = -150
                right_speed = -150
            elif key == 'a':      # 左转
                left_speed = -100
                right_speed = 100
            elif key == 'd':      # 右转
                left_speed = 100
                right_speed = -100
            elif key == ' ':      # 空格停止
                left_speed = 0
                right_speed = 0
            elif key == 'q':      # 退出
                left_speed = 0
                right_speed = 0
                running = False
            else:
                continue

            print(f"  目标速度: L={left_speed:4d}, R={right_speed:4d}")


def keyboard_control(ser):
    """键盘实时控制主循环"""
    global running, left_speed, right_speed

    # 启动键盘输入线程
    input_thread = threading.Thread(target=keyboard_listener, daemon=True)
    input_thread.start()

    last_left = 0
    last_right = 0

    try:
        while running:
            with cmd_lock:
                current_left = left_speed
                current_right = right_speed

            # 只在速度变化时发送指令
            if current_left != last_left or current_right != last_right:
                last_left = current_left
                last_right = current_right

                if current_left == 0 and current_right == 0:
                    send_command(ser, 0x05, 0, 0)
                elif current_left > 0 and current_right > 0:
                    send_command(ser, 0x01, current_left, current_right)
                elif current_left < 0 and current_right < 0:
                    send_command(ser, 0x02, -current_left, -current_right)
                elif current_left < 0 and current_right > 0:
                    send_command(ser, 0x03, -current_left, current_right)
                elif current_left > 0 and current_right < 0:
                    send_command(ser, 0x04, current_left, -current_right)
                else:
                    send_command(ser, 0x05, 0, 0)

            time.sleep(0.1)  # 10Hz 控制频率

    except KeyboardInterrupt:
        running = False

    # 退出前停止小车
    send_command(ser, 0x05, 0, 0)
    print("\n已停止，退出。")


# ==================== 主程序 ====================
if __name__ == '__main__':
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        print(f"串口 {SERIAL_PORT} 已打开\n")
        time.sleep(1)  # 等待 STM32 初始化完成
    except serial.SerialException as e:
        print(f"串口打开失败: {e}")
        print("请检查 COM 口号是否正确，以及是否被其他程序（如 SSCOM）占用。")
        sys.exit(1)

    # 选择模式
    print("请选择模式：")
    print("  1 - 自动测试")
    print("  2 - 键盘实时控制")
    choice = input("输入 1 或 2: ").strip()

    if choice == '1':
        auto_test(ser)
    elif choice == '2':
        keyboard_control(ser)
    else:
        print("无效选择，退出。")

    ser.close()
    print("串口已关闭。")