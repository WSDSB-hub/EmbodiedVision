import pybullet as p
import pybullet_data
import time

# 连接仿真引擎（GUI模式，能看到画面）
client = p.connect(p.GUI)
p.setAdditionalSearchPath(pybullet_data.getDataPath())
p.setGravity(0, 0, -10)

# 加载地面
plane = p.loadURDF("plane.urdf")

# 加载一个小车模型
car = p.loadURDF("r2d2.urdf", [0, 0, 1])

print("PyBullet 仿真环境正常！按 Ctrl+C 退出")
while True:
    p.stepSimulation()
    time.sleep(1./240.)