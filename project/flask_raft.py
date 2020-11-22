#! /usr/bin/env python
# coding: utf-8
import argparse
from flask import Flask, request, jsonify
import logging
import csv
from Raft.Server.server import Server
from Raft.RPC.request_vote import *
import pickle
from starter_code.computers import FlightComputer

server = None

app = Flask(__name__)
# disable flask logging
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

@app.route('/')
def h():
    return "hello world"

@app.route('/vote_request', methods=['POST'])
def vote_request():
    print("I DONT WANT TO VOTE")
    print(request.json)
    return jsonify(VoteAnswer(True, server.currentTerm, server.candidateID, 0, 0).__dict__)

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

def get_peers():
    peers = []
    with open('peering.csv') as peering_file:
        csv_reader = csv.reader(peering_file, delimiter=',')
        line = 0
        for row in csv_reader:
            row_tuple = tuple(row)
            if line == 0:
                line = line + 1
                if row_tuple != ('host','port'):
                    print('The csv file for handling peering is not correct. Aborting...')
                    exit(-1)
            else:
                if row_tuple != (arguments.host, str(arguments.port)):
                    peers.append(row_tuple)
    return peers

if __name__ == '__main__':
    (arguments, _) = parse_arguments()
    print("Running server http://{}:{}/".format(arguments.host, arguments.port))
    peers = get_peers()
    fc = FlightComputer(states[timestep])
    server = Server(fc, arguments.host, arguments.port, peers)
    server.start_server()
    app.run(debug=False, host=arguments.host, port=arguments.port)
