# Flask for each FLight Computer. The server implements Raft Consensus Algorithm

from .state import State
from ..State_Machine.log import Log
from ..Abstraction.timer import RaftRandomTime, RaftTimer
from ..RPC.request_vote import VoteAnswer, VoteRequest
from ..RPC.append_entries import *
from ..Abstraction.send import *
from flask import Flask, request, jsonify
import json
import math
import threading
import logging

class Server:
    def __init__(self, rocket, id, peers=[]):
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
        self.id = id
        self.election_timer = RaftRandomTime(2, 10, self.time_out)
        # Raft information
        self.vote = 0
        self.majority = math.floor((len(peers) + 1) / 2) + 1
        for peer in peers:
            self.rocket.add_peer(peer)

    def start_server(self):
        self.election_timer.start()

    def init_vote(self):
        self.vote = 0

    def reset_election_timer(self):
        self.election_timer.reset()

    """
    Election handler
    """
    def time_out(self):
        if self.state is State.LEADER:
            return
        else:
            # Start an election
            print("The server http://{}:{}/ has an election timeout".format(self.id['host'], self.id['port']))
            self.init_vote()
            # Goes to CANDIDATE state
            self.state = State.CANDIDATE
            # Increment current term
            self.currentTerm = self.currentTerm + 1
            # Vote for itself
            self.votedFor = self.id
            self.vote = self.vote + 1
            # Start the timer election
            self.election_timer.reset()
            # get the peers and send a VoteRequest
            peers = self.rocket.get_peers()
            for peerCandidateID in peers:
                threading.Thread(target=self.run_election,
                                 args=(self.currentTerm,
                                        self._last_log_index(),
                                        self._last_log_term(),
                                        peerCandidateID)).start()

    def run_election(self, currentTerm, lastLogIndex, lastLogTerm, peerCandidateID):
        message = VoteRequest(currentTerm, self.id, lastLogIndex, lastLogTerm).__dict__
        # Post method
        url = "vote_request"
        # Need to loop while state is CANDIDATE and currentTerm == self.currentTerm
        while self.state is State.CANDIDATE and currentTerm is self.currentTerm:
            reply = send_post(peerCandidateID, url, message)
            if reply is not None and self.state is State.CANDIDATE:
                if reply.json()['voteGranted']:
                    # A follower said yes to this candidate
                    self.vote = self.vote + 1
                    if self.vote >= self.majority:
                        self._become_leader()
                else:
                    # A follower said No to this candidate
                    if reply.json()['term'] > self.currentTerm\
                    and self.state is State.CANDIDATE:
                        # Update and reset some variables
                        self.cancel_server_election(reply.json()['term'])
                return

    def cancel_server_election(self, term):
        """
        Cancel the election of a candidate
        """
        # Update variables and then reset the election time
        self.currentTerm = term
        self.state = State.FOLLOWER
        self.votedFor = None
        self.vote = 0
        self.reset_election_timer()

    def _become_leader(self):
        if self.state == State.CANDIDATE:
            print("Server {}:{} is now a leader. Congrats.".format(self.id['host'], self.id['port']))
            # Update variables
            self.state = State.LEADER
            self.votedFor = None
            self._start_heartbeat_to_follower()

    def grant_vote(self, term, candidateID):
        """
        Accepts the vote
        update the term
        set the voteFor at candidateID (Allow to avoid double vote)
        reset the timer 'election timer'
        """
        self.currentTerm = term
        self.votedFor = candidateID
        self.election_timer.reset()

    def check_consistent_vote(self, candidateID):
        if self.votedFor is None or self.votedFor is candidateID:
            # The server has not voted yet, or already voted for this candidate
            return True
        return False

    def check_election_log_safety(self, lastLogTerm, lastLogIndex):
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

    """
    Heartbeat handler
    """
    def _start_heartbeat_to_follower(self):
        """
        Send hearbeat to follower at each time step
        """
        for peerCandidateID in self.rocket.get_peers():
            threading.Thread(target=self._send_heartbeat,
                             args=(peerCandidateID,)).start()


    def _send_heartbeat(self, peerCandidateID):
        url = "append_entries"
        while self.state is State.LEADER:
            message = AppendEntriesRequest(self.currentTerm,
                                           self.id,
                                           self._last_log_index(),
                                           self._last_log_term(),
                                           None,
                                           self.commitIndex).__dict__
            reply = send_post(peerCandidateID, url, message)

    """
    Various function
    """
    def _last_log_index(self):
        return self.log[-1].index if self.log else 0

    def _last_log_term(self):
        return self.log[-1].term if self.log else 0

    def commitmend_extraCondition(self):
        """
        Election Safety:
        Leader Append-Only:
        Log Matching:
        Leader Completeness:
        State Machine Safety:
        """
        pass
