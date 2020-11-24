# Flask for each FLight Computer. The raft server implements Raft Consensus Algorithm

# TODO: Valeur index

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
import time

class Raft:
    def __init__(self, rocket, id, peers=[]):
        # Common to all raft server
        self.state = State.FOLLOWER
        self.currentTerm = 1
        self.votedFor = None
        self.log = []
        self.commitIndex = 0
        self.lastApplied = 0
        # Only Leader handles these variables
        self.nextIndex = self._init_next_index(peers)
        self.matchIndex = self._init_match_index(peers)
        # Flight Computer object
        self.rocket = rocket
        # Flask information
        self.id = id
        self.election_timer = RaftRandomTime(0.15, 0.3, self.time_out)
        # Raft information
        self.vote = 0
        self.majority = math.floor((len(peers) + 1) / 2) + 1
        for peer in peers:
            self.rocket.add_peer(peer)
        # Various variable (Locks, etc)
        self.lock_append_entries = threading.Lock()
        self.become_leader_lock = threading.Lock()
        print("Sleeping for 5 s...")
        time.sleep(5)

    def _init_next_index(self, peers):
        nextIndex = {}
        for peer in peers:
            # TODO: maybe 0
            nextIndex[(peer['host'], peer['port'])] = 1
        return nextIndex

    def _init_match_index(self, peers):
        matchIndex = {}
        for peer in peers:
            matchIndex[(peer['host'], peer['port'])] = 0
        return matchIndex

    def start_raft(self):
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
            print("The raft server http://{}:{}/ has an election timeout".format(self.id['host'], self.id['port']))
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
            for peer in peers:
                threading.Thread(target=self.run_election,
                                 args=(self.currentTerm,
                                        self._last_log_index(),
                                        self._last_log_term(),
                                        peer)).start()

    def run_election(self, currentTerm, lastLogIndex, lastLogTerm, peer):
        message = VoteRequest(currentTerm, self.id, lastLogIndex, lastLogTerm).__dict__
        # Post method
        url = "vote_request"
        # Need to loop while state is CANDIDATE and currentTerm == self.currentTerm
        while self.state is State.CANDIDATE and currentTerm is self.currentTerm:
            reply = send_post(peer, url, message)
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
                        self._become_follower(reply.json()['term'])
                return

    def _become_follower(self, term):
        """
        Cancel the election of a candidate
        """
        # Update variables and then reset the election time
        self.currentTerm = term
        self.state = State.FOLLOWER
        self.votedFor = None
        self.vote = 0
        self.reset_election_timer()
        if self.lock_append_entries.locked():
            self.lock_append_entries.release()
        if self.become_leader_lock.locked():
            self.become_leader_lock.release()

    def _become_leader(self):
        self.become_leader_lock.acquire()
        if self.state == State.CANDIDATE:
            print("Raft server {}:{} is now a leader. Congrats.".format(self.id['host'], self.id['port']))
            # Update variables
            self.state = State.LEADER
            for peer in self.rocket.get_peers():
                self.nextIndex[(peer['host'], peer['port'])] = self.commitIndex + 1
                self.matchIndex[(peer['host'], peer['port'])] = self.commitIndex
                threading.Thread(target=self._send_append_entries,
                                 args=(peer,)).start()
            self.become_leader_lock.release()


    def decide_vote(self, request_json):
        """
        Raft server deciding a vote request from a candidate
        """
        answer = None

        if self.currentTerm < request_json['term']:
            # Ensure that the raft server stays or become a follower in this case
            self._become_follower(request_json['term'])

        if request_json['term'] == self.currentTerm and \
        self._check_consistent_vote(request_json['candidateID']) and \
        self._check_election_log_safety(request_json['lastLogTerm'], \
                                       request_json['lastLogIndex']):
            # The raft server grant this candidate
            print("Raft server http://{}:{} voted for the raft server http://{}:{}"\
            .format(self.id['host'],
                    self.id['port'],
                    request_json['candidateID']['host'],
                    request_json['candidateID']['port']))
            answer = jsonify(VoteAnswer(True,
                                        self.currentTerm).__dict__)
            self._grant_vote(request_json['term'], request_json['candidateID'])
        else:
            # The FOLLOWER raft server cannot grant this candidate
            answer = jsonify(VoteAnswer(False,
                                        self.currentTerm).__dict__)

        return answer

    def _grant_vote(self, term, candidateID):
        """
        Accepts the vote
        update the term
        set the voteFor at candidateID (Allow to avoid double vote)
        reset the timer 'election timer'
        """
        self.currentTerm = term
        self.votedFor = candidateID
        self.election_timer.reset()

    def _check_consistent_vote(self, candidateID):
        if self.votedFor is None or self.votedFor is candidateID:
            # The raft server has not voted yet, or already voted for this candidate
            return True
        # The raft server cannot vote for this candidate
        return False

    def _check_election_log_safety(self, lastLogTerm, lastLogIndex):
        """
        Check if a the last log of the raft server is as up-to-date than the last
        log of the candidate.
        return True if last log is up-to-date with the candidate
               False otherwise
        """
        if self.log:
            if lastLogTerm > self._last_log_term() or\
               (lastLogTerm >= self._last_log_term() and\
               lastLogIndex >= self._last_log_index()):
               return True
            else:
               return False
        return True


    """
    AppendEntries Handler
    """
    def execute_commande(self, request_json):
        self.lock_append_entries.acquire()
        self.log.append(self.currentTerm, request_json['command'])
        self.lock_append_entries.release()

    def _send_append_entries(self, peer):

        """
            while i am leader:
                Take lock
                send append_entries
                release lock
        """
        url = 'append_entries'
        while self.state == State.LEADER:
            # Take lock just for atomic reading in self.log
            prevLogIndex = min(self.nextIndex[self._get_id_tuple(peer)], self._last_log_index())
            self.nextIndex[self._get_id_tuple(peer)] = prevLogIndex
            message = AppendEntriesRequest(self.currentTerm,
                                           self.id,
                                           prevLogIndex - 1,
                                           self.log[prevLogIndex -1].term if self.log else 1,
                                           self.log,
                                           self.commitIndex).get_message()
            reply = send_post(peer, url, message)
            # TODO: Analyser réponse follower
            if reply is not None and self.state is State.LEADER:
                self._append_entries_answer(reply.json(), peer)

    def _append_entries_answer(self, reply_json, peer):
        """
        when leader re-send
        """
        if reply_json['term'] > self.currentTerm:
            self._become_follower(reply_json['term'])
        elif self.state == State.LEADER and reply_json['term'] == self.currentTerm:
            if reply_json['success']:
                 self.nextIndex[self._get_id_tuple(peer)] =\
                  self.nextIndex[self._get_id_tuple(peer)] + 1
            else:
                 self.nextIndex[self._get_id_tuple(peer)] =\
                    max(1, self.nextIndex[self._get_id_tuple(peer)] - 1)


    def _store_entries(self, prevLogIndex, entries, commitIndex):
        index = prevLogIndex
        for json_log in entries:
            log_received = Log(json_log['term'], json_log['command'])
            index = index + 1
            if self.log[index].term is not log_received.term:
                self.log.append(log_received)

        self.commitIndex = min(commitIndex, index)
        return index


    def receive_leader_command(self, request_json):
        if request_json['term'] > self.currentTerm:
            self._become_follower(request_json['term'])
        if request_json['term'] < self.currentTerm:
            return AppendEntriesAnswer(self.currentTerm, False, -1).__dict__
        else:
            index = 0
            prevLogIndex = request_json['prevLogIndex']
            prevLogTerm = request_json['prevLogTerm']
            success = prevLogIndex == 0 or \
             (prevLogIndex <= self._last_log_index() and \
             self.log[prevLogIndex].term == prevLogTerm )
            if success:
                # Reset timer only if success
                self.reset_election_timer()
                index = self._store_entries(prevLogIndex,
                                            request_json['entries'],
                                            request_json['commitIndex'])
            return AppendEntriesAnswer(self.currentTerm, success, index).__dict__



    """
    Various function
    """
    def _last_log_index(self):
        return len(self.log) + 1

    def _last_log_term(self):
        return self.log[-1].term if self.log else 1

    def _get_id_tuple(self, peer):
        return (peer['host'], peer['port'])
