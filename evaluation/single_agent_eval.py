import numpy as np
import torch
from tqdm import tqdm
import pandas as pd
from nocturne.envs.base_env import BaseEnv
from utils.config import load_config
import logging

def evaluate_policy(
    env_config, 
    mode, 
    num_scenes=100,
    max_iters=100, 
    scene_path_mapping=None, 
    policy=None, 
    controlled_agents=1, 
    deterministic=True,
):  
    """Evaluate a policy on a set of scenes.

    Args:
        env_config (Box): Environment configurations.
        mode (str): Mode of evaluation. Either "expert_replay" or "policy".
        scene_path_mapping (dict, optional): Dictionary with scene information. Defaults to None.
        policy (optional): Learned policy. Defaults to None.
        num_scenes (int, optional): Number of traffic scenes to use for evaluation. Defaults to 100.
        controlled_agents (int, optional): Number of agents to control with the provided policy. Defaults to 1.
        deterministic (bool, optional): Whether to evaluate the policy in deterministic or stochastic mode. Defaults to True.

    Raises:
        ValueError: If scene is not found in scene_path_mapping.

    Returns:
        df: performance per scene.
    """
    
    MAX_ACCEL = 0
    MAX_STEERING = 0
    
    # Set the number of vehicles to control per scene
    env_config.max_num_vehicles = controlled_agents
    
    # Set which files to use
    env_config.num_files = num_scenes

    # Make env
    env = BaseEnv(env_config)

    # Storage
    df = pd.DataFrame(
        columns=[
            'scene_id',
            'veh_id',
            'goal_rate', 
            'off_road', 
            'veh_veh_collision', 
        ],
    )

    # Run
    obs_dict = env.reset()
    agent_ids = [veh_id for veh_id in obs_dict.keys()]
    dead_agent_ids = []
    last_info_dicts = {agent_id: {} for agent_id in agent_ids}
    total_off_road = 0
    total_coll = 0
    total_goal_achieved = 0

    for episode in tqdm(range(max_iters)):
        
        logging.debug(f'scene: {env.file} -- veh_id = {agent_ids[0]} --')
        
        frames = []
        
        for time_step in range(env_config.episode_length):
            
            # Get actions
            action_dict = {}

            if mode == "policy" and policy is not None:
                for agent_id in obs_dict:
                    # Get observation
                    obs = torch.from_numpy(obs_dict[agent_id]).unsqueeze(dim=0)

                    # Get action
                    action, _ = policy.predict(obs, deterministic=deterministic)
                    action_dict[agent_id] = int(action)

            if mode == "expert_replay":
                # Use expert actions
                for veh_obj in env.controlled_vehicles:
                    veh_obj.expert_control = True
                    
                    expert_action = env.scenario.expert_action(veh_obj, time_step)
                    
                    if expert_action is not None:
                        if expert_action.acceleration > MAX_ACCEL:
                            MAX_ACCEL = expert_action.acceleration
                            #print(f'MAX_ACCEL: {MAX_ACCEL:3f}')
                        if expert_action.steering > MAX_STEERING:
                            MAX_STEERING = expert_action.steering
                            #print(f'MAX_STEERING: {MAX_STEERING:3f} \n')  
            
            if mode == "cont_expert_act_replay":  # Use continuous expert actions
                for veh_obj in env.controlled_vehicles:
                    veh_obj.expert_control = False
                    
                    # Get (continuous) expert action
                    expert_action = env.scenario.expert_action(veh_obj, time_step)
                    
                    action_dict[veh_obj.id] = expert_action
                    
            if mode == "disc_expert_act_replay":  # Use discretized expert actions            
                # Get expert actions and discretize
                for veh_obj in env.controlled_vehicles:
                    veh_obj.expert_control = True
                    
                    # Get (continuous) expert action
                    expert_action = env.scenario.expert_action(veh_obj, time_step)
                                
                    # Discretize expert action
                    if expert_action is None:
                        logging.info(f'None at {time_step} for veh {veh_obj.id} in {env.file} \n')
                    
                    elif expert_action is not None:
                        expert_accel, expert_steering, _ = expert_action.numpy()
                        
                        # Map actions to nearest grid indices and joint action
                        acc_grid_idx = np.argmin(np.abs(env.accel_grid - expert_accel))
                        ste_grid_idx = np.argmin(np.abs(env.steering_grid - expert_steering))
    
                        expert_action_idx = env.actions_to_idx[
                            env.accel_grid[acc_grid_idx], 
                            env.steering_grid[ste_grid_idx],
                        ][0]
                        
                        action_dict[veh_obj.id] = expert_action_idx
                                            
                        logging.debug(f'true_exp_acc = {expert_action.acceleration:.4f}; true_exp_steer = {expert_action.steering:.4f}')
                        logging.debug(f'disc_exp_acc = {env.accel_grid[acc_grid_idx]:.4f}; disc_exp_steer = {env.steering_grid[ste_grid_idx]:.4f} \n')
                        
                for veh_obj in env.controlled_vehicles:
                    veh_obj.expert_control = True
                        
                # Turn off expert control
                for veh_obj in env.controlled_vehicles:
                    veh_obj.expert_control = False

            # Take a step
            obs_dict, rew_dict, done_dict, info_dict = env.step(action_dict)

            for agent_id, is_done in done_dict.items():
                if is_done and agent_id not in dead_agent_ids:
                    dead_agent_ids.append(agent_id)
                    # Store agents' last info dict
                    last_info_dicts[agent_id] = info_dict[agent_id].copy()

            if done_dict["__all__"]:
                # Update df
                for agent_id in agent_ids:
                    total_coll += last_info_dicts[agent_id]["veh_veh_collision"] * 1
                    total_off_road += last_info_dicts[agent_id]["veh_edge_collision"] * 1
                    total_goal_achieved += last_info_dicts[agent_id]["goal_achieved"] * 1
                                
                if scene_path_mapping is not None:
                    if env.file in scene_path_mapping.keys():
                        df_scene_i = pd.DataFrame(
                            {   
                                'scene_id': env.file,
                                'veh_id': agent_ids[0],
                                'goal_rate': total_goal_achieved, 
                                'off_road': total_off_road, 
                                'veh_veh_collision': total_coll, 
                                'num_total_vehs' : scene_path_mapping[env.file]["num_agents"],
                                'num_controlled_vehs': len(agent_ids),
                                'num_int_paths': scene_path_mapping[env.file]["intersecting_paths"],
                            },
                        index=[0]) 
                    else:
                        raise ValueError(f"Scene {env.file} not found in scene_path_mapping")
                                
                else:
                    df_scene_i = pd.DataFrame(
                        {   
                            'scene_id': env.file,
                            'goal_rate': total_goal_achieved, 
                            'off_road': total_off_road, 
                            'veh_veh_collision': total_coll, 
                        },
                    index=[0])  
                 
                # Append to df
                df = pd.concat([df, df_scene_i], ignore_index=True)
        
                # Reset
                obs_dict = env.reset()
                agent_ids = [veh_id for veh_id in obs_dict.keys()]
                dead_agent_ids = []
                last_info_dicts = {agent_id: {} for agent_id in agent_ids}
                total_off_road = 0
                total_coll = 0
                total_goal_achieved = 0
                
                break # Continue to next scene

    return df


if __name__ == "__main__":
    
    # Global setting
    logger = logging.getLogger()
    logging.basicConfig(format="%(message)s")
    logger.setLevel('INFO')
    
    env_config = load_config("env_config")
    
    df_disc_expert_replay = evaluate_policy(
        env_config=env_config,
        mode='disc_expert_replay',
        num_scenes=100,
        max_iters=100,
    )