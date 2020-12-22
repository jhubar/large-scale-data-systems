import argparse
import sys
import json
from flask import Flask, request, jsonify, redirect
import logging
from Server.raft import Raft
from Server.computer import *
from Tools.tools import *
import pickle

# Init Flask server
app = Flask(__name__)

@app.route('/heartbeat', methods=['POST'])
def get_heartbeat():
    asw = request.json

    return jsonify(raft.process_heartbeat(asw))

@app.route('/vote_request', methods=['POST'])
def vote_request():
    """
    Rules:  - Reply false if term < currentTerm
            - If votedFor is null or candidateId, and candidate’s log is at
              least as up-to-date as receiver’s log, grant vote
    """
    request_json = request.json
    asw = raft.process_ask_for_vote(request_json)
    return jsonify(asw)

@app.route('/decide_on_state', methods=['POST'])
def decide_on_state():
    """
    This method receive a post request from the client (generally
    test_consensus.py) to organize the state replication to each
    others nodes. If the node is not the leader, the request is
    send to the the leader if there is one or return a no leader
    error to the client
    """
    # If the node is follower:
    if raft.state == FOLLOWER:
        reply = {
            'Error': 'bad_leader',
            'leader_id': raft.leader_following
        }
        return jsonify(reply)
    # If the system is in election process:
    if raft.state == CANDIDATE:
        reply = {
            'Error': 'no_leader',
        }
        return jsonify(reply)

    # If the node is the leader:
    else:
        reply = raft.state_consensus(request.json)

        return jsonify(reply)

@app.route('/replic_state', methods=['POST'])
def replic_state():
    """
    This method apply the given state to the node
    """
    # Check if acceptable state:
    if not raft.fc.acceptable_state(request.json):
        reply = {
            'Error': 'Not_acceptable'
        }
        return jsonify(reply)
    else:
        raft.fc.deliver_state(request.json)
        reply = {
            'ack': True
        }
        return jsonify(reply)

@app.route('/action_consensus', methods=['POST'])
def action_consensus():
    """
    This method organize the action consensus and the
    action delivery
    """
    # If the node is follower:
    if raft.state == FOLLOWER:
        reply = {
            'Error': 'bad_leader',
            'leader_id': raft.leader_following
        }
        return jsonify(reply)
    # If the system is in election process:
    if raft.state == CANDIDATE:
        reply = {
            'Error': 'no_leader',
        }
        return jsonify(reply)

    # If the node is the leader:
    else:
        reply = raft.action_consensus()
        print(reply)

        return jsonify(reply)


@app.route('/what_to_do', methods=['POST'])
def what_to_do():
    """
    This method receive the request from the leader
    who ask to the node what action it mean to do
    """
    action = raft.fc.sample_next_action()

    return jsonify(action)

@app.route('/apply_action', methods=['POST'])
def apply_action():
    """
    This method tell to the follower to apply
    the action who come from the action consensus
    """
    # Deliver the action
    raft.fc.deliver_action(request.json)

    reply = {'state': 'deliver'}

    return jsonify(reply)



def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("--flight-computers-type", type=int, default=0, help="The type of flight computers (Normal=0 or Random=1). (default: 0)")
    parser.add_argument('--type', type=int, default=-1, help="Specifiy the type of bad computer to create: "
                                                             "Full throttle: 0, Random throttle: 1,"
                                                             "Slow: 2, Crashing: 3")
    parser.add_argument("--port", type=int, default=8000, help="The port of the server (default: 8000).")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="The IP addresses of the server (default: localhost)")
    return parser.parse_known_args()

if __name__ == '__main__':

    # disable flask logging
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)

    # Unpickle files
    actions = pickle.load(open("data/actions.pickle", "rb"))
    states = pickle.load(open("data/states.pickle", "rb"))

    # Parse arguments
    (arguments, _) = parse_arguments()
    raft_id = {'host': arguments.host, 'port': arguments.port}
    print("Starting to run the raft server http://{}:{}/".format(raft_id['host'], raft_id['port']))
    # Get peers
    peers = []
    with open('peering.json') as peers_file:
        peering_json = json.load(peers_file)
        try:
            # Check if file is ok
            peers = peering_json['peers']
            # Try to remove its own raft_id in peers
            peers.remove(raft_id)
        except Exception as e:
            print("The file peering.json contains erroneous data...")
            print(e)
            sys.exit()
    # Keep only port as id
    peers_id = []
    for peer in peers:
        peers_id.append(peer['port'])

    # Initialise the flight computers
    fc = None

    # To manually select the type of faulty flight computer
    if arguments.type > -1:
        fc = allocate_specific_flight_computer(states[0], arguments.type)
        names = ['Full_Throttle', 'Random_Throttle', 'Slow', 'Crashing']
        fc.type = names[arguments.type]
    else:
        if arguments.flight_computers_type == 0:
            fc = FlightComputer(states[0])
        else:
            fc = allocate_random_flight_computer(states[0])


    # Init raft
    raft = Raft(fc, raft_id['port'], peers_id)
    raft.start_raft()
    print('Start a new {} flight computer'.format(fc.type))
    # Run Flask app
    app.run(debug=False, host=arguments.host, port=arguments.port)
