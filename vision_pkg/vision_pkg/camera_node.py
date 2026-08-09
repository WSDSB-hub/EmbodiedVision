#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
import cv2
import numpy as np
from cv_bridge import CvBridge

class CameraNode(Node):
    def __init__(self):
        super().__init__('camera_node')
        self.publisher = self.create_publisher(Image, '/camera/image', 10)
        self.bridge = CvBridge()
        self.timer = self.create_timer(0.1, self.timer_callback)
        self.get_logger().info('Camera node started (test image mode)')

    def timer_callback(self):
        # 生成一张测试图片（蓝色背景 + 红色方块模拟障碍物）
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        frame[:, :] = (200, 220, 255)  # 浅蓝色背景
        cv2.rectangle(frame, (250, 150), (390, 350), (0, 0, 255), -1)  # 红色方块
        cv2.putText(frame, "ROS2 Test", (200, 100), cv2.FONT_HERSHEY_SIMPLEX, 1, (0,0,0), 2)

        msg = self.bridge.cv2_to_imgmsg(frame, encoding='bgr8')
        self.publisher.publish(msg)
        self.get_logger().info('Published test image')

def main(args=None):
    rclpy.init(args=args)
    node = CameraNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
