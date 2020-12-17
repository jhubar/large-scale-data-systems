import argparse
import math
import pickle
import numpy as np
import time

from Raft.Abstraction.send import send_post
import threading

# Load the pickle files
actions = pickle.load(open("data/actions.pickle", "rb"))
states = pickle.load(open("data/states.pickle", "rb"))
timestep = 0

def readout_state():
    return states[timestep]

def execute_action(action):
    #print(action)
    #print(actions[timestep])
    for k in action.keys():
        assert(action[k] == actions[timestep][k])


complete = False

while not complete:
    timestep += 1
    state = readout_state()
    # Try replicate the action
    state_dict = {}
    state_dict['state'] = state
    state_decided = send_post({'host': '127.0.0.1', 'port': 8001}, 'decide_on_state', state_dict, TIMEOUT=0.075)
    if state_decided is None or not state_decided.json():
        continue
    # Check the action that the leader will try to replicate
    action = send_post({'host': '127.0.0.1', 'port': 8001}, 'sample_next_action', {}, TIMEOUT=0.075)
    if action is None:
        continue
    if action.json() is None:
        complete = True
        continue
    action_dict = {}
    action_dict['action'] = action.json()
    # Ask to leader to replicate this action
    answer = send_post({'host': '127.0.0.1', 'port': 8001}, 'decide_on_action', action_dict, TIMEOUT=0.075)
    if answer is not None and answer.json():
        execute_action(action.json())
    else:
        timestep -= 1


if complete:
    print("Success!")
else:
    print("Fail!")
