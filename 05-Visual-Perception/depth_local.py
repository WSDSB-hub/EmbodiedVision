import cv2
import torch
import numpy as np

# ========== 1. 加载本地缓存的 MiDaS 模型 ==========
print("正在加载本地 MiDaS 模型（无需下载）...")

# 使用本地缓存的 repo
repo_path = r"C:\Users\wangk\.cache\torch\hub\intel-isl_MiDaS_master"

# 手动加载模型
model = torch.hub.load(repo_path, "MiDaS_small", source="local", trust_repo=True)
model.eval()

# 手动加载权重（已经在缓存里）
weights_path = r"C:\Users\wangk\.cache\torch\hub\checkpoints\midas_v21_small_256.pt"
state_dict = torch.load(weights_path, map_location="cpu")
model.load_state_dict(state_dict)

print("模型加载完成！")

# ========== 2. 拍照 ==========
print("正在拍照...")
cap = cv2.VideoCapture(0)
ret, img = cap.read()
cap.release()

if not ret:
    print("拍照失败！")
    exit()

cv2.imwrite("original.jpg", img)
print("已保存原图 original.jpg")

# ========== 3. 手动预处理（不使用有bug的transform）==========
print("正在计算深度图...")

# MiDaS_small 的输入尺寸是 256x256
input_size = 256

# 缩放并归一化
img_resized = cv2.resize(img, (input_size, input_size))
img_rgb = cv2.cvtColor(img_resized, cv2.COLOR_BGR2RGB) / 255.0

# 转为 tensor: [1, 3, 256, 256]
input_tensor = torch.from_numpy(img_rgb).permute(2, 0, 1).unsqueeze(0).float()

# ========== 4. 推理 ==========
with torch.no_grad():
    prediction = model(input_tensor)
    # 缩放到原始图像大小
    prediction = torch.nn.functional.interpolate(
        prediction.unsqueeze(1),
        size=img.shape[:2],
        mode="bicubic",
        align_corners=False
    ).squeeze()

# ========== 5. 转换为伪彩色深度图 ==========
depth = prediction.cpu().numpy()
depth = (depth - depth.min()) / (depth.max() - depth.min())
depth = (depth * 255).astype(np.uint8)
colored = cv2.applyColorMap(depth, cv2.COLORMAP_INFERNO)

cv2.imwrite("depth_result.jpg", colored)
print("深度图已保存为 depth_result.jpg（近处偏黄白，远处偏紫黑）")

# ========== 6. 显示 ==========
cv2.namedWindow("Depth Result", cv2.WINDOW_NORMAL)
cv2.resizeWindow("Depth Result", 800, 600)
cv2.imshow("Depth Result", colored)
print("按任意键关闭窗口...")
cv2.waitKey(0)
cv2.destroyAllWindows()
print("程序结束。")