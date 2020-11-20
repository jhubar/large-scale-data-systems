# Flask for each FLight Computer. The server implements Raft Consensus Algorithm

from .state import State
from ..State_Machine.log import Log
from ..Abstraction.timer import RaftRandomTime, RaftTimer
from ..RPC.request_vote import VoteAnswer, VoteRequest
from ..Abstraction.send import *
from flask import Flask, request, jsonify
import json
import threading
import logging

app = Flask(__name__)
# disable flask logging
'''log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)'''

class Server:
    def __init__(self, rocket, host, port):
        # Common to all server
        self.state = State.FOLLOWER
        self.currentTerm = 0
        self.votedFor = None
        self.log = []
        self.commitIndex = 0
        self.lastApplied = 0
        # Only Leader handles these variables
        self.nextIndex = []
        self.matchIndex = []
        # Flight Computer object
        self.rocket = rocket
        # Flask information
        self.candidateID = (host, port)
        self.election_timer = RaftRandomTime(5, 25, self.time_out)
        # Raft information
        self.vote = 0
        self.majority = None

    def start_server(self, peers=[]):
        print('Starting {}:{}'.format(self.candidateID[0], self.candidateID[1]))
        for peer in peers:
            if peer is not self.candidateID:
                self.rocket.add_peer(peer)
        self.majority = ((len(peers) + 1) / 2) + 1
        self.election_timer.start()
        threading.Thread(target=self.run_server).start()

    def run_server(self):
        app.run(debug=False, host=self.candidateID[0], port=self.candidateID[1])

    def init_vote(self):
        self.vote = 0

    def time_out(self):
        self.init_vote()
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
            for peerCandidateID in peers:
                (lastLogIndex, lastLogTerm) = (self.log[-1].index, self.log[-1].term) if self.log else (0,0)
                threading.Thread(target=self.run_election,
                                 args=(self.currentTerm,
                                        lastLogIndex,
                                        lastLogTerm,
                                        peerCandidateID)).start()

    def run_election(self, currentTerm, lastLogIndex, lastLogTerm, peerCandidateID):
        message = VoteRequest(currentTerm, self.candidateID, lastLogIndex, lastLogTerm).__dict__
        # Post method
        url = "vote_request"
        # Need to loop while state is CANDIDATE and currentTerm == self.currentTerm
        while self.state is State.CANDIDATE and currentTerm is self.currentTerm:
            reply = send_post(peerCandidateID, url, message)
            if reply is not None:
                if reply.json()['voteGranted']:
                    ''' A follower said yes to this candidate '''
                    self.vote = self.vote + 1
                    if self.vote >= self.majority:
                        print("Server {}:{} is now a leader. Congrats".format(self.candidateID[0], self.candidateID[1]))
                        self.state = State.LEADER
                else:
                    ''' A follower said No to this candidate '''
                    if reply.json()['term'] > self.currentTerm:
                        self.currentTerm = reply.json()['term']
                        self.state = State.FOLLOWER
                break

        #print("Election of port = {} term = {} finished".format(self.candidateID[1], currentTerm))

    @app.route('/vote_request', methods=['POST'])
    def vote_request():
        print("I DONT WANT TO VOTE")
        print(request.json)
        return jsonify(VoteAnswer(True, self.currentTerm, self.candidateID, 0, 0).__dict__)


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
