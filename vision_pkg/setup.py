from setuptools import setup

package_name = 'vision_pkg'

setup(
    name=package_name,
    version='0.1.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Your Name',
    maintainer_email='your@email.com',
    description='ROS2 vision package',
    license='Apache License 2.0',
    entry_points={
        'console_scripts': [
            'image_publisher = vision_pkg.image_publisher:main',
            'image_subscriber = vision_pkg.image_subscriber:main',
        ],
    },
)
