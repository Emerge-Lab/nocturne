import numpy as np
import gymnasium as gym

from nocturne.envs.base_env import BaseEnv
from utils.config import load_config


class LightNocturneEnvWrapper: 
    """A minimal wrapper around the Nocturne BaseEnv."""

    def __init__(self, config):
        self.env = BaseEnv(config)
        self.files = self.env.files

        # Make action and observation spaces compatible with SB3 (requires gymnasium)
        self.action_space = gym.spaces.Discrete(self.env.action_space.n)
        self.observation_space = gym.spaces.Box(-np.inf, np.inf, self.env.observation_space.shape, np.float32)
    
    def step(self, actions=None):

        obs = np.zeros((self.num_agents, self.observation_space.shape[0]))
        rews, dones, infos = np.zeros((self.num_agents)), np.zeros((self.num_agents)), []

        if actions is not None:
            agent_actions = {
                agent_id: actions[idx] for idx, agent_id in enumerate(self.agent_ids) 
                if agent_id not in self.dead_agent_ids
            }
        else:
            agent_actions = {}

        # Take a step to obtain dicts
        next_obses_dict, rew_dict, done_dict, info_dict = self.env.step(agent_actions)

        # Update dead agents based on most recent done_dict
        for agent_id, is_done in done_dict.items():
            if is_done and agent_id not in self.dead_agent_ids:
                self.dead_agent_ids.append(agent_id)

        # Convert dicts to arrays
        for idx, key in enumerate(self.agent_ids):
            if key in next_obses_dict:
                obs[idx, :] = next_obses_dict[key]
                rews[idx] = rew_dict[key] 
                dones[idx] = done_dict[key] * 1
                infos.append(info_dict[key])
            else:
                infos.append([None])
            

        return obs, rews, dones, infos


    def reset(self, filename=None):
        obs_dict = self.env.reset(filename)

        self.controlled_vehicles = self.env.controlled_vehicles
        self.num_agents = len(self.controlled_vehicles)
        self.agent_ids = []
        self.dead_agent_ids = []
        self.scenario = self.env.scenario
        obs = []
        for agent_id in obs_dict.keys():
            self.agent_ids.append(agent_id)
            obs.append(obs_dict[agent_id])

        self.map_agent_id_to_idx = {agent_id: idx for idx, agent_id in enumerate(self.agent_ids)}

        return np.array(obs)

    def close(self) -> None:
        """Close the environment."""
        self.env.close()




if __name__ == "__main__":

    env_config = load_config("env_config")

    env = LightNocturneEnvWrapper(env_config)
