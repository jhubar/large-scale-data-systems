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
    timestep = 3830
    complete = False
    servers = get_servers()
    id_leader = None

    # Varibales to count good anwsers proportions
    total_aws = 0
    good_aws = 0
    to_compare_keys = ['pitch', 'throttle', 'heading', 'stage', 'next_state']
    while not complete:
        timestep += 1
        time.sleep(1)
        print("Trying to replicate at timestep = {}".format(timestep))

        state = readout_state(timestep)
        print(state)
        if id_leader is None:
            # Randomly select a server
            id_leader = select_leader(servers)
        # Try replicate the action
        state_dict = {}
        state_dict['state'] = state

        state_decided = send_post(id_leader, 'decide_on_state', state_dict, TIMEOUT=0.075)

        # print("Decided state: {}".format(state_decided.json()))


        # Check if no answer from the server
        if state_decided is None:
            # Set leader to None
            id_leader = None
            time.sleep(0.5)
            continue
        if state_decided.json()['host'] is None:
            id_leader = None
            time.sleep(0.5)
            continue
        if state_decided.json()['status'] is False:
            continue

        # Check if leader has changed
        tmp_leader = {'host': state_decided.json()['host'], 'port': state_decided.json()['port']}
        id_leader = change_leader(tmp_leader, id_leader)

        # Decide action
        aws = None
        aws = send_post(id_leader, 'action_consensus', {}, TIMEOUT=0.075)
        if aws is None:
            id_leader = None
            time.sleep(0.5)
            continue

        if 'host' not in aws.json().keys() or aws.json()['host'] is None:
            id_leader = None
            time.sleep(0.5)
            continue

        if 'next_state' not in aws.json().keys():
            continue

        tmp_leader = {'host': aws.json()['host'], 'port': aws.json()['port']}

        print(aws.json())

        action = aws.json()
        action.pop('host')
        action.pop('port')
        print('CONSENSUS ACTION: {}'.format(action))

        # Check good predictions proportion:
        is_same = True
        original = actions[timestep]
        for ky in to_compare_keys:
            if original[ky] != action[ky]:
                is_same = False
        total_aws += 1

        if is_same:
            good_aws += 1

        print('CONSENSUS-SCORE: good action: {} / {}'.format(good_aws, total_aws))

        # check if action is None, i.e it means consensus is done
        id_leader = change_leader(tmp_leader, id_leader)
        if action is None:
            complete = True
            time.sleep(0.5)
            continue


    if complete:
        print("Success!")
    else:
        print("Fail!")

def readout_state(timestep):
    return states[timestep]

def execute_action(action, timestep):
    keys = ["pitch", "throttle","heading","stage","next_state"]

    for k in keys:
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
