# Flask for each FLight Computer. The raft server implements Raft Consensus Algorithm

from .state import State
from collections import Counter
from ..State_Machine.log import Log
from ..Abstraction.timer import RaftRandomTime, RaftTimer
from ..RPC.request_vote import VoteAnswer, VoteRequest
from ..RPC.append_entries import *
from ..Abstraction.send import *
import json
import math
import threading
import logging
import time

class Raft:
    def __init__(self, rocket, id, peers=[]):
        # Common to all raft server
        self.state = State.FOLLOWER
        self.currentTerm = 0
        self.votedFor = None
        self.log = []
        self.commitIndex = 0
        self.lastApplied = 0
        # Flight Computer object
        self.rocket = rocket
        # Flask information
        self.id = id
        # Raft information
        self.election_timer = RaftRandomTime(4.5, 9, self.time_out)
        self.vote = 0
        self.majority = math.floor(len(peers) / 2) + 1
        for peer in peers:
            self.rocket.add_peer(peer)
        # Various variable (Locks, etc)
        self.lock_append_entries = threading.Lock()
        self.become_leader_lock = threading.Lock()
        self.update_commit_lock = threading.Lock()
        # Only Leader handles these variables
        self.nextIndex = self._init_next_index(peers)
        self.matchIndex = self._init_match_index(peers)
        self.append_entries_timer = self._init_append_entries_timer(peers)

    def _init_next_index(self, peers):
        nextIndex = {}
        nextIndex[self._get_id_tuple(self.id)] = 1
        for peer in peers:
            # TODO: maybe 0
            nextIndex[self._get_id_tuple(peer)] = 1
        return nextIndex

    def _init_match_index(self, peers):
        matchIndex = {}
        matchIndex[self._get_id_tuple(self.id)] = 0
        for peer in peers:
            matchIndex[self._get_id_tuple(peer)] = 0
        return matchIndex

    def _init_append_entries_timer(self, peers):
        append_entries_timer = {}
        for peer in peers:
            append_entries_timer[self._get_id_tuple(peer)] = \
                RaftTimer(1.5, self._send_append_entries, args=(peer,))
        return append_entries_timer

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
            answer = VoteAnswer(True, self.currentTerm).__dict__
            self._grant_vote(request_json['term'], request_json['candidateID'])
        else:
            # The FOLLOWER raft server cannot grant this candidate
            answer = VoteAnswer(False, self.currentTerm).__dict__

        return answer

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
        if self.update_commit_lock.locked():
            self.update_commit_lock.release()

    def _become_leader(self):
        self.become_leader_lock.acquire()
        if self.state == State.CANDIDATE:
            print("Raft server {}:{} is now a leader. Congrats.".format(self.id['host'], self.id['port']))
            # Update variables
            self.state = State.LEADER
            for peer in self.rocket.get_peers():
                self.nextIndex[self._get_id_tuple(peer)] = self._last_log_index() + 1
                self.matchIndex[self._get_id_tuple(peer)] = 0
                self.append_entries_timer[self._get_id_tuple(peer)].start()
            self.become_leader_lock.release()

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
        if lastLogTerm > self._last_log_term() or\
           (lastLogTerm >= self._last_log_term() and\
           lastLogIndex >= self._last_log_index()):
           return True
        else:
           return False


    """
    AppendEntries Handler
    """

    def execute_commande(self, request_json):
        self.lock_append_entries.acquire()
        self.log.append(Log(self.currentTerm, request_json['command']))
        self.matchIndex[self._get_id_tuple(self.id)] =\
            self.matchIndex[self._get_id_tuple(self.id)] + 1
        self.nextIndex[self._get_id_tuple(self.id)] =\
            self.nextIndex[self._get_id_tuple(self.id)] + 1
        self.lock_append_entries.release()
        # TODO: Normaly it should return something else here. (Like the results of the command)
        return True

    def receive_leader_command(self, request_json):
        print('Received append entries: {}'.format(request_json))
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
             self._get_term_by_index(prevLogIndex) == prevLogTerm)
            if success:
                # Reset timer only if success
                self.reset_election_timer()
                index = self._store_entries(prevLogIndex,
                                            request_json['entries'],
                                            request_json['commitIndex'])
            return AppendEntriesAnswer(self.currentTerm, success, index).__dict__

    def _store_entries(self, prevLogIndex, entries, commitIndex):
        index = prevLogIndex
        for json_log in entries:
            log_received = Log(json_log['term'], json_log['command'])
            self.log.insert(index, log_received)
            index = index + 1
            self.log = self.log[0:index]

        self.commitIndex = min(commitIndex, index)
        return index

    def _send_append_entries(self, peer):
        url = 'append_entries'
        if self.state == State.LEADER:
            prevLogIndex = self.nextIndex[self._get_id_tuple(peer)]
            message = AppendEntriesRequest(self.currentTerm,
                                           self.id,
                                           prevLogIndex - 1,
                                           self._get_term_by_index(prevLogIndex - 1),
                                           self.log[(prevLogIndex - 1):len(self.log)],
                                           self.commitIndex).get_message()
            reply = send_post(peer, url, message)
            if reply is not None and self.state is State.LEADER:
                self._append_entries_answer(reply.json(), peer)
            self.append_entries_timer[self._get_id_tuple(peer)].reset()


    def _append_entries_answer(self, reply_json, peer):
        """
        when leader receives follower answer
        """
        if reply_json['term'] > self.currentTerm:
            self._become_follower(reply_json['term'])
        elif self.state == State.LEADER and reply_json['term'] == self.currentTerm:
            if reply_json['success']:
                if self.nextIndex[self._get_id_tuple(peer)] < reply_json['index'] + 1:
                     self.nextIndex[self._get_id_tuple(peer)] =\
                                                    reply_json['index'] + 1
                     self.matchIndex[self._get_id_tuple(peer)] = reply_json['index']
                     self._update_commit(reply_json['index'])
            else:
                 self.nextIndex[self._get_id_tuple(peer)] =\
                    max(1, self.nextIndex[self._get_id_tuple(peer)] - 1)


    def _update_commit(self, index):
        self.update_commit_lock.acquire()
        if index > self.commitIndex:
            count = len([value for value in self.matchIndex.values() if value >= index])
            if count >= self.majority and \
                    self._get_term_by_index(index) == self.currentTerm:
                self.commitIndex = index
        self.update_commit_lock.release()

    """
    Various function
    """
    def _last_log_index(self):
        return len(self.log)

    def _last_log_term(self):
        return self.log[-1].term if self.log else 0

    def _get_term_by_index(self, index):
        if index == 0:
            return 0
        return self.log[index - 1].term

    def _get_id_tuple(self, peer):
        return (peer['host'], peer['port'])
