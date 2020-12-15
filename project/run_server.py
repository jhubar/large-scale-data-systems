#! /usr/bin/env python
# coding: utf-8
import argparse
import sys
import json
from flask import Flask, request, jsonify, redirect
import logging
from Raft.Server.raft import Raft
from Raft.Server.state import State
from Raft.Server.computers import *

raft = None

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
    return jsonify(raft.decide_vote(request_json))

@app.route('/append_entries', methods=['POST'])
def append_entries():
    request_json = request.json
    return jsonify(raft.receive_leader_command(request_json))

@app.route('/command', methods=['POST'])
def get_command():
    if raft.state is State.FOLLOWER:
        leader_id = raft.votedFor
        return redirect("http://{}:{}/command".format(leader_id['host'],\
                                                      leader_id['port']),\
                        code=307)
    elif raft.state is State.CANDIDATE:
        return jsonify(False)
    else:
        return jsonify(raft.add_entries())


def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("--flight-computers-type", type=int, default=0, help="The type of flight computers (Normal=0 or Random=1). (default: 0)")
    parser.add_argument("--port", type=int, default=8000, help="The port of the server (default: 8000).")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="The IP addresses of the server (default: localhost)")
    return parser.parse_known_args()

def get_peers(raft_id):
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
            return None

    return peers

if __name__ == '__main__':
    (arguments, _) = parse_arguments()
    # Initialise the raft id
    raft_id = {'host': arguments.host, 'port': arguments.port}
    print("Starting to run the raft server http://{}:{}/".format(raft_id['host'], raft_id['port']))
    # Get the peers of the raft
    peers = get_peers(raft_id)
    if peers is None:
        sys.exit()
    # Initialise the flight computers and the raft. Then start the raft
    fc = None
    if arguments.flight_computers_type == 0:
        fc = FlightComputer
    else:
        fc = allocate_random_flight_computer()
    raft = Raft(fc, raft_id, peers)
    raft.start_raft()
    # Run Flask app
    app.run(debug=False, host=arguments.host, port=arguments.port)
