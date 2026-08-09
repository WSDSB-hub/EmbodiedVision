## 方向一：ROS2 节点化架构验证

### 目标
将原有的单文件视觉避障脚本重构为基于 ROS2 的模块化分布式系统，实现图像采集、感知推理和运动控制三个独立节点的异步话题通信。验证 ROS2 框架在机器人系统中的可行性，并为后续 micro-ROS 移植奠定基础。

### 技术架构
┌─────────────────┐ /camera/image ┌─────────────────┐
│ image_publisher │ ──────────────────→ │ image_subscriber │
│ (发布者节点) │ │ (订阅者节点) │
│ │ │ │
│ 生成测试图片 │ │ 接收并验证图像 │
│ 发布到话题 │ │ 打印接收日志 │
└─────────────────┘ └─────────────────┘

- **节点 1（image_publisher）**：以 2Hz 频率生成测试图片（蓝色背景 + 红色方块），通过 `/camera/image` 话题发布 `sensor_msgs/Image` 消息。
- **节点 2（image_subscriber）**：订阅 `/camera/image` 话题，接收图像消息并打印验证信息。

### 运行环境
- **操作系统**：WSL Ubuntu 22.04
- **ROS2 版本**：Humble
- **依赖包**：`rclpy`、`std_msgs`、`sensor_msgs`

### 节点设计

#### 发布者节点（image_publisher）
- **包路径**：`vision_pkg/vision_pkg/image_publisher.py`
- **话题**：`/camera/image`（sensor_msgs/Image）
- **频率**：2Hz
- **关键实现**：手动构建 `Image` 消息，避免依赖 `cv_bridge`（解决 NumPy 版本冲突）。消息包含图像的宽度、高度、编码格式（bgr8）和原始字节数据。
- **设计考量**：使用测试图片代替真实摄像头，原因有二：
  1. WSL 无法直接访问 Windows USB 摄像头。
  2. 验证 ROS2 节点通信的核心目标是话题发布/订阅机制，而非图像内容。

#### 订阅者节点（image_subscriber）
- **包路径**：`vision_pkg/vision_pkg/image_subscriber.py`
- **话题**：`/camera/image`（sensor_msgs/Image）
- **关键实现**：在回调函数中接收图像消息，打印图像的宽度和高度，验证消息传输的完整性。

### 通信验证
在两个独立终端中分别启动发布者和订阅者节点，通过 `ros2 topic list` 确认 `/camera/image` 话题存在，通过终端输出确认订阅者成功接收图像消息。

### 关键问题与解决

| 问题 | 原因 | 解决方案 |
|:---|:---|:---|
| `cv_bridge` 报 KeyError: 16 | NumPy 2.x 与 cv_bridge 版本不兼容 | 手动构建 Image 消息，绕过 cv_bridge |
| `colcon build` 失败：`setup.py` 语法错误 | `setuptools` 版本过高 | 降级 `setuptools` 到 59.6.0 并精简 `setup.py` |
| `ros2 run` 找不到包 | 编译后未加载环境变量 | 执行 `source install/setup.bash` |
| Windows 原生 ROS2 安装失败 | C 盘空间不足、网络不稳定 | 改用 WSL Ubuntu 环境 |

### 后续迁移方案
当前使用测试图片验证了 ROS2 话题通信机制。迁移到真实小车时，仅需：
1. 将发布者节点中的测试图片生成代码替换为 `cv2.VideoCapture(0)` 实时采集。
2. 将部署环境从 WSL 迁移到小车上的嵌入式 Linux 板卡（如树莓派）。
3. 业务逻辑代码无需任何改动。

### 与模块化架构的对比

| 维度 | 多线程+队列（Windows） | ROS2 节点化（WSL） |
|:---|:---|:---|
| **通信机制** | `queue.Queue` | ROS2 话题 |
| **节点解耦** | 线程独立，共享进程空间 | 节点独立，可跨进程/跨机器 |
| **可扩展性** | 新增线程需修改主程序 | 新增节点即插即用 |
| **工业标准** | 自定义方案 | ROS2 官方框架 |
| **当前适用场景** | 实物小车实时避障 | 架构验证与未来部署 |

两种方案在架构思想上完全一致（模块化、解耦、异步通信），仅通信层实现不同。多线程版本已稳定运行于实物小车，ROS2 版本已验证架构可行性，未来可平滑迁移。

### 产出
- `ros2/vision_pkg/`：完整的 ROS2 功能包（含发布者、订阅者、启动配置）
- `images/ros2_test.png`：终端通信验证截图
