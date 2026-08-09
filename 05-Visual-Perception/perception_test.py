import cv2
import torch
import numpy as np
from ultralytics import YOLO

# 1. 加载 YOLO 模型
print("加载 YOLO 模型...")
yolo_model = YOLO("yolov8n.pt")

# 2. 加载本地 MiDaS 模型
print("加载 MiDaS 深度估计模型...")
repo_path = r"C:\Users\wangk\.cache\torch\hub\intel-isl_MiDaS_master"
midas = torch.hub.load(repo_path, "MiDaS_small", source="local", trust_repo=True)
midas.eval()

weights_path = r"C:\Users\wangk\.cache\torch\hub\checkpoints\midas_v21_small_256.pt"
state_dict = torch.load(weights_path, map_location="cpu")
midas.load_state_dict(state_dict)
print("模型加载完成！")

# 3. 距离标定参数（需要你根据实际测试调整）
KNOWN_DEPTH_AT_1M = 150  # 1米远时，深度图上的平均像素值（需要实际测试校准）

cap = cv2.VideoCapture(0)
print("按 S 截图保存，按 Q 退出\n")

while True:
    ret, frame = cap.read()
    if not ret:
        break

    # --- MiDaS 深度估计（先算深度，YOLO框需要用到深度值）---
    h, w = frame.shape[:2]
    img_resized = cv2.resize(frame, (256, 256))
    img_rgb = cv2.cvtColor(img_resized, cv2.COLOR_BGR2RGB) / 255.0
    input_tensor = torch.from_numpy(img_rgb).permute(2, 0, 1).unsqueeze(0).float()

    with torch.no_grad():
        depth_pred = midas(input_tensor)
        depth_pred = torch.nn.functional.interpolate(
            depth_pred.unsqueeze(1), size=(h, w), mode="bicubic", align_corners=False
        ).squeeze()

    depth_np = depth_pred.cpu().numpy()

    # --- YOLO 检测 ---
    results = yolo_model(frame, verbose=False)

    # --- 标注检测框 + 距离 ---
    annotated = frame.copy()
    for r in results:
        for box in r.boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            cls = int(box.cls[0])
            conf = float(box.conf[0])

            # 提取检测框中心区域的深度平均值
            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
            # 取中心点周围 10×10 区域的平均深度值
            region = depth_np[max(0, cy-5):min(h, cy+5), max(0, cx-5):min(w, cx+5)]
            if region.size > 0:
                avg_depth = np.mean(region)
            else:
                avg_depth = 0

            # 深度值越大 = 越近（MiDaS 输出的是"逆深度"，大值=近）
            # 简单换算：用经验公式把深度像素值映射到米
            if avg_depth > 0:
                distance_m = KNOWN_DEPTH_AT_1M / (avg_depth + 1e-6)
            else:
                distance_m = 999.0

            # 标注
            label = f"{yolo_model.names[cls]} {conf:.2f} | {distance_m:.1f}m"
            cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(annotated, label, (x1, y1 - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

    # --- 深度图伪彩色 ---
    depth_display = depth_np.copy()
    depth_display = (depth_display - depth_display.min()) / (depth_display.max() - depth_display.min())
    depth_display = (depth_display * 255).astype(np.uint8)
    depth_colored = cv2.applyColorMap(depth_display, cv2.COLORMAP_INFERNO)

    # --- 并排显示 ---
    depth_resized = cv2.resize(depth_colored, (w, h))
    combined = np.hstack((annotated, depth_resized))

    cv2.imshow("Perception", combined)

    key = cv2.waitKey(1) & 0xFF
    if key == ord('q'):
        break
    elif key == ord('s'):
        cv2.imwrite("perception_result.jpg", combined)
        print("截图已保存为 perception_result.jpg")

cap.release()
cv2.destroyAllWindows()
print("程序结束。")