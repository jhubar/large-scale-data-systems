#! /usr/bin/env python
# coding: utf-8
import argparse
import sys
import json
from flask import Flask, request, jsonify
import logging
from Raft.Server.server import Server
from Raft.Server.state import State
import pickle
from starter_code.computers import FlightComputer

server = None

app = Flask(__name__)
# disable flask logging
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)


@app.route('/vote_request', methods=['POST'])
def vote_request():
    """
    Rules:  - Reply false if term < currentTerm
            - If votedFor is null or candidateId, and candidate’s log is at
              least as up-to-date as receiver’s log, grant vote
    """
    request_json = request.json
    return server.decide_vote(request_json)

@app.route('/append_entries', methods=['POST'])
def append_entries():
    request_json = request.json
    return server.receive_leader_command(request_json)

@app.route('/command', methods=['GET'])
def get_command():
    if server.state is State.FOLLOWER:
        leader_id = server.votedFor
        return redirect("http://{}:{}/command".format(leader_id['host'],\
                                                      leader_id['port']),\
                        code=302)
    elif server.state is State.CANDIDATE:
        return jsonify(False)
    else:
        return server.execute_commande(request.json)

# Load the pickle files
actions = pickle.load(open("data/actions.pickle", "rb"))
states = pickle.load(open("data/states.pickle", "rb"))
timestep = 0

def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("--flight-computers-type", type=int, default=0, help="The type of flight computers (Normal=0 or Random=1). (default: 0)")
    parser.add_argument("--port", type=int, default=8000, help="The port of the server (default: 8000).")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="The IP addresses of the server (default: localhost)")
    return parser.parse_known_args()

def get_peers(server_id):
    peers = []
    with open('peering.json') as peers_file:
        peering_json = json.load(peers_file)
        try:
            # Check if file is ok
            peers = peering_json['peers']
            # Try to remove its own server_id in peers
            peers.remove(server_id)
        except Exception as e:
            print("The file peering.json contains erroneous data...")
            return None

    return peers

if __name__ == '__main__':
    (arguments, _) = parse_arguments()
    # Initialise the Server id
    server_id = {'host': arguments.host, 'port': arguments.port}
    print("Starting to run the server http://{}:{}/".format(server_id['host'], server_id['port']))
    # Get the peers of the Server
    peers = get_peers(server_id)
    if peers is None:
        sys.exit()
    # Initialise the flight computers and the server. Then start the server
    fc = FlightComputer(states[timestep])
    server = Server(fc, server_id, peers)
    server.start_server()
    # Run Flask app
    app.run(debug=False, host=arguments.host, port=arguments.port)
