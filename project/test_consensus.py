import argparse
import math
import pickle
import numpy as np
import time
import json

from Raft.Abstraction.send import send_post
import threading

# Load the pickle files
actions = pickle.load(open("data/actions.pickle", "rb"))
states = pickle.load(open("data/states.pickle", "rb"))

def main():
    timestep = 0
    complete = False
    servers = get_servers()
    id_leader = None
    while not complete:
        timestep += 1
        state = readout_state(timestep)
        if id_leader is None:
            # Randomly select a server
            id_leader = select_leader(servers)
        print()
        print("Replicate this state")
        # Try replicate the action
        state_dict = {}
        state_dict['state'] = state
        state_decided = send_post(id_leader, 'decide_on_state', state_dict, TIMEOUT=0.075)

        # Check if no answer from the server
        if state_decided is None:
            # Set leader to None
            id_leader = None
            continue
        # Check if leader has changed
        id_leader = change_leader(state_decided.json()['leader'], id_leader)
        if not state_decided.json()['status']:
            # Consensus failed on State
            continue

        print("LEADER! May the force be with you")
        # Check the action that the leader will try to replicate
        action = send_post(id_leader, 'sample_next_action', {}, TIMEOUT=0.075)
        if action is None:
            # Leader maybe crashed...
            id_leader = None
            continue
        print(action.json())
        # check if action is None, i.e it means consensus is done
        id_leader = change_leader(action.json()['leader'], id_leader)
        if action.json()['action'] is None:
            complete = True
            continue
        elif action.json()['action'] == -1:
            # No leader
            continue

        print('LEADER! Replicate this action')
        print()
        action_dict = {}
        action_dict['action'] = action.json()['action']
        # Ask to leader to replicate this action
        action_decided = send_post(id_leader, 'decide_on_action', action_dict, TIMEOUT=0.075)
        if action_decided is None:
            id_leader = None
            timestep -= 1
            continue

        id_leader = change_leader(action_decided.json()['leader'], id_leader)
        if action_decided.json()['status']:
            execute_action(action.json()['action'], timestep)
        else:
            timestep -= 1

    if complete:
        print("Success!")
    else:
        print("Fail!")

def readout_state(timestep):
    return states[timestep]

def execute_action(action, timestep):
    for k in action.keys():
        assert(action[k] == actions[timestep][k])

def get_servers():
    servers = []
    with open('peering.json') as server_file:
        peering_json = json.load(server_file)
        try:
            # Check if file is ok
            servers = peering_json['peers']
        except Exception as e:
            print("The file peering.json contains erroneous data...")
            return None

    return servers

def select_leader(servers):
    leader_index = np.random.randint(0, len(servers))
    return servers[leader_index]

def change_leader(proposed_leader, id_leader):
    if proposed_leader != id_leader:
        id_leader = proposed_leader
    return id_leader

if __name__ == '__main__':
    main()
