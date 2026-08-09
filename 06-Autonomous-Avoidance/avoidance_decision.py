import cv2
import torch
import numpy as np
from ultralytics import YOLO

# ==================== 参数配置 ====================
SAFE_DISTANCE = 0.5          # 安全距离（米），小于此距离触发避障
KNOWN_DEPTH_AT_1M = 150      # 1米参考深度值（需要根据你的环境微调）
FRAME_WIDTH = 640            # 画面宽度
# =================================================

print("加载模型中...")
# YOLO
yolo_model = YOLO("yolov8n.pt")

# MiDaS（本地缓存）
repo_path = r"C:\Users\wangk\.cache\torch\hub\intel-isl_MiDaS_master"
midas = torch.hub.load(repo_path, "MiDaS_small", source="local", trust_repo=True)
midas.eval()
weights_path = r"C:\Users\wangk\.cache\torch\hub\checkpoints\midas_v21_small_256.pt"
state_dict = torch.load(weights_path, map_location="cpu")
midas.load_state_dict(state_dict)
print("模型加载完成！")

cap = cv2.VideoCapture(0)
print("按 S 截图保存，按 Q 退出\n")

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

    # ---- YOLO 检测 ----
    results = yolo_model(frame, verbose=False)

    # ---- 避障决策 ----
    obstacles = []   # 存储所有检测到的障碍物信息
    annotated = frame.copy()

    for r in results:
        for box in r.boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            cls = int(box.cls[0])
            conf = float(box.conf[0])

            # 计算障碍物中心区域的深度
            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
            region = depth_np[max(0, cy-5):min(h, cy+5), max(0, cx-5):min(w, cx+5)]
            avg_depth = np.mean(region) if region.size > 0 else 0
            distance_m = KNOWN_DEPTH_AT_1M / (avg_depth + 1e-6) if avg_depth > 0 else 999.0

            obstacles.append({
                'cls': yolo_model.names[cls],
                'conf': conf,
                'distance_m': distance_m,
                'cx': cx, 'x1': x1, 'x2': x2
            })

            # 标注障碍物
            label = f"{yolo_model.names[cls]} {conf:.2f} | {distance_m:.1f}m"
            cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(annotated, label, (x1, y1 - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

    # ---- 生成决策 ----
    if len(obstacles) == 0:
        action = "FORWARD (前进)"
        action_color = (0, 255, 0)   # 绿色
    else:
        # 找到最近的障碍物
        closest = min(obstacles, key=lambda o: o['distance_m'])

        if closest['distance_m'] < SAFE_DISTANCE:
            # 判断障碍物在画面中的位置
            if closest['cx'] < w * 0.4:
                action = "TURN RIGHT (右转)"
                action_color = (0, 165, 255)   # 橙色
            elif closest['cx'] > w * 0.6:
                action = "TURN LEFT (左转)"
                action_color = (0, 165, 255)
            else:
                action = "BACKWARD (后退)"
                action_color = (0, 0, 255)     # 红色
        else:
            action = "FORWARD (前进)"
            action_color = (0, 255, 0)

    # ---- 显示决策结果 ----
    cv2.rectangle(annotated, (10, 10), (500, 60), (0, 0, 0), -1)
    cv2.putText(annotated, f"Decision: {action}", (20, 45),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, action_color, 2)

    # 如果有障碍物，显示最近障碍物信息
    if len(obstacles) > 0:
        closest = min(obstacles, key=lambda o: o['distance_m'])
        info = f"Closest: {closest['cls']} at {closest['distance_m']:.1f}m"
        cv2.putText(annotated, info, (20, 75),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

    # ---- 深度图伪彩色 ----
    depth_display = depth_np.copy()
    depth_display = (depth_display - depth_display.min()) / (depth_display.max() - depth_display.min())
    depth_display = (depth_display * 255).astype(np.uint8)
    depth_colored = cv2.applyColorMap(depth_display, cv2.COLORMAP_INFERNO)

    # ---- 并排显示 ----
    depth_resized = cv2.resize(depth_colored, (w, h))
    combined = np.hstack((annotated, depth_resized))

    cv2.imshow("Obstacle Avoidance", combined)

    key = cv2.waitKey(1) & 0xFF
    if key == ord('q'):
        break
    elif key == ord('s'):
        cv2.imwrite("avoidance_result.jpg", combined)
        print("截图已保存为 avoidance_result.jpg")

cap.release()
cv2.destroyAllWindows()
print("程序结束。")