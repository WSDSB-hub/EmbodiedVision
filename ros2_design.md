## 方向一：ROS2 节点化架构验证

### 目标
将原有的单文件视觉避障脚本重构为基于 ROS2 的模块化分布式系统，实现图像采集与感知推理两个独立节点的异步话题通信。验证 ROS2 框架在机器人系统中的可行性，并为后续 micro-ROS 移植奠定基础。

### 系统架构
本系统包含两个独立的 ROS2 节点，通过话题异步通信：

- 节点1：image_publisher（发布者节点）
  - 功能：生成测试图片，通过话题发布图像消息
  - 话题名称：/camera/image
  - 消息类型：sensor_msgs/Image
  - 发布频率：2Hz

- 节点2：image_subscriber（订阅者节点）
  - 功能：订阅图像话题，接收消息并验证传输完整性
  - 话题名称：/camera/image
  - 消息类型：sensor_msgs/Image

两个节点之间通过 ROS2 的话题（Topic）机制进行异步通信，发布者不关心订阅者是否存在，订阅者也不依赖发布者的实现细节，实现了完全的模块解耦。

### 节点设计

**发布者节点（image_publisher）**
- 文件路径：vision_pkg/vision_pkg/image_publisher.py
- 发布话题：/camera/image
- 发布频率：2Hz
- 核心实现：手动构建 Image 消息，避免依赖 cv_bridge（解决 NumPy 版本冲突）。消息包含以下字段：
  - height：480
  - width：640
  - encoding：bgr8
  - is_bigendian：0
  - step：width × 3
  - data：原始字节数组（uint8）

设计考量：使用测试图片（蓝色背景 + 红色方块）代替真实摄像头，因为 WSL 无法直接访问 Windows USB 摄像头。验证 ROS2 话题通信机制的核心目标与图像内容无关。手动构建消息比 cv_bridge 更底层，减少了环境依赖，且便于理解 ROS 消息结构。

**订阅者节点（image_subscriber）**
- 文件路径：vision_pkg/vision_pkg/image_subscriber.py
- 订阅话题：/camera/image
- 核心实现：在回调函数中接收图像消息，打印图像尺寸信息（例如：Received image: 640x480），验证消息传输的完整性和实时性。

### 通信流程
1. 在终端1启动发布者节点：ros2 run vision_pkg image_publisher
2. 在终端2启动订阅者节点：ros2 run vision_pkg image_subscriber
3. 发布者每隔 0.5 秒发布一张测试图像到 /camera/image 话题。
4. 订阅者接收到消息后，在终端打印 Received image: 640x480，证实通信正常。

### 验证方法
- 使用 ros2 topic list 命令，确认 /camera/image 话题存在。
- 使用 ros2 topic echo /camera/image 命令，直接查看话题中流动的消息内容。
- 观察订阅者终端是否持续打印接收日志。

### 关键问题与解决方案
在整个开发与验证过程中，遇到了以下几个主要问题：

1. cv_bridge 报错 KeyError: 16
   - 原因：NumPy 2.x 版本与 cv_bridge 不兼容，导致图像编码转换失败。
   - 解决方案：放弃使用 cv_bridge，改为手动构建 Image 消息。直接填充消息的 height、width、encoding、step 和 data 字段，绕过了版本冲突。
   - 技术启示：理解底层消息结构比依赖中间件更可靠，也减少了对特定库版本的依赖。

2. colcon build 编译失败：setup.py 语法错误
   - 原因：系统中的 setuptools 版本过高（84.0.0），与 colcon 的某些解析逻辑不兼容。
   - 解决方案：将 setuptools 降级到 59.6.0，并精简 setup.py 文件的内容，移除了可能导致警告的可选配置项。
   - 技术启示：ROS2 工具链对依赖版本有严格要求，环境配置是开发的第一步。

3. ros2 run 提示 Package not found
   - 原因：编译成功后会生成新的安装文件，但当前终端的环境变量并未更新，导致命令找不到包。
   - 解决方案：每次编译后，都需要执行 source install/setup.bash 命令来刷新环境变量。
   - 技术启示：ROS2 工作空间的环境管理属于基本操作，需要形成固定习惯。

4. Windows 原生 ROS2 安装失败
   - 原因：C 盘空间不足，且 Chocolatey 源无法找到对应的安装包。
   - 解决方案：放弃在 Windows 上直接安装，转而使用 WSL Ubuntu 环境进行 ROS2 开发。
   - 技术启示：开发环境的选择需要考虑实际资源限制，WSL 提供了很好的 Linux 兼容层。

5. git clone 超时
   - 原因：从 WSL 内部直接访问 GitHub 速度极慢，连接不稳定。
   - 解决方案：在 Windows 上使用浏览器手动下载代码压缩包，然后通过 /mnt/d/ 路径传入 WSL 中解压使用。
   - 技术启示：在网络受限的环境下，手动下载是稳定可靠的替代方案。

### 与模块化架构的对比
本项目的实物小车目前运行的是 Windows 上的多线程+队列模块化方案。两种方案在架构思想上完全一致，都实现了模块化、解耦和异步通信，仅通信层的实现方式不同。

- 多线程+队列方案（Windows）
  - 通信机制：使用 Python 标准库中的 queue.Queue（线程安全队列）。
  - 节点关系：各功能模块运行在独立的线程中，但共享同一个进程空间。
  - 扩展性：新增功能模块需要修改主程序，添加新的线程。
  - 标准化程度：属于自定义方案，不具备行业通用性。
  - 调试工具：需要自行编写日志输出。
  - 当前状态：已稳定运行在实物小车上，完成所有避障功能。

- ROS2 节点化方案（WSL）
  - 通信机制：使用 ROS2 原生的 Topic（话题发布/订阅）。
  - 节点关系：各节点完全独立，可以跨进程甚至跨机器通信。
  - 扩展性：新增节点可以即插即用，无需改动现有代码。
  - 标准化程度：基于 ROS2 官方框架，是机器人行业的通用标准。
  - 调试工具：拥有 ros2 topic list、echo、rqt_graph 等内置命令行和可视化工具。
  - 当前状态：已在 WSL 中完成架构验证，节点间通信正常。

### 后续迁移方案
当前阶段使用测试图片验证了 ROS2 的话题通信机制。未来向实物小车迁移时，只需要进行以下三步操作，业务逻辑代码完全无需修改：

1. 改造发布者节点：将生成测试图片的代码，替换为用 OpenCV 调用真实摄像头的代码。
2. 迁移部署环境：将 ROS2 节点从 WSL 迁移到小车上的嵌入式 Linux 板卡（例如树莓派）。
3. 增加控制节点：新建一个 control_node，订阅障碍物信息话题，做出避障决策后通过串口发送指令给 STM32。

整个迁移过程的核心变化只是通信层的替换，上层逻辑保持稳定。

### 环境配置
- 操作系统：WSL Ubuntu 22.04
- ROS2 版本：Humble
- 编译工具：colcon
- 关键依赖：rclpy、std_msgs、sensor_msgs

### 产出
- ros2/vision_pkg/：完整的 ROS2 功能包，包含发布者、订阅者以及所有启动配置文件。
- images/ros2_test.png：终端通信验证的截图，显示订阅者成功收到消息。
