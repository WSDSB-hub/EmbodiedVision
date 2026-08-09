import gymnasium as gym
from gymnasium import spaces
import numpy as np
import pybullet as p
import pybullet_data

class AvoidanceEnv(gym.Env):
    """小车自主避障强化学习环境"""
    
    def __init__(self):
        super().__init__()
        # 动作空间：0=前进，1=左转，2=右转
        self.action_space = spaces.Discrete(3)
        # 观测空间：前方三个方向的距离传感器数据
        self.observation_space = spaces.Box(
            low=0, high=10, shape=(3,), dtype=np.float32
        )
        self.client = None
        self.car_id = None
        self.obstacles = []

    def reset(self, seed=None, options=None):
        if self.client is not None:
            p.disconnect()
        self.client = p.connect(p.DIRECT)  # DIRECT模式无GUI，训练更快
        p.setAdditionalSearchPath(pybullet_data.getDataPath())
        p.setGravity(0, 0, -10)
        
        p.loadURDF("plane.urdf")
        self.car_id = p.loadURDF("r2d2.urdf", [0, 0, 0.5])
        
        self.obstacles = []
        for _ in range(2):
            x = 2.0 + np.random.uniform(-0.5, 0.5)
            y = np.random.uniform(-1.0, 1.0)
            obs_id = p.loadURDF("cube_small.urdf", [x, y, 0.5])
            self.obstacles.append(obs_id)
        
        obs = np.array([2.0, 2.0, 2.0], dtype=np.float32)
        return obs, {}

    def step(self, action):
        pos, _ = p.getBasePositionAndOrientation(self.car_id)
        
        if action == 0:      # 前进
            new_x = pos[0] + 0.1
            new_y = pos[1]
        elif action == 1:    # 左转
            new_x = pos[0] + 0.05
            new_y = pos[1] + 0.1
        else:                # 右转
            new_x = pos[0] + 0.05
            new_y = pos[1] - 0.1
        
        p.resetBasePositionAndOrientation(
            self.car_id, [new_x, new_y, 0.5], [0, 0, 0, 1]
        )
        
        min_dist = 10.0
        for obs_id in self.obstacles:
            obs_pos, _ = p.getBasePositionAndOrientation(obs_id)
            dist = np.linalg.norm(
                np.array([new_x, new_y]) - np.array(obs_pos[:2])
            )
            if dist < min_dist:
                min_dist = dist
        
        obs = np.array([min_dist, min_dist, min_dist], dtype=np.float32)
        
        if min_dist < 0.3:
            reward = -10
            terminated = True
        elif new_x > 5.0:
            reward = 10
            terminated = True
        else:
            reward = -0.1 * min_dist + 1.0
            terminated = False
        
        return obs, reward, terminated, False, {}

    def close(self):
        if self.client is not None:
            p.disconnect()