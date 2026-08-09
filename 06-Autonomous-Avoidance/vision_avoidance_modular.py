import cv2
import torch
import numpy as np
from ultralytics import YOLO
import serial
import time
import threading
from queue import Queue, Empty

# ==================== 配置区 ====================
SERIAL_PORT = 'COM11'          # 蓝牙串口 COM 号
BAUD_RATE = 115200
SAFE_DISTANCE = 0.5            # 安全距离（米）
KNOWN_DEPTH_AT_1M = 150        # 1米参考深度值
FRAME_WIDTH = 640
# ===============================================

# 两个线程安全队列，模拟 ROS2 话题
image_queue = Queue(maxsize=2)       # 模拟 /camera/image 话题
obstacle_queue = Queue(maxsize=10)   # 模拟 /obstacles 话题

# ==================== 线程1：摄像头采集 ====================
def camera_thread():
    """模拟 camera_node：采集图像，发布到 image_queue"""
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("[Camera] 摄像头未识别！")
        return

    print("[Camera] 摄像头节点已启动")
    while True:
        ret, frame = cap.read()
        if not ret:
            continue
        # 清空旧帧，只保留最新一帧
        while not image_queue.empty():
            try:
                image_queue.get_nowait()
            except Empty:
                break
        image_queue.put(frame)
        time.sleep(0.05)  # 约 20fps

# ==================== 线程2：视觉感知 ====================
def perception_thread():
    """模拟 perception_node：订阅 image_queue，YOLO+深度，发布到 obstacle_queue"""
    print("[Perception] 加载模型中...")
    yolo_model = YOLO("yolov8n.pt")
    repo_path = r"C:\Users\wangk\.cache\torch\hub\intel-isl_MiDaS_master"
    midas = torch.hub.load(repo_path, "MiDaS_small", source="local", trust_repo=True)
    midas.eval()
    weights_path = r"C:\Users\wangk\.cache\torch\hub\checkpoints\midas_v21_small_256.pt"
    midas.load_state_dict(torch.load(weights_path, map_location="cpu"))
    print("[Perception] 感知节点已启动")

    while True:
        try:
            frame = image_queue.get(timeout=1)
        except Empty:
            continue

        h, w = frame.shape[:2]

        # 深度估计
        img_resized = cv2.resize(frame, (256, 256))
        img_rgb = cv2.cvtColor(img_resized, cv2.COLOR_BGR2RGB) / 255.0
        input_tensor = torch.from_numpy(img_rgb).permute(2, 0, 1).unsqueeze(0).float()
        with torch.no_grad():
            depth_pred = midas(input_tensor)
            depth_pred = torch.nn.functional.interpolate(
                depth_pred.unsqueeze(1), size=(h, w), mode="bicubic", align_corners=False
            ).squeeze()
        depth_np = depth_pred.cpu().numpy()

        # YOLO 检测
        results = yolo_model(frame, verbose=False)
        obstacles = []
        for r in results:
            for box in r.boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                cls = int(box.cls[0])
                conf = float(box.conf[0])
                cx = (x1 + x2) // 2
                cy = (y1 + y2) // 2
                region = depth_np[max(0, cy-5):min(h, cy+5), max(0, cx-5):min(w, cx+5)]
                avg_depth = np.mean(region) if region.size > 0 else 0
                distance_m = KNOWN_DEPTH_AT_1M / (avg_depth + 1e-6) if avg_depth > 0 else 999.0
                obstacles.append({
                    'cls': yolo_model.names[cls],
                    'conf': conf,
                    'distance_m': distance_m,
                    'cx': cx,
                    'x1': x1, 'x2': x2
                })

        # 清空旧障碍物信息，只保留最新
        while not obstacle_queue.empty():
            try:
                obstacle_queue.get_nowait()
            except Empty:
                break
        obstacle_queue.put((frame, depth_np, obstacles))

# ==================== 线程3：避障决策与控制 ====================
def control_thread():
    """模拟 control_node：订阅 obstacle_queue，做避障决策，串口发送"""
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        print(f"[Control] 串口 {SERIAL_PORT} 已打开")
    except Exception as e:
        print(f"[Control] 串口打开失败: {e}")
        return

    time.sleep(2)  # 等待 STM32 初始化
    print("[Control] 控制节点已启动")

    while True:
        try:
            frame, depth_np, obstacles = obstacle_queue.get(timeout=1)
        except Empty:
            continue

        h, w = frame.shape[:2]
        annotated = frame.copy()

        # 标注障碍物
        for obs in obstacles:
            label = f"{obs['cls']} {obs['conf']:.2f} | {obs['distance_m']:.1f}m"
            cv2.rectangle(annotated, (obs['x1'], 0), (obs['x2'], 0), (0, 255, 0), 2)
            cv2.putText(annotated, label, (obs['x1'], 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

        # 避障决策
        if len(obstacles) == 0:
            action = "FORWARD"
            ser.write(b'w')
        else:
            closest = min(obstacles, key=lambda o: o['distance_m'])
            if closest['distance_m'] < SAFE_DISTANCE:
                if closest['cx'] < w * 0.4:
                    action = "TURN RIGHT"
                    ser.write(b'd')
                elif closest['cx'] > w * 0.6:
                    action = "TURN LEFT"
                    ser.write(b'a')
                else:
                    action = "BACKWARD"
                    ser.write(b's')
            else:
                action = "FORWARD"
                ser.write(b'w')

        # 显示
        cv2.rectangle(annotated, (10, 10), (300, 60), (0, 0, 0), -1)
        cv2.putText(annotated, f"Action: {action}", (20, 45),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)

        depth_display = (depth_np - depth_np.min()) / (depth_np.max() - depth_np.min())
        depth_display = (depth_display * 255).astype(np.uint8)
        depth_colored = cv2.applyColorMap(depth_display, cv2.COLORMAP_INFERNO)
        combined = np.hstack((annotated, depth_colored))

        cv2.imshow("Vision Avoidance (Modular)", combined)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    ser.write(b' ')
    ser.close()
    cv2.destroyAllWindows()

# ==================== 主程序 ====================
if __name__ == '__main__':
    t1 = threading.Thread(target=camera_thread, daemon=True)
    t2 = threading.Thread(target=perception_thread, daemon=True)
    t3 = threading.Thread(target=control_thread, daemon=True)

    t1.start()
    t2.start()
    t3.start()

    # 主线程等待控制线程结束（按 Q 退出）
    t3.join()
    print("程序结束。")