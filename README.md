# VisionBot — A Self-Built Visual Obstacle Avoidance Robot

## Project Overview

I built this robot to answer a question that has bothered me since I started learning about embodied intelligence: what does it actually take to close the perception-decision-action loop on a real physical system? Papers and simulation environments make it look clean — a neural network outputs an action, a robot executes it, done. But when you're the one who has to make the motor spin at exactly the right speed, and the camera has to see a transparent water bottle, and the serial port refuses to work in one direction for no apparent reason, you realize that the gap between a simulated agent and a real robot is where most of the engineering actually lives.

This project is my attempt to cross that gap. The robot uses a USB camera to watch the road ahead. YOLOv8 detects obstacles and MiDaS estimates their depth. A rule-based state machine decides whether to go forward, turn, or back up. The decision is sent over Bluetooth to an STM32F103C8T6 microcontroller, which runs a 100 Hz PID speed controller on two DC motors. The entire system runs on a 12V LiPo battery, completely untethered.

Along the way, I burned a motor driver, fried an MCU, fought an encoder that refused to cooperate, discovered that monocular depth estimation is blind to transparent objects, and learned that sometimes the best engineering decision is to stop debugging a serial port and switch to Bluetooth. This README documents what I built, why I built it, and — most importantly — what went wrong and what I learned from each failure.

---

## System Architecture

The system uses a heterogeneous computing architecture. The laptop handles all AI inference — YOLO object detection and MiDaS depth estimation — because these models require computational resources far beyond what a microcontroller can provide. The STM32 handles real-time motor control — reading encoder pulses, computing PID output, and updating PWM duty cycles at a strict 100 Hz interval — because this task requires deterministic timing that a general-purpose OS cannot guarantee.

The two processors communicate over Bluetooth. The laptop sends single ASCII characters (`'w'`, `'a'`, `'d'`, `'s'`, space) that the STM32 parses as motion commands. This simple protocol keeps the firmware minimal and reliable.

<img src="System Architecture.drawio.png"/>



---

## Hardware Platform

| Component | Model/Specification | Role |
|:---|:---|:---|
| MCU | STM32F103C8T6 (JiangKeDa) | Real-time motor control, 72 MHz Cortex-M3 |
| Motor Driver | TB6612FNG | Dual H-bridge, VM rated ≥15V |
| Motors ×2 | MG513P28 | 12V DC geared, Hall encoder, 13 PPR, 1:28 gear ratio |
| Camera | USB 1080P plug-and-play | Visual perception input, fixed focus |
| Battery | 3S LiPo 12V 2200mAh | Onboard power, with balance charger |
| Step-Down | LM2596 DC-DC | 12V → 5V for MCU and Bluetooth |
| Bluetooth ×2 | HC-05 with baseboard | Master-slave paired, wireless serial |
| Protection | 50V 100μF electrolytic capacitor | Absorbs motor back-EMF voltage spikes |
| Protection | 1kΩ resistors ×6 | In series with control signal lines, limits fault current to GPIO |

The hardware design includes two protective measures that were added after early failures. A 100μF electrolytic capacitor is connected in parallel across the motor power rail (`VIN+` to `VIN-`) to absorb the back-EMF voltage spikes generated when motors start, brake, or are manually turned. Without this capacitor, the instantaneous voltage can exceed the TB6612's internal MOSFET breakdown voltage. Six 1kΩ resistors are placed in series with the control signal lines (`PA0→PWMA`, `PA2→AIN1`, `PA3→AIN2`, `PA1→PWMB`, `PA4→BIN1`, `PA5→BIN2`). If the TB6612 fails internally and allows 12V to backfeed through these lines, the resistors limit the current to approximately 12mA — well within the STM32 GPIO's survival range.

<img src="hardware setup(1).png"/>

---

## Embedded Motor Control System

### Encoder Interface

The motors use Hall-effect quadrature encoders producing 13 pulses per revolution. Each encoder outputs two signals — A-phase and B-phase — which are offset by 90 degrees. The relative phase between the two signals indicates rotation direction: A leading B means forward, B leading A means reverse.

