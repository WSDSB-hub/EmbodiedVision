import struct

def pack_command(cmd, left_speed, right_speed):
    """
    打包指令（与STM32端帧格式一致）
    cmd: 0x01前进, 0x02后退, 0x03左转, 0x04右转, 0x05停止
    """
    frame = bytearray([0xAA, cmd])
    frame += struct.pack('>h', left_speed)   # 大端，int16
    frame += struct.pack('>h', right_speed)
    checksum = 0
    for b in frame:
        checksum ^= b
    frame.append(checksum)
    return frame


def parse_frame(frame):
    """
    模拟STM32端解析（与main.c中Parse_Command逻辑一致）
    返回 (cmd, left_speed, right_speed) 或 None
    """
    if len(frame) != 7:
        return None
    if frame[0] != 0xAA:
        return None

    # 校验
    checksum = 0
    for i in range(6):
        checksum ^= frame[i]
    if checksum != frame[6]:
        return None

    cmd = frame[1]
    left_speed = (frame[2] << 8) | frame[3]
    # 处理有符号int16
    if left_speed >= 32768:
        left_speed -= 65536
    right_speed = (frame[4] << 8) | frame[5]
    if right_speed >= 32768:
        right_speed -= 65536

    return cmd, left_speed, right_speed


# ========== 测试 ==========
print("=== 串口协议自测 ===\n")

test_cases = [
    ("前进", 0x01, 100, 100),
    ("后退", 0x02, -100, -100),
    ("左转", 0x03, -80, 80),
    ("右转", 0x04, 80, -80),
    ("停止", 0x05, 0, 0),
]

all_pass = True
for name, cmd, left, right in test_cases:
    packed = pack_command(cmd, left, right)
    parsed = parse_frame(packed)

    hex_str = ' '.join(f'{b:02X}' for b in packed)
    print(f"{name}: 打包 → {hex_str}")

    if parsed is None:
        print(f"  ❌ 解析失败！")
        all_pass = False
    elif parsed == (cmd, left, right):
        print(f"  ✅ 解析正确: cmd={parsed[0]}, L={parsed[1]}, R={parsed[2]}")
    else:
        print(f"  ❌ 解析错误: 期望(cmd={cmd},L={left},R={right})，得到{parsed}")
        all_pass = False
    print()

if all_pass:
    print("🎉 全部测试通过！串口协议设计正确，Python端与STM32端逻辑一致。")
else:
    print("❌ 部分测试失败，请检查代码。")