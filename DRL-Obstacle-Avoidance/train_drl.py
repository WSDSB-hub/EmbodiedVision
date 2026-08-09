from stable_baselines3 import PPO
from drl_avoidance_env import AvoidanceEnv

print("创建仿真环境...")
env = AvoidanceEnv()

print("开始训练PPO模型（预计10-30分钟，请耐心等待）...")
model = PPO(
    "MlpPolicy",
    env,
    verbose=1,
    learning_rate=0.0003,
    n_steps=1024,
)

model.learn(total_timesteps=100000)
model.save("ppo_avoidance_model")
print("模型已保存为 ppo_avoidance_model.zip")
env.close()