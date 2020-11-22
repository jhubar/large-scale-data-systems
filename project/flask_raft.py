#! /usr/bin/env python
# coding: utf-8
import argparse
import sys
import json
from flask import Flask, request, jsonify
import logging
from Raft.Server.server import Server
from Raft.RPC.request_vote import *
from Raft.RPC.append_entries import *
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
    answer = None
    if server.currentTerm > request_json['term']:
        # If the server has a better term than the candidate
        answer = jsonify(VoteAnswer(False,
                                    server.currentTerm).__dict__)
    elif server.check_consistent_vote(request_json['candidateID']) and \
        server.check_election_log_safety(request_json['lastLogTerm'], request_json['lastLogIndex']):
        # The server grant this candidate
        print("Server http://{}:{} voted for server http://{}:{}"\
        .format(server.id['host'],
                server.id['port'],
                request_json['candidateID']['host'],
                request_json['candidateID']['port']))
        answer = jsonify(VoteAnswer(True,
                                    server.currentTerm).__dict__)
        server.grant_vote(request_json['term'], request_json['candidateID'])
    else:
        # If
        answer = jsonify(VoteAnswer(False,
                                    server.currentTerm).__dict__)
    return answer

@app.route('/append_entries', methods=['POST'])
def heartbeat_request():
    # The server receives a heartbeat from a "leader".
    request_json = request.json
    #print(request_json)
    server.reset_timer()
    """
    if server.currentTerm > request_json['term']:
        return jsonify(AppendEntriesAnswer(server.currentTerm, False).__dict__)
    elif server.check_log_index(request_json['lastLogIndex']):
        return jsonify(AppendEntriesAnswer(server.currentTerm, False).__dict__)
    elif server.check_existing_entry(request_json['entries']):
    """


    return jsonify(False)

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
