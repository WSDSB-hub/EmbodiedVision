import serial
import time

ser = serial.Serial('COM10', 115200, timeout=1)
print("串口已打开，输入命令 (w/s/a/d/空格/q):")

while True:
    cmd = input(">> ").strip()
    if cmd == 'q':
        break
    elif cmd in ('w', 's', 'a', 'd', ' '):
        ser.write(cmd.encode())
        print(f"已发送: {cmd}")
    else:
        print("无效命令")

ser.close()
print("结束")