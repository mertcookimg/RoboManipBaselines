import numpy as np
import pinocchio as pin
import gymnasium as gym
import multimodal_robot_model
from multimodal_robot_model.common import MotionStatus
from .RolloutBase import RolloutBase

class RolloutRealUR5eGear(RolloutBase):
    def __init__(self, robot_ip, camera_ids):
        self.robot_ip = robot_ip
        self.camera_ids = camera_ids
        super().__init__()

    def setupEnv(self):
        self.env = gym.make(
            "multimodal_robot_model/RealUR5eGearEnv-v0",
            robot_ip=self.robot_ip,
            camera_ids=self.camera_ids,
            scale_dt=self.args.scale_dt
        )

    def setCommand(self):
        # Set joint command
        if self.data_manager.status in (MotionStatus.PRE_REACH, MotionStatus.REACH):
            # No action is required in pre-reach or reach phases
            pass
        elif self.data_manager.status == MotionStatus.TELEOP:
            self.motion_manager.joint_pos = self.pred_action[:6]

        # Set gripper command
        if self.data_manager.status == MotionStatus.GRASP:
            self.motion_manager.gripper_pos = self.env.action_space.low[6]
        elif self.data_manager.status == MotionStatus.TELEOP:
            self.motion_manager.gripper_pos = self.pred_action[6]
