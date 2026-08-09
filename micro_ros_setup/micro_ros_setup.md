## 方向二：STM32 移植 micro-ROS（架构设计与验证）

### 目标
将 STM32F103 从被动执行器升级为 ROS2 网络中的原生节点，使其能直接订阅 ROS2 话题并发布状态信息，实现 PC + MCU 的异构分布式 ROS2 系统。

### 技术架构设计
- **通信层**：使用 UART 作为 micro-ROS 的传输层，STM32 通过串口与 PC 端 ROS2 节点交换数据。
- **实时操作系统**：基于 FreeRTOS 创建独立任务运行 micro-ROS 执行器，确保 10ms 控制周期不受通信阻塞。
- **节点设计**：STM32 订阅 `/cmd_dir` 话题（`std_msgs/msg/Int8`），根据收到的 ASCII 指令控制电机方向和 PWM 输出。

### 环境搭建
- 在 WSL Ubuntu 中成功编译了 `micro_ros_setup` 构建工具。
- 下载并配置了 FreeRTOS + STM32 HAL 的交叉编译工具链。
- 在 CubeIDE 中创建了 `04_micro_ros` 工程，启用了 FreeRTOS，并编写了完整的 `main.c` 代码（含 micro-ROS 订阅回调、电机方向控制逻辑）。

### 关键发现与失败原因
在 `create_firmware_ws.sh` 阶段发现 STM32F103C8T6 不在 micro-ROS 官方支持列表内。根本原因是：
- STM32F103 仅 20KB SRAM，无法满足 micro-ROS 运行时的内存需求（最低约 40KB）。
- micro-ROS 的 FreeRTOS 移植模板主要面向 STM32F4 系列（如 nucleo_f446re、olimex-stm32-e407）。

### 经验总结与后续方案
- **当前方案**：STM32 通过蓝牙接收单字符指令，虽非 ROS2 节点但实时性最佳，已稳定用于小车自主避障。
- **后续升级方案**：若需完整 micro-ROS 功能，可替换为 STM32F4 系列，直接使用官方 `nucleo_f446re` 模板即可完成移植。

### 产出
- `ros2/micro_ros_design/`：已编译的构建环境
- `04_micro_ros/`：含 FreeRTOS + micro-ROS 代码框架的 CubeIDE 工程