TIM3 is configured in Encoder Mode for the left motor, reading A-phase on PA6 and B-phase on PA7. TIM4 is configured identically for the right motor on PB6 and PB7. Both timers are set to TI1+TI2 mode, which counts on every edge of both channels — this gives 4× decoding, so the effective resolution is:

*[Place formula image here: Pulses per revolution = 13 (PPR) × 4 (4× decoding) × 28 (gear ratio) = 1456]*

### Speed Measurement

A 10ms periodic interrupt from TIM1 triggers the control loop. In each iteration, the current encoder counter value is read using `__HAL_TIM_GET_COUNTER()`. The pulse delta from the previous reading is computed:

*[Place formula image here: Delta = counter_now - counter_last]*

The delta is then converted to RPM:

*[Place formula image here: RPM = (Delta × 6000) / 1456]*

The factor 6000 comes from: 100 (to scale from 10ms to 1 second) × 60 (to scale from seconds to minutes).

A software outlier filter is applied: if `|Δ| > 100` in any 10ms period, the delta is set to zero. This filters out electromagnetic interference spikes that would otherwise produce physically impossible RPM readings (observed up to 14,000 RPM during testing).

### PID Controller Implementation

The PID controller is implemented as a positional (not incremental) algorithm, written from scratch in C without using any pre-built library. The PID structure holds the three gains, the target value, error history, integral accumulator, and output limits.

The control law is:

*[Place formula image here: u(t) = u0 + Kp*e(t) + Ki*∫e(t)dt + Kd*de(t)/dt]*

Discretized for the 10ms control period:

*[Place formula image here: u[k] = u0 + Kp*e[k] + Ki*∑e[i] + Kd*(e[k] - e[k-1])]*

Where `u₀ = 275` is the feed-forward base duty cycle (27.5%), determined experimentally as the approximate steady-state duty needed to maintain 100 RPM under no load.

Integral anti-windup is implemented by clamping the integral term between `-100` and `+500`. Without this, if the motor stalls (e.g., someone grabs the wheel), the integral term would accumulate indefinitely, causing a violent surge when the obstruction is removed. Output limiting constrains the final PWM value between `0` and `900` (the valid range for the TIM2 compare register with `ARR=999`).

### PID Tuning Process and Final Parameters

The parameters were tuned manually using real-time RPM visualization through the serial port. The tuning procedure followed the classic Ziegler-Nichols-inspired approach: start with `Ki=0`, `Kd=0`, increase `Kp` until sustained oscillation appears at the critical gain, then set `Kp` to approximately 60% of the critical value. Introduce `Ki` incrementally to eliminate steady-state error. Introduce `Kd` last to suppress overshoot.

| Parameter | Value | Role |
|:---|:---|:---|
| `Kp` | 2.5 | Proportional gain — responds to instantaneous error |
| `Ki` | 0.2 | Integral gain — eliminates steady-state error |
| `Kd` | 0.1 | Derivative gain — suppresses overshoot, adds damping |
| Base Duty `u₀` | 275 | Feed-forward term (~27.5% PWM) |
| PWM Frequency | 1 kHz | `Prescaler=71`, `Counter Period=999` |
| Control Period | 10 ms | TIM1 interrupt, 100 Hz control loop |

### PID Performance

| Metric | Value |
|:---|:---|
| Target RPM | 100 |
| Steady-State RPM | 90–98 |
| Steady-State Error | <10% |
| RPM Fluctuation | ±5 RPM |
| Disturbance Recovery Time | <1 second |
| Recovery Behavior | Returns to steady-state within 1s after manual wheel grab |

<img src="pid serial data.png"/>

---

## Vision-Based Perception System

### Object Detection: YOLOv8n

YOLOv8n (nano variant, ~6.2MB) is used for real-time object detection. It recognizes 80 common indoor object classes from the COCO dataset. Running on a laptop CPU, inference speed is 20–30 FPS — sufficient for the robot's walking-speed navigation.

