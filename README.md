# VisionBot — A Self-Built Visual Obstacle Avoidance Robot

## Project Overview

I built this robot to answer a question that has bothered me since I started learning about embodied intelligence: what does it actually take to close the perception-decision-action loop on a real physical system? Papers and simulation environments make it look clean — a neural network outputs an action, a robot executes it, done. But when you're the one who has to make the motor spin at exactly the right speed, and the camera has to see a transparent water bottle, and the serial port refuses to work in one direction for no apparent reason, you realize that the gap between a simulated agent and a real robot is where most of the engineering actually lives.

This project is my attempt to cross that gap. The robot uses a USB camera to watch the road ahead. YOLOv8 detects obstacles and MiDaS estimates their depth. A rule-based state machine decides whether to go forward, turn, or back up. The decision is sent over Bluetooth to an STM32F103C8T6 microcontroller, which runs a 100 Hz PID speed controller on two DC motors. The entire system runs on a 12V LiPo battery, completely untethered.

Along the way, I burned a motor driver, fried an MCU, fought an encoder that refused to cooperate, discovered that monocular depth estimation is blind to transparent objects, and learned that sometimes the best engineering decision is to stop debugging a serial port and switch to Bluetooth. This README documents what I built, why I built it, and — most importantly — what went wrong and what I learned from each failure.

---

## System Architecture

The system uses a heterogeneous computing architecture. The laptop handles all AI inference — YOLO object detection and MiDaS depth estimation — because these models require computational resources far beyond what a microcontroller can provide. The STM32 handles real-time motor control — reading encoder pulses, computing PID output, and updating PWM duty cycles at a strict 100 Hz interval — because this task requires deterministic timing that a general-purpose OS cannot guarantee.

The two processors communicate over Bluetooth. The laptop sends single ASCII characters (`'w'`, `'a'`, `'d'`, `'s'`, space) that the STM32 parses as motion commands. This simple protocol keeps the firmware minimal and reliable.

