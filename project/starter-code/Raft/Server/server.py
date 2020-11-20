# Flask for each FLight Computer. The server implements Raft Consensus Algorithm

from .state import State
from ..State_Machine.log import Log
from ..Abstraction.timer import RaftRandomTime, RaftTimer
from ..RPC.request_vote import VoteAnswer, VoteRequest
from flask import Flask, request, jsonify
import json
import threading
import requests

app = Flask(__name__)

class Server:
    def __init__(self, rocket, host, port, peers=[]):
        # Common to all server
        self.state = State.FOLLOWER
        self.currentTerm = 0
        self.votedFor = None
        self.log = []
        self.commitIndex = 0
        self.lastApplied = 0
        # Only Leader plays with these variables
        self.nextIndex = []
        self.matchIndex = []
        # Flight Computer object
        self.rocket = rocket
        # Flask information
        self.candidateID = (host, port)
        self.vote = 0
        self.election_timer = RaftRandomTime(5, 10, self.time_out)
        for peer in peers:
            self.rocket.add_peer(peer)

    def start_server(self, peers=[]):
        print('Starting {}:{}'.format(self.candidateID[0], self.candidateID[1]))
        self.election_timer.start()
        threading.Thread(target=self.launch_server).start()

    def launch_server(self):
        app.run(debug=False, host=self.candidateID[0], port=self.candidateID[1])

    @app.route('/')
    def hello_world():
        print("hey")
        return '<p> Hello World </p>'

    def init_vote(self):
        self.vote = 0

    def time_out(self):
        self.init_vote()
        print("Time out i am (port: {}) asking to be a leader".format(self.candidateID[1]))
        if self.state is State.LEADER:
            return
        else:
            # Goes to CANDIDATE state
            self.state = State.CANDIDATE
            # Increment current term
            self.currentTerm = self.currentTerm + 1
            # Vote for itself
            self.vote = self.vote + 1
            # Start the timer election
            self.election_timer.reset()

            peers = self.rocket.get_peers()
            for (host, port) in peers:
                jsonPayload = json.dumps(VoteRequest(self.currentTerm,
                                                     self.candidateID,
                                                     self.log[-1].index if self.log else 0,
                                                     self.log[-1].term if self.log else 0).__dict__)
                print(jsonPayload)
                #requests.post('http:{}:{}/requestVote'.format(host, port), data=jsonPayload)

    """
    def check_request_vote(self):
        voteBody = resquests.json
        (candidate_host, candidate_port) = voteBody['candidateID'][1]
        if voteBody['term'] < self.currentTerm:
            self.aws(self,False)
            requests.get('http:{}:{}/replyVote'.format(candidate_host, candidate_port),
                         data=json_vote_answer)
            return

        if  not self.log\
            and self.votedFor is None \
            or self.votedFor is votedBody['candidateID']\
            and (self.log[-1].term, self.log[-1].index) is (voteBody['lastLogTerm'], voteBody['lastLogIndex']):
            self.aws(self,True)

    @app.route('/replyVote', methods=['GET'])
    def candidate_vote_reply(self):
        pass


    def add_peer(self, peer):
        self.rocket.add_peer(peer)

    def starting_lection(self):
        pass

    def election_procedure(self):
        pass

    @app.route('/appendEntries/')
    def receiver_implementation(self):
        content = request
        if content['term'] < content['currentTerm']
    """
