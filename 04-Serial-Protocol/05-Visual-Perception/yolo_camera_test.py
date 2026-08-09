import cv2
from ultralytics import YOLO

# 加载 YOLOv8n 模型（第一次运行会自动下载，约 6MB）
print("正在加载 YOLO 模型...")
model = YOLO("yolov8s.pt")
print("模型加载完成！")

# 打开摄像头（0 表示电脑自带的或第一个 USB 摄像头）
cap = cv2.VideoCapture(0)
if not cap.isOpened():
    print("摄像头未识别！请检查是否插好。")
    exit()

print("按 Q 键退出程序。")



while True:
    ret, frame = cap.read()
    if not ret:
        print("画面读取失败")
        break

    # 备份原图（防止被模型修改）
    display_frame = frame.copy()

    # 关闭YOLO的自动绘图，防止它弹小窗
    results = model(frame, verbose=False)

    # 手动在原图上画检测框
    for result in results:
        if result.boxes is not None:
            for box in result.boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                conf = float(box.conf[0])
                cls = int(box.cls[0])
                label = f"{model.names[cls]} {conf:.2f}"

                # 画绿色矩形框
                cv2.rectangle(display_frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                # 写标签
                cv2.putText(display_frame, label, (x1, y1 - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

    # 显示画面
    cv2.imshow("YOLO 实时检测", display_frame)

    # 按 Q 键退出
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
print("程序已退出。")