from multimodal_robot_model.diffusion_policy import RolloutDiffusionPolicy
from multimodal_robot_model.common.rollout import RolloutMujocoXarm7Cable

class RolloutDiffusionPolicyMujocoXarm7Cable(RolloutDiffusionPolicy, RolloutMujocoXarm7Cable):
    pass

if __name__ == "__main__":
    rollout = RolloutDiffusionPolicyMujocoXarm7Cable()
    rollout.run()