The model outputs bounding boxes with class labels and confidence scores. Detection results are drawn onto the camera frame using OpenCV's `rectangle()` and `putText()` functions. To avoid a secondary popup window created by YOLO's internal `plot()` method, the bounding boxes are rendered manually by iterating over `result.boxes`.

### Monocular Depth Estimation: MiDaS_small

MiDaS_small is used for monocular depth estimation — inferring relative depth from a single RGB image. The model was chosen over alternatives (DPT, Depth-Anything-V2) after encountering compatibility issues with those libraries.

The official `transforms` preprocessing pipeline was bypassed because it returned a 5-dimensional tensor (`[1, 1, 3, H, W]`) that MiDaS could not process, producing the error `Expected 3D or 4D input to conv2d, but got input of size [1, 1, 3, 129, 257]`. A manual preprocessing pipeline was implemented instead:

1. Resize the frame to 256×256 pixels.
2. Convert BGR to RGB and normalize to [0, 1].
3. Convert to a PyTorch tensor and permute dimensions to `[C, H, W]`.
4. Add batch dimension to get `[1, 3, 256, 256]`.

The model outputs a relative depth map, which is resized back to the original frame dimensions using bicubic interpolation, normalized, and color-mapped with OpenCV's `COLORMAP_INFERNO` for visualization.

### Perception Fusion and Distance Estimation

For each YOLO detection box, the average depth value is computed from a 10×10 pixel region centered on the bounding box. This average depth value is converted to an approximate metric distance using a hand-calibrated scaling constant:

*[Place formula image here: Distance (m) ≈ 150 / (average_depth_value + ε)]*

The constant `150` was determined by placing an object at a known 1-meter distance and recording the average depth value in that region. This is a rough approximation — MiDaS outputs relative (inverse) depth, not absolute metric depth — but it is sufficient for the robot's obstacle avoidance logic, which only needs to know "is something close or far?"

Each detection box is annotated with: class name, confidence score, and estimated distance in meters.

*[Place YOLO detection result here. Show the camera frame with bounding boxes, class labels, confidence scores, and distance annotations. Ideally, include a scene with multiple objects at different distances — e.g., a chair at 1.5m, a backpack at 1.2m, a person at 2.0m.]*

---

## Autonomous Decision and Robot Integration

### Avoidance Strategy

The avoidance logic is a rule-based state machine that operates on the fused perception output:

1. If no obstacles are detected → command `FORWARD` (`'w'`).
2. Find the closest obstacle by minimum estimated distance.
3. If the closest distance is less than the safety threshold (0.5 meters):
   - Obstacle in the left 40% of the frame → command `TURN RIGHT` (`'d'`).
   - Obstacle in the right 40% of the frame → command `TURN LEFT` (`'a'`).
   - Obstacle in the center 20% → command `BACKWARD` (`'s'`).
4. If the closest distance exceeds the threshold → command `FORWARD` (`'w'`).

This simple strategy is effective for static obstacle environments. It fails in dynamic scenarios (moving obstacles) and cluttered spaces (multiple obstacles at different distances in different directions) — limitations that motivate the reinforcement learning exploration in Direction 3.

### Wireless Communication

The laptop-to-STM32 communication uses Bluetooth (HC-05 modules in master-slave paired configuration). This choice was made after the wired serial link (CH340 USB-TTL) failed in one direction: the STM32 could transmit data to the PC (TX direction), but could never receive data from the PC (RX direction). Extensive debugging — swapping TX/RX lines, replacing CH340 modules, testing on different computers — could not resolve the issue. The root cause was likely a driver-level or hardware-level fault in the CH340's RX channel.

