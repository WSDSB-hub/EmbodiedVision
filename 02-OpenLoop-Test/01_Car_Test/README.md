# 02 - Open Loop Test

## 目标
验证双电机硬件连接和基本驱动功能。让两个轮子能够受控正转、反转和调速，为后续PID闭环控制打下基础。

## 测试内容
- 两个轮子正转加速（200→600占空比）
- 两个轮子反转加速（200→600占空比）
- 暂停后循环

## 硬件配置
- 左轮PWM：PA0（TIM2_CH1）
- 右轮PWM：PA1（TIM2_CH2）
- 左轮方向：PA2（AIN1）、PA3（AIN2）
- 右轮方向：PA4（BIN1）、PA5（BIN2）
- 左轮编码器：PA6/PA7（TIM3）
- 右轮编码器：PB6/PB7（TIM4）

## 测试结果
两个轮子均能正常正反转和调速，方向一致，电机驱动和编码器接线正确。

## 文件说明
- `01_Car_Test/`：STM32CubeIDE完整工程
- `openloop_test.mp4`：【335efce7af04f9399de7b8bb2ac7c353】https://www.bilibili.com/video/BV1W4um6YE7F?vd_source=ca02a8f800081a3f155da90b42811dbe
