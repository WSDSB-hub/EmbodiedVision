#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
import numpy as np

class ImagePublisher(Node):
    def __init__(self):
        super().__init__('image_publisher')
        self.publisher = self.create_publisher(Image, '/camera/image', 10)
        self.timer = self.create_timer(0.5, self.timer_callback)
        self.get_logger().info('Image publisher started')

    def timer_callback(self):
        img = np.zeros((480, 640, 3), dtype=np.uint8)
        img[:, :] = (200, 220, 255)
        img[150:350, 250:390] = (0, 0, 255)

        msg = Image()
        msg.height = img.shape[0]
        msg.width = img.shape[1]
        msg.encoding = 'bgr8'
        msg.is_bigendian = 0
        msg.step = img.shape[1] * 3
        msg.data = img.tobytes()
        self.publisher.publish(msg)
        self.get_logger().info('Published test image')

def main(args=None):
    rclpy.init(args=args)
    node = ImagePublisher()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
