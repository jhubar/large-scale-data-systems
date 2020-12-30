import argparse
import math
import pickle
import numpy as np
import time
import json

from Abstraction.send import send_post

def select_leader(servers):
    """
    This method randomly select a leader in the servers list
    :param servers: the servers list
    :return: the id of a leader
    """
    leader_index = np.random.randint(0, len(servers))
    return servers[leader_index]

if __name__ == '__main__':

    # Load the pickle files
    actions = pickle.load(open("data/actions.pickle", "rb"))
    states = pickle.load(open("data/states.pickle", "rb"))

    # The starting time step:
    timestep = 0
    # A variable to store the leader id
    id_leader = None
    # The host adress
    host = '127.0.0.1'
    # State's keys who must have the same value to compare if two states are the same
    to_compare_keys = ['pitch', 'throttle', 'heading', 'stage', 'next_state']
    # Anwsers conting variables:
    total_asw = 0
    good_asw = 0

    # Get the list of active flight computers
    servers_tmp = []
    with open('peering.json') as server_file:
        peering_json = json.load(server_file)
        try:
            # Check if file is ok
            servers_tmp = peering_json['peers']
        except Exception as e:
            print("The file peering.json contains erroneous data...")
    # Keep only port as id
    servers = []
    for serv in servers_tmp:
        servers.append(serv['port'])

    # Main loop
    complete = False
    while not complete:

        timestep += 1
        # A time sleep to simulate real duration of a time step
        time.sleep(0.1)

        # =============================================================================== #
        #                             State Replication step                              #
        #                                                                                 #
        # During this step, the state of the rocket, given by the states pickle wil be    #
        # send to the leader who will organize the replication step to each computers     #
        # =============================================================================== #

        print("Trying to replicate state at timestep {} the state {}".format(timestep, states[timestep]))

        # Check the leader to contact: if None, a computer of the list is randomly choice
        if id_leader is None:
            id_leader = select_leader(servers)
            print('new random leader. Id: {}'.format(id_leader))

        # Prepare the request:
        req = {
            'obj': 'decide_on_state',
            'time_step': timestep
        }
        for ky in states[timestep].keys():
            req[ky] = states[timestep][ky]
        # Send the request to the given node:
        reply = send_post(id_leader, 'decide_on_state', states[timestep], TIMEOUT=0.075)

        # Handle exceptions:
        # No answer
        if reply is None:
            # A time sleep to let the time to the system to get stable
            time.sleep(0.1)
            id_leader = None
            continue
        # If connection error:
        if isinstance(reply, dict):
            print('Connection error with leader id {}'.format(id_leader))
            id_leader = None
            continue
        # Translate the answer:
        reply = reply.json()
        if 'Error' in reply.keys():

            # if bad_leader: try again with the returned leader id
            if 'bad_leader' in reply['Error']:
                id_leader = reply['leader_id']
                print('leader redirection to id {}'.format(id_leader))
                timestep -= 1
                continue

            # If the system is in election process:
            if 'no_leader' in reply['Error']:
                id_leader = None
                continue
        if 'status' in reply.keys():
            if reply['status'] == 'succes':
                print('State replication: Succes')
            else:
                print('State replication: Echec. No majority of acknowledgment')

        # =============================================================================== #
        #                             Action Consensus step                               #
        #                                                                                 #
        # During this step, the leader will organize the consensus by the following way:  #
        #   1. A state consensus request is send to the leader                            #
        #   2. The leader send an action opinion request to each follower                 #
        #   3. Each follower reply the action that it mean to do                          #
        #   4. When more than the majority of nodes are are replying the same action,     #
        #       the leader orders to each node (and himself) to apply this action         #
        # =============================================================================== #

        print("Trying to make an action consensus at timestep {}".format(timestep))

        # Prepare the request:
        req = {'to_do': 'action_consensus'}
        # Send the request
        reply = send_post(id_leader, 'action_consensus', req, TIMEOUT=0.075)

        # Handle exceptions:
        # No answer
        if reply is None:
            # A time sleep to let the time to the system to get stable
            time.sleep(0.1)
            id_leader = None
            continue
        # If connection error:
        if isinstance(reply, dict):
            print('Connection error with leader id {}'.format(id_leader))
            id_leader = None
            continue
        # Translate the answer:
        reply = reply.json()
        if 'Error' in reply.keys():

            # if bad_leader: try again with the returned leader id
            if 'bad_leader' in reply['Error']:
                id_leader = reply['leader_id']
                timestep -= 1
                print('Leader redirection to id {}'.format(id_leader))
                continue

            # If the system is in election process:
            if 'no_leader' in reply['Error']:
                id_leader = None
                continue
            # Others type of errors:
            else:
                print('Error during action consensus process. Reply: {}'.format(reply))

        # If a valid state is reply
        if 'pitch' in reply.keys():
            print('Action consensus succes: {}'.format(reply))

        # =============================================================================== #
        #                             True answer counting                                #
        #                                                                                 #
        # Compare consensus actions with the list                                         #
        # =============================================================================== #

        action = actions[timestep]
        is_same = True
        original = actions[timestep]
        for ky in to_compare_keys:
            if original[ky] != action[ky]:
                is_same = False
        total_asw += 1

        if is_same:
            good_asw += 1
        print('CONSENSUS-SCORE: good action: {} / {}'.format(good_asw, total_asw))