The Bluetooth solution not only solved the communication problem but also eliminated the USB tether, making the robot fully wireless. The STM32 firmware uses polling-based UART reception (checking the `RXNE` flag in USART1's status register in each main loop iteration) to read incoming ASCII characters. A switch-case block maps characters to motor commands.

### Power System

The robot carries its own power: a 3S LiPo battery (12V nominal, ~12.6V fully charged). The 12V rail directly powers the TB6612 motor driver's `VIN` pin. An LM2596 step-down module converts 12V to 5V for the STM32 core board and Bluetooth module. All ground lines (battery negative, step-down output negative, STM32 GND, TB6612 GND, Bluetooth GND) are tied together on a breadboard.

During development, the STM32 was powered via ST-Link's 3.3V pin. For standalone operation, the ST-Link is disconnected and the step-down module supplies 5V directly to the core board's 5V pin. The TB6612's `STBY` pin is tied to 5V (high = enable).

*[Place system integration photo here. Show the fully assembled robot with all modules mounted on the chassis, battery strapped on, Bluetooth module visible, and camera mounted at the front.]*

---

## ROS2 and Robotic Software Architecture

### Direction 1: ROS2 Node-Based Architecture

The original avoidance script was a single monolithic Python file containing all logic — camera capture, YOLO inference, depth estimation, decision-making, and serial transmission — in one `while` loop. This is fine for prototyping but does not demonstrate the modular, distributed design expected in modern robotics software.

The code was refactored into a multi-threaded architecture with three independent threads communicating through `queue.Queue` (Python's thread-safe queue):

1. **Camera Thread** — captures frames and puts them into `image_queue`. Runs at ~20 FPS, keeps only the most recent frame to avoid queue buildup.
2. **Perception Thread** — gets frames from `image_queue`, runs YOLO and MiDaS, puts obstacle data into `obstacle_queue`.
3. **Control Thread** — gets obstacle data from `obstacle_queue`, makes avoidance decisions, sends serial commands.

This architecture mirrors ROS2's node-and-topic design. Each thread is an independent module with a single responsibility. The queues decouple the modules: the camera thread doesn't know or care whether anyone is reading its images; the perception thread doesn't know who will consume its obstacle data.

To validate the ROS2 architecture concept, a complete ROS2 package `vision_pkg` was created in WSL Ubuntu with ROS2 Humble. The package contains:

- **`image_publisher` node**: publishes test images (blue background + red square) to the `/camera/image` topic at 2 Hz.
- **`image_subscriber` node**: subscribes to `/camera/image` and logs received image dimensions.

The `Image` message was constructed manually (filling `height`, `width`, `encoding`, `step`, and `data` fields) to avoid dependency on `cv_bridge`, which had a version conflict with NumPy 2.x (`KeyError: 16`). The nodes were compiled with `colcon build` and verified to communicate correctly.

Several environment issues were resolved during this process: `setuptools` was downgraded from 84.0.0 to 59.6.0 to fix a `colcon build` parsing error; the `cv_bridge` dependency was entirely bypassed; Windows-native ROS2 installation was abandoned due to C drive space constraints and Chocolatey package unavailability, and WSL Ubuntu was used instead.

### Direction 2: micro-ROS on STM32 — Architecture Design

The goal was to make the STM32 a native ROS2 node — subscribing to velocity topics and publishing odometry — using micro-ROS, the embedded version of ROS2 designed for microcontrollers.

The micro-ROS build environment was successfully set up. The `micro_ros_setup` tool was cloned (via manual browser download to bypass WSL Git timeout issues), compiled with `colcon`, and used to initialize a FreeRTOS-based firmware workspace. A CubeIDE project was created with FreeRTOS enabled, and the micro-ROS integration code was written — including a subscriber callback that maps ROS2 `std_msgs/msg/Int8` messages to motor direction and PWM commands.

However, at the `create_firmware_ws.sh` stage, it was discovered that `stm32f103c8t6` is not in the list of officially supported platforms. The root cause is hardware resource limitation: the STM32F103C8T6 has only 20KB of SRAM, while micro-ROS requires a minimum of approximately 40KB for the FreeRTOS task, the micro-ROS executor, and the DDS-XRCE transport layer.

The architecture design, build environment setup, CubeIDE project framework, and integration code are all documented and preserved in the repository under `ros2/micro_ros_design/` and `docs/micro_ros_design.md`. Upgrading to an STM32F4 series (e.g., STM32F407VET6) would make deployment straightforward using the officially supported `nucleo_f446re` template.

---

## Deep Reinforcement Learning Exploration

### Direction 3: PPO-Based Obstacle Avoidance in PyBullet

The rule-based avoidance strategy works for simple static environments but has obvious limitations: it cannot handle multiple simultaneous obstacles, it makes binary left/right decisions rather than smooth trajectories, and the safety threshold is a manually tuned parameter with no theoretical justification.

To explore whether a learning-based approach could produce better behavior, a custom Gymnasium environment was built in the PyBullet physics simulator. The environment models a simple differential-drive robot that must navigate past obstacles to reach a goal zone.

**State Space**: A 3-dimensional vector representing forward distance sensor readings, with values normalized to [0, 10] meters.

**Action Space**: Three discrete actions — 0: go forward, 1: turn left, 2: turn right.

**Reward Function**:
- Reach goal zone (x > 5.0): `+10`
- Collide with obstacle (distance < 0.3m): `-10`
- Normal step: `-0.1 × min_distance + 1.0`

The linear penalty term encourages maintaining distance from obstacles. The `+1.0` offset ensures the agent receives positive reward for making forward progress, preventing it from learning to stay still to avoid penalties.

**Training**: PPO (Proximal Policy Optimization) from Stable-Baselines3, with an MLP policy network (2 hidden layers of 64 units), learning rate `3×10⁻⁴`, `n_steps=1024`, trained for 100,000 timesteps. Training was run in PyBullet's `DIRECT` mode (headless, no rendering) and completed in a few minutes on a laptop CPU.

**Results**: The trained model achieved a cumulative test reward of `+62.04` and successfully reached the goal in 90 steps by learning a right-side bypass strategy. The model did not develop sophisticated steering — it mostly just turns right — but the complete RL pipeline (environment design, algorithm selection, training, evaluation, and honest analysis of limitations) is implemented and documented.

| Metric | Value |
|:---|:---|
| Algorithm | PPO (Stable-Baselines3) |
| Training Steps | 100,000 |
| Test Cumulative Reward | +62.04 |
| Test Steps to Goal | 90 |
| Learned Strategy | Right-side bypass |

The trained model (`ppo_avoidance_model.zip`) and all training scripts are included in the `DRL-Obstacle-Avoidance/` directory.

---

## Engineering Challenges and Solutions

This section documents the most significant failures encountered during the project and the diagnostic and resolution processes. These experiences were more instructive than any successful integration — they taught hardware debugging, signal integrity analysis, and the importance of protective circuit design.

### 1. TB6612 Motor Driver Burned on First Power-Up

**Problem**: The TB6612 module emitted smoke the moment 12V power was applied. The motor did not turn at all.

**Analysis**: The purchased module's VM pin had a maximum voltage rating of only 10V, as confirmed by checking the manufacturer's datasheet after the failure. The 3S LiPo battery outputs approximately 12.6V when fully charged, exceeding the VM pin's absolute maximum by over 25%. The internal H-bridge MOSFET was destroyed by overvoltage breakdown.

**Solution**: Replaced with a TB6612 module rated for VM ≥15V. Added a 50V 100μF electrolytic capacitor across the motor power rail (`VIN+` to `VIN-`) to absorb the back-EMF voltage spikes generated by motor inductance during startup, braking, and direction changes. This spike can instantaneously exceed the DC supply voltage by a factor of 2–3×.

**Engineering Insight**: Always verify component datasheet specifications before applying power — especially the distinction between "typical operating voltage" and "absolute maximum rating." Passive protection (capacitors) should be considered mandatory, not optional, when driving inductive loads with semiconductor switches.

### 2. STM32 MCU Fried by Backfeed from Damaged TB6612

**Problem**: Several days after replacing the TB6612, the STM32 main chip suddenly overheated and emitted smoke during a test run. The MCU was destroyed.

**Analysis**: The replacement TB6612 had internally failed (likely due to accumulated stress from repeated motor starts without adequate protection at that point). When the internal H-bridge MOSFET shorted, the 12V motor supply rail became connected to the control signal pins (PWMA, AIN1, AIN2, etc.). This 12V backfed through the GPIO pins into the STM32's internal protection diodes and power rail, exceeding the absolute maximum GPIO voltage of `VDD + 0.3V` (approximately 3.6V) and destroying the chip.

**Solution**: Added six 1kΩ current-limiting resistors in series with all control signal lines. If a similar backfeed event occurs, the resistor limits the fault current to `I = (12V - 3.6V) / 1kΩ ≈ 8.4mA` — well within the STM32 GPIO's survival range. Additionally, the JiangKeDa version of the STM32 board was adopted, which includes onboard self-recovery fuses and TVS protection diodes.

**Engineering Insight**: When interfacing a microcontroller to a high-voltage (relative to MCU VDD) power stage, always design for the failure mode where the power stage shorts and applies its rail voltage to the control lines. Current-limiting resistors are cheap insurance against a known failure mechanism.

### 3. Right-Wheel Encoder Unstable — Hardware Fault Isolation

**Problem**: The right-wheel encoder produced erratic readings — frequent zero values interspersed with plausible RPM values. The left encoder worked perfectly. PID control of the right wheel was impossible.

**Analysis**: A cross-swap test was performed: the left encoder's signal lines (PA6/PA7) were connected to the right encoder, and the right encoder's lines (PB6/PB7) were connected to the left encoder. After the swap, the problem followed the hardware — the right encoder readings (now appearing on the left channel) were still erratic. This confirmed that the encoder and its wiring were fine, and the fault was on the MCU side — specifically, the PB6 or PB7 GPIO pin had been damaged.

**Solution**: Since no spare MCU board was available, a workaround was adopted: use only the left encoder for PID feedback, and copy the left PID output to both motors (`__HAL_TIM_SET_COMPARE(&htim2, TIM_CHANNEL_2, left_pid_output)`). This sacrifices independent closed-loop control of the right wheel but allows the robot to continue operating.

**Engineering Insight**: Cross-swap testing is the most definitive way to isolate whether a fault lies in the sensor/peripheral or the MCU. When hardware is damaged and replacements aren't immediately available, a functional workaround that keeps the system operational is better than stalling the project.

### 4. Encoder Reading Spikes to 14,000 RPM — EMI Analysis

**Problem**: At moderate to high motor speeds, the serial monitor intermittently displayed RPM values exceeding 14,000 — physically impossible for this motor and gear ratio.

**Analysis**: The encoder signal lines (PA6, PA7, PB6, PB7) are configured as timer encoder inputs. Between encoder pulses, when the signal should be stable, the lines were in a high-impedance (floating) state. The operating motor generates significant electromagnetic interference (EMI), which was capacitively or inductively coupled onto the floating signal lines, producing spurious edges that the timer's encoder mode counted as legitimate pulses.

**Solution**: A two-layer defense was implemented. In hardware: internal pull-up resistors were enabled on PA6, PA7, PB6, and PB7 via `GPIOA->ODR |= (GPIO_PIN_6 | GPIO_PIN_7)` and `GPIOB->ODR |= (GPIO_PIN_6 | GPIO_PIN_7)`. This forces the signal lines to a defined HIGH level when idle, significantly increasing noise immunity. In software: an outlier rejection filter was added — if the absolute pulse delta in any 10ms period exceeds 100, the delta is set to zero. This threshold corresponds to approximately 412 RPM, well above the maximum physical speed of the motor.

**Engineering Insight**: Floating CMOS inputs are antennas for EMI. Always define the idle state of digital signal lines with pull-up or pull-down resistors. When a hardware fix is insufficient, a software filter provides defense-in-depth. The combination of both approaches solved the problem completely.

### 5. printf Cannot Print Floating-Point Numbers

**Problem**: The serial monitor displayed text labels (e.g., "RPM:") but no numeric values. Integer printing worked fine; only floats failed.

**Analysis**: STM32CubeIDE links against the Newlib-nano standard C library by default. To minimize Flash and RAM footprint, Newlib-nano compiles `printf` without floating-point formatting support. The `%f`, `%.1f`, `%.2f` format specifiers are silently ignored, and no conversion occurs.

**Solution**: All floating-point values are multiplied by 100 and cast to `int32_t` before printing. Integer and fractional parts are printed separately using `%ld.%02ld` format strings. For example, an RPM value of 157.89 is printed as `157.89` via `sprintf(buf, "%ld.%02ld", rpm_int/100, rpm_int%100)`.

**Engineering Insight**: This is a well-documented limitation of Newlib-nano, but discovering it through debugging is far more memorable than reading about it in documentation. Resource-constrained embedded systems often require workarounds for features that are taken for granted on desktop platforms.

### 6. Transparent Object Invisible to Depth Estimation

**Problem**: A clear plastic water bottle was correctly detected by YOLO (labeled "bottle" with high confidence), but the MiDaS depth map showed the background wall behind the bottle, not the bottle itself. The depth value in the bottle's detection box region was effectively infinite.

**Analysis**: This is not a software bug — it is a fundamental limitation of monocular depth estimation. The technique relies on surface texture, shading, and perspective cues to infer depth. A transparent object does not occlude the background; light passes through it, so the camera captures the texture of whatever is behind the bottle. The neural network correctly interprets this as "the background wall is at distance X," because that is what the pixel data represents.

**Solution**: Wrapped a strip of colored opaque tape around the bottle. The tape provides the surface texture and occlusion that the depth model needs. After this modification, the depth map correctly showed the bottle at its actual distance.

**Engineering Insight**: Perception failures in real-world robotics are often not algorithmic problems but physical ones. The solution is sometimes not to improve the model, but to change the environment to make it more perceivable. This is a legitimate engineering approach — retroreflective markers, QR codes, and colored fiducials are used in industrial robotics for exactly this reason.

### 7. Serial Communication Unidirectional Failure

**Problem**: The STM32 could transmit data to the PC (TX direction — PC received "PID Ready" and RPM data normally), but could never receive data from the PC (RX direction — Python scripts and SSCOM both failed to deliver commands). The STM32's `HAL_UART_Receive_IT` callback was never triggered.

**Analysis**: TX/RX lines were swapped to rule out wiring error. Different CH340 modules were tested to rule out module failure. Different USB ports and a different computer were tested to rule out driver or OS issues. The failure persisted in all configurations. The root cause was likely a hardware fault in the CH340's TX channel or an electrical issue on the STM32's RX pin (PA10).

**Solution**: Abandoned wired serial and adopted Bluetooth (HC-05 master-slave paired configuration). The HC-05 modules connect to the STM32's USART1 pins (PA9/PA10) just like the CH340, so no firmware changes were needed. The Bluetooth link works bidirectionally and also eliminates the USB tether.

**Engineering Insight**: When debugging reaches diminishing returns on a particular component, switching to an alternative technology is a valid engineering decision. The time spent trying to fix the CH340 link could have been spent on more productive tasks. The serial protocol design and self-test scripts are preserved in the repository as evidence of the design work.

### 8. micro-ROS Not Supported on STM32F103

**Problem**: After setting up the micro-ROS build environment, compiling the toolchain, and writing the integration code, the `create_firmware_ws.sh` script reported that `stm32f103c8t6` is not in the list of officially supported platforms.

**Analysis**: The STM32F103C8T6 has only 20KB of SRAM. micro-ROS requires a minimum of approximately 40KB for the FreeRTOS kernel, the micro-ROS client library, the DDS-XRCE transport layer, and the application code. The official FreeRTOS templates in micro-ROS target STM32F4 series chips (e.g., `nucleo_f446re`, `olimex-stm32-e407`) which have 128KB+ SRAM.

**Solution**: The architecture design, build environment, CubeIDE project, and integration code are fully documented. The limitation is clearly explained. Upgrading to an STM32F4 board would resolve the issue immediately using the official templates. This was not pursued due to time constraints, but the preparatory work is complete.

**Engineering Insight**: Knowing when a technical approach is infeasible with current hardware — and being able to explain exactly why — is as important as knowing how to implement it. This demonstrates technical judgment rather than blind persistence.

---

## Experimental Results

### PID Closed-Loop Performance

| Metric | Value |
|:---|:---|
| Target RPM | 100 |
| Steady-State RPM | 90–98 |
| Steady-State Error | <10% |
| RPM Fluctuation Range | ±5 RPM |
| Disturbance Recovery Time | <1 second |
| PWM Frequency | 1 kHz |
| Control Period | 10 ms |

### Visual Perception Performance

| Metric | Value |
|:---|:---|
| YOLOv8n Inference Speed | 20–30 FPS (laptop CPU) |
| MiDaS Input Resolution | 256×256 |
| Depth Scaling Constant | 150 (1-meter reference) |
| Avoidance Safety Threshold | 0.5 meters |

### Reinforcement Learning Training

| Metric | Value |
|:---|:---|
| Algorithm | PPO (Stable-Baselines3) |
| Training Environment | PyBullet (DIRECT mode) |
| Training Steps | 100,000 |
| Test Cumulative Reward | +62.04 |
| Test Steps to Goal | 90 |

### ROS2 Verification

| Metric | Value |
|:---|:---|
| ROS2 Distribution | Humble |
| Environment | WSL Ubuntu 22.04 |
| Nodes | image_publisher, image_subscriber |
| Topic | /camera/image |
| Communication | Verified via `ros2 topic list` and subscriber logs |

---

## Future Research Directions

### Embodied Intelligence and Sim-to-Real Transfer

The current system uses a rule-based state machine for avoidance decisions. This works for simple static environments but will fail in dynamic or cluttered scenes. The reinforcement learning environment built in Direction 3 provides a foundation for training more sophisticated navigation policies. The natural next step is to close the sim-to-real gap — train a policy in PyBullet (or a more realistic simulator like Isaac Sim) and deploy it on the physical robot. Domain randomization (varying lighting, textures, obstacle geometries during training) would improve transfer robustness.

### ROS2-Native Robot with Onboard Compute

The current system runs AI inference on a laptop. To make the robot truly self-contained, the laptop should be replaced with an embedded Linux board (Raspberry Pi 4B or Orange Pi 3B). The modular Python code can be directly migrated to ROS2 nodes running on the onboard computer. The STM32 would continue handling real-time motor control, communicating with the ROS2 nodes either via the existing Bluetooth serial link or (after upgrading to an STM32F4) via micro-ROS as a native ROS2 node.

### Multi-Sensor Fusion for Robust Perception

The transparent object failure demonstrated the fundamental limitation of relying on a single monocular camera. Adding a second sensing modality — even a simple ultrasonic distance sensor — would provide a safety net when visual perception fails. This is standard practice in commercial robots: sensor redundancy is not optional, it is essential for safety-critical operation. A ROS2-based sensor fusion node that combines visual depth estimates with ultrasonic range readings would be a natural extension.

---

## Repository Structure

The repository is organized by project phase, with each phase containing its own code, documentation, and media.

- **01-Hardware-Setup** — Hardware photos, wiring diagram, and component list.
- **02-OpenLoop-Test** — CubeIDE project for open-loop motor control verification.
- **03-PID-Control** — CubeIDE project for PID speed closed-loop control, serial data screenshots, and disturbance test video.
- **04-Serial-Protocol** — Communication protocol design, Python control and self-test scripts.
- **05-Visual-Perception** — YOLO + MiDaS perception pipeline, detection/depth/fusion screenshots, transparent object fix comparison.
- **06-Autonomous-Avoidance** — Monolithic and modular avoidance scripts, decision screenshots, and full demonstration video.
- **ros2/vision_pkg** — Direction 1: ROS2 node package with publisher and subscriber, communication verification screenshot.
- **ros2/micro_ros_design** — Direction 2: micro-ROS build environment and CubeIDE project framework.
- **DRL-Obstacle-Avoidance** — Direction 3: PyBullet simulation environment, PPO training script, trained model weights, and test results.
- **docs/** — Detailed design documents for all phases and directions.
- **images/** — All screenshots and photographs.
- **videos/** — Links to demonstration videos.

---

## License

MIT License
