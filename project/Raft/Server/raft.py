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
import pickle
import os, signal
import sys
from enum import Enum

# Load the pickle files
actions = pickle.load(open("data/actions.pickle", "rb"))
states = pickle.load(open("data/states.pickle", "rb"))

class Raft:
    def __init__(self, rocket, id, peers=[]):
        self.timestep = 0
        # Common to all raft server
        self.state = State.FOLLOWER
        self.currentTerm = 0
        self.votedFor = None
        self.log = []
        self.entry_buffered = None
        self.commitIndex = 0
        self.lastApplied = 0
        # Flight Computer object
        self.rocket = rocket(states[self.timestep])
        # Flask information
        self.id = id
        # Raft information
        self.election_timer = RaftRandomTime(0.45, 0.9, self.time_out, args=())
        self.vote = 0
        self.majority = math.ceil((len(peers) + 1) / 2)
        for peer in peers:
            self.rocket.add_peer(peer)
        # Various variable (Locks, etc)
        self.append_entries_lock = self._init_append_entries_lock(peers)
        self.add_entries_lock = threading.Lock()
        self.leader_command_lock = threading.Lock()
        self.become_leader_lock = threading.Lock()
        self.update_commit_lock = threading.Lock()
        # Only Leader handles these variables
        self.nextIndex = self._init_next_index(peers)
        self.matchIndex = self._init_match_index(peers)
        self.append_entries_timer = self._init_append_entries_timer(peers)
        # Boolean that allows to know if rocket ends
        self.is_done = False
        time.sleep(3)

    def _init_next_index(self, peers):
        nextIndex = {}
        nextIndex[self._get_id_tuple(self.id)] = 1
        for peer in peers:
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
                RaftTimer(0.225, self._send_append_entries, args=(peer,))
        return append_entries_timer

    def _init_append_entries_lock(self, peers):
        append_entries_lock = {}
        for peer in peers:
            append_entries_lock[self._get_id_tuple(peer)] = threading.Lock()
        return append_entries_lock

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
        self.entry_buffered = None
        self.reset_election_timer()
        # release lock if needed
        # if self.add_entries_lock.locked():
        #     self.add_entries_lock.release()
        # if self.leader_command_lock.locked():
        #     self.leader_command_lock.release()
        # if self.become_leader_lock.locked():
        #     self.become_leader_lock.release()
        # if self.update_commit_lock.locked():
        #     self.update_commit_lock.release()
        # for peer in self.rocket.get_peers():
        #     if self.append_entries_lock[self._get_id_tuple(peer)].locked():
        #         self.append_entries_lock[self._get_id_tuple(peer)].release()

    def _become_leader(self):
        with self.become_leader_lock:
            if self.state == State.CANDIDATE:
                print("Raft server {}:{} is now a leader. Congrats."\
                                        .format(self.id['host'], self.id['port']))
                # Update variables
                self.state = State.LEADER
                # Update next index and match index
                self.nextIndex[self._get_id_tuple(self.id)] =\
                                                    self.commitIndex + 1
                print(self.nextIndex[self._get_id_tuple(self.id)])
                self.matchIndex[self._get_id_tuple(self.id)] = self.commitIndex
                for peer in self.rocket.get_peers():
                    self.nextIndex[self._get_id_tuple(peer)] =\
                                                    self.commitIndex + 1
                    self.matchIndex[self._get_id_tuple(peer)] = 0
                    # Start heartbeat
                    self.append_entries_timer[self._get_id_tuple(peer)].start()
                # start append entries
                threading.Thread(target=self.add_entries).start()

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

    def receive_leader_command(self, request_json):
        self.leader_command_lock.acquire()
        answer = self._check_leader_command(request_json)
        if self.leader_command_lock.locked():
            self.leader_command_lock.release()
        return answer

    def _check_leader_command(self, request_json):
        #print("Server received command from leader : {}\n".format(request_json))
        if request_json['term'] > self.currentTerm:
            self._become_follower(request_json['term'])
        if request_json['term'] < self.currentTerm:
            return AppendEntriesAnswer(self.currentTerm,
                                       False,
                                       -1,
                                       False).__dict__
        else:
            # Check raft completeness
            index = 0
            prevLogIndex = request_json['prevLogIndex']
            prevLogTerm = request_json['prevLogTerm']
            success_raft = prevLogIndex == 0 or \
             (prevLogIndex <= self._last_log_index() and \
             self._get_term_by_index(prevLogIndex) == prevLogTerm)
            rocket_flag = False
            if success_raft:
                # Check the command
                index, rocket_flag =\
                            self._store_and_execute(prevLogIndex,
                                                    request_json['entries'],
                                                    request_json['commitIndex'])
                if rocket_flag:
                    # Reset only if rocket is ok with the current command
                    self.reset_election_timer()
            else:
                # Let the leader try to synchronize
                self.reset_election_timer()
            return AppendEntriesAnswer(self.currentTerm,
                                       success_raft,
                                       index,
                                       rocket_flag).__dict__

    def _store_and_execute(self, prevLogIndex, entries, commitIndex):
        # Initialise
        index = prevLogIndex
        rocket_flag = False
        self.log = self.log[0:index]
        # Check size of entries, empty entries means heartbeat
        if entries:
            # Check if more than 1 entry is sent
            if len(entries) > 1:
                # need to execute every entries except the last one
                # Because it means the first n - 1 command are replicated
                for json_log in entries[0:-1]:
                    log_received = Log(json_log['term'], json_log['command'])
                    # Store
                    self.log.append(log_received)
                    # Execute
                    self._deliver_command(log_received)
                    index += 1
            # Need now to accept the last command sent
            json_log = entries[-1]
            log_received = Log(json_log['term'], json_log['command'])
            rocket_flag = self._acceptable_command(log_received)

        # update commitIndex
        # Always index (because the value is shifted by 1 logically)
        # The index is 0 if no command, otherwise it starts to 1
        self.commitIndex = commitIndex
        return index, rocket_flag

    def _deliver_command(self, entry):
        if 'action' in entry.command:
            self.rocket.deliver_action(entry.command['action'])
            # Check Action
            try:
                for k in entry.command['action'].keys():
                    assert(entry.command['action'][k] == actions[self.timestep][k])
            except AssertionError as e:
                print(e)
                print("our action {}".format(entry.command['action']))
                print("the expected action {}".format(actions[self.timestep]))
                print("error at timestep = {}".format(self.timestep))
                os._exit(-1)
        else:
            self.rocket.deliver_state(entry.command['state'])
        # update timestep
        self.timestep = math.floor(len(self.log) / 2) + 1

    def _acceptable_command(self, entry):
        if 'action' in entry.command:
            try:
                return self.rocket.acceptable_action(entry.command['action'])
            except Exception as e:
                # In case the flight computer crashed
                print(e)
                os._exit(-1)
        else:
            return self.rocket.acceptable_state(entry.command['state'])

    def add_entries(self):
        if self.rocket.sample_next_action is None:
            # Do nothing
            return
        # Acquire lock
        with self.add_entries_lock:
            # Check which command (State or Action) to send
            while self.state is State.LEADER and not self.is_done:
                last_entry = self._get_last_log()
                command = {}
                if last_entry is None or 'action' in last_entry.command:
                    command['state'] = states[self.timestep]
                else:
                    try:
                        command['action'] = self.rocket.sample_next_action()
                    except Exception as e:
                        # If the computer crashed
                        print(e)
                        os._exit(-1)
                    if command['action'] is None:
                        self.is_done = True
                        return
                entry = Log(self.currentTerm, command)
                self.log.append(entry)
                # Wait majority
                self._wait_majority()
                if self.state != State.LEADER:
                    # Do nothing
                    break
                # Leader can deliver state because of the majority
                self._deliver_command(entry)

    def _wait_majority(self):
        # Update matchIndex for the leader
        self.matchIndex[self._get_id_tuple(self.id)] =\
            self.matchIndex[self._get_id_tuple(self.id)] + 1
        # Update nextIndex for the leader
        self.nextIndex[self._get_id_tuple(self.id)] =\
            self.nextIndex[self._get_id_tuple(self.id)] + 1
        # Get currentCommitIndex
        next_commit_index = self._last_log_index()
        # Start exchanging message
        for peer in self.rocket.get_peers():
            # Set the append entries timer to zero, i.e start immediately
            self.append_entries_timer[self._get_id_tuple(peer)].reset_with_time(0)
        while self.state is State.LEADER:
            if self.commitIndex < next_commit_index:
                # Loop while command not replicated
                continue
            break

    def _send_append_entries(self, peer):
        with self.append_entries_lock[self._get_id_tuple(peer)]:
            url = 'append_entries'
            if self.state == State.LEADER:
                # Cancel append entries timer by default (the heartbeat)
                #self.append_entries_timer[self._get_id_tuple(peer)].cancel()
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
                # Reset the append entry timer (the heartbeat)
                self.append_entries_timer[self._get_id_tuple(peer)].reset()


    def _append_entries_answer(self, reply_json, peer):
        """
        when leader receives follower answer
        """
        #print("Leader received reply {}\n".format(reply_json))
        if reply_json['term'] > self.currentTerm:
            self._become_follower(reply_json['term'])
        elif self.state == State.LEADER and reply_json['term'] == self.currentTerm:
            if reply_json['success']:
                if reply_json['rocket_flag']:
                    if self.nextIndex[self._get_id_tuple(peer)] < reply_json['index'] + 2:
                        # It means that the leader knows that the follower accepted the last entry
                        # It is here the difference with Raft
                        # We suppose that rocket_flag means that the leader can
                        # compute reply_json['index'] + 1 for match index
                        self.nextIndex[self._get_id_tuple(peer)] =\
                                                        reply_json['index'] + 1
                        self.matchIndex[self._get_id_tuple(peer)] =\
                                                        reply_json['index'] + 1
                        self._update_commit(reply_json['index'] + 1)
            else:
                # Set the follower in the same state of the leader
                self.nextIndex[self._get_id_tuple(peer)] =\
                    max(1, reply_json['index'] + 1) # TODO: Maybe + 1 ?
                self.matchIndex[self._get_id_tuple(peer)] =\
                    max(0, reply_json['index'])


    def _update_commit(self, index):
        if index > self.commitIndex:
            with self.update_commit_lock:
                count = len([value for value in self.matchIndex.values()\
                                             if value >= index])
                if count >= self.majority and \
                        self._get_term_by_index(index) == self.currentTerm:
                    self.commitIndex = index

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

    def _get_last_log(self):
        return self.log[-1] if self.log else None

    def _get_id_tuple(self, peer):
        return (peer['host'], peer['port'])
