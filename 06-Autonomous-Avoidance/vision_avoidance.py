import cv2
import torch
import numpy as np
from ultralytics import YOLO
import serial
import time

# ==================== 配置区 ====================
SERIAL_PORT = 'COM9'          # CH340的COM口号
BAUD_RATE = 115200
SAFE_DISTANCE = 0.5            # 安全距离（米），小于此距离触发避障
KNOWN_DEPTH_AT_1M = 150        # 1米参考深度值
# ===============================================

print("加载模型中...")
yolo_model = YOLO("yolov8n.pt")
repo_path = r"C:\Users\wangk\.cache\torch\hub\intel-isl_MiDaS_master"
midas = torch.hub.load(repo_path, "MiDaS_small", source="local", trust_repo=True)
midas.eval()
weights_path = r"C:\Users\wangk\.cache\torch\hub\checkpoints\midas_v21_small_256.pt"
midas.load_state_dict(torch.load(weights_path, map_location="cpu"))
print("模型加载完成！")

# 打开串口
ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
print(f"串口 {SERIAL_PORT} 已打开")
time.sleep(2)  # 等STM32初始化

cap = cv2.VideoCapture(0)
print("开始自主避障！按 Q 退出\n")

while True:
    ret, frame = cap.read()
    if not ret:
        break

    h, w = frame.shape[:2]

    # ---- 深度估计 ----
    img_resized = cv2.resize(frame, (256, 256))
    img_rgb = cv2.cvtColor(img_resized, cv2.COLOR_BGR2RGB) / 255.0
    input_tensor = torch.from_numpy(img_rgb).permute(2, 0, 1).unsqueeze(0).float()

    with torch.no_grad():
        depth_pred = midas(input_tensor)
        depth_pred = torch.nn.functional.interpolate(
            depth_pred.unsqueeze(1), size=(h, w), mode="bicubic", align_corners=False
        ).squeeze()
    depth_np = depth_pred.cpu().numpy()

    # ---- YOLO检测 ----
    results = yolo_model(frame, verbose=False)
    obstacles = []
    annotated = frame.copy()

    for r in results:
        for box in r.boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            cls = int(box.cls[0])
            conf = float(box.conf[0])
            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
            region = depth_np[max(0, cy-5):min(h, cy+5), max(0, cx-5):min(w, cx+5)]
            avg_depth = np.mean(region) if region.size > 0 else 0
            distance_m = KNOWN_DEPTH_AT_1M / (avg_depth + 1e-6) if avg_depth > 0 else 999.0

            obstacles.append({'cls': yolo_model.names[cls], 'conf': conf,
                              'distance_m': distance_m, 'cx': cx, 'x1': x1, 'x2': x2})

            label = f"{yolo_model.names[cls]} {conf:.2f} | {distance_m:.1f}m"
            cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(annotated, label, (x1, y1 - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

    # ---- 避障决策 + 发送串口指令 ----
    if len(obstacles) == 0:
        action = "FORWARD"
        ser.write(b'w')          # 前进
    else:
        closest = min(obstacles, key=lambda o: o['distance_m'])
        if closest['distance_m'] < SAFE_DISTANCE:
            if closest['cx'] < w * 0.4:
                action = "TURN RIGHT"
                ser.write(b'd')  # 右转
            elif closest['cx'] > w * 0.6:
                action = "TURN LEFT"
                ser.write(b'a')  # 左转
            else:
                action = "BACKWARD"
                ser.write(b's')  # 后退
        else:
            action = "FORWARD"
            ser.write(b'w')      # 前进

    # ---- 显示 ----
    cv2.rectangle(annotated, (10, 10), (400, 60), (0, 0, 0), -1)
    cv2.putText(annotated, f"Action: {action}", (20, 45),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)

    depth_display = (depth_np - depth_np.min()) / (depth_np.max() - depth_np.min())
    depth_display = (depth_display * 255).astype(np.uint8)
    depth_colored = cv2.applyColorMap(depth_display, cv2.COLORMAP_INFERNO)
    combined = np.hstack((annotated, depth_colored))

    cv2.imshow("Vision Avoidance", combined)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# 退出前停止小车
ser.write(b' ')
ser.close()
cap.release()
cv2.destroyAllWindows()
print("程序结束，小车已停止。")
