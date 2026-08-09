from stable_baselines3 import PPO
from drl_avoidance_env import AvoidanceEnv

model = PPO.load("ppo_avoidance_model")
env = AvoidanceEnv()

obs, _ = env.reset()
total_reward = 0
step = 0

for _ in range(200):
    action, _ = model.predict(obs)
    obs, reward, terminated, _, _ = env.step(int(action))
    total_reward += reward
    step += 1
    print(f"Step {step}: action={action}, reward={reward:.2f}, total={total_reward:.2f}")
    if terminated:
        break

print(f"\n测试结束：总步数={step}，累计奖励={total_reward:.2f}")
env.close()