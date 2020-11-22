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

class Server:
    def __init__(self, rocket, host, port, peers=[]):
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
        self.majority = ((len(peers) + 1) / 2) + 1
        for peer in peers:
            self.rocket.add_peer(peer)

    def start_server(self):
        self.election_timer.start()

    def run_server(self):
        app.run(debug=False, host=self.candidateID[0], port=self.candidateID[1])

    def init_vote(self):
        self.vote = 0

    def time_out(self):
        print("The server http://{}:{}/ has an election timeout".format(self.candidateID[0], self.candidateID[1]))
        self.init_vote()
        if self.state is State.LEADER:
            return
        else:
            # Goes to CANDIDATE state
            self.state = State.CANDIDATE
            # Increment current term
            self.currentTerm = self.currentTerm + 1
            # Vote for itself
            self.votedFor = self.candidateID
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
                        self._become_leader()
                else:
                    ''' A follower said No to this candidate '''
                    if reply.json()['term'] > self.currentTerm:
                        self.currentTerm = reply.json()['term']
                        self.state = State.FOLLOWER
                return

    def _become_leader(self):
        if self.state != State.LEADER:
            self.state = State.LEADER
            print("Server {}:{} is now a leader. Congrats".format(self.candidateID[0], self.candidateID[1]))
            # TODO: Beginning heartbeat (AppendEntries),
        self.votedFor = None


    def vote_granted(self, term, candidateID):
        """
        Accepts the vote
        update the term
        update the candidateID
        reset the timer

        """
        self.currentTerm = term
        self.votedFor = tuple(candidateID)
        self.election_timer.reset()

    def check_log_safety(self, lastLogTerm, lastLogIndex):
        """
        Check if a the last log of the server is as up-to-date than the last
        log of the candidate.
        return True if last log is up-to-date with the candidate
               False otherwise
        """
        if self.log:
            if self.log[-1].term <= lastLogTerm \
            and self.log[-1].index <= lastLogIndex:
                return  True
            else:
                return  False
        else:
            return True

    def commitmend_extraCondition(self):
        """
        Election Safety:
        Leader Append-Only:
        Log Matching:
        Leader Completeness:
        State Machine Safety:
        """
        pass
