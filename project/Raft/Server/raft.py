# Flask for each FLight Computer. The raft server implements Raft Consensus Algorithm

from .state import State
from collections import Counter
from ..Abstraction.timer import RaftRandomTime, RaftTimer
from ..RPC.request_vote import VoteAnswer, VoteRequest
from ..RPC.heartbeat import Heartbeat, HeartbeatAnswer
from ..RPC.action_answer import ActionAnswer
from ..Abstraction.send import *
import json
import math
import threading
import logging
import time
import os
import sys
from enum import Enum
from flask import Flask, request, jsonify, redirect

class Raft:
    def __init__(self, fc, id, peers=[]):
        # Common to all raft server
        self.state = State.FOLLOWER
        self.votedFor = None
        self.index = 0
        self.currentTerm = 0
        # Flight Computer object
        self.fc = fc
        self.id = id
        # Raft information
        self.election_timer = RaftRandomTime(0.150, 0.500, self.time_out, args=())
        self.vote = 0
        self.majority = math.floor((len(peers) + 1) / 2) + 1
        for peer in peers:
            self.fc.add_peer(peer)
        # Various variable (Locks, etc)
        self.rpc_lock = self._init_rpc_lock(peers)
        self.increment_vote_lock = threading.Lock()
        # Only Leader handles these variables
        self.heartbeat_timer = self._init_heartbeat_timer(peers)
        self.command_answer = {}

        self.followers_actions = {}
        self.beats_blocker = False
        self.follower_exec_action = []
        self.followers_actions_loc = self._init_rpc_lock(peers)
        self.followers_what_to_do_loc = self._init_rpc_lock(peers)


    def _init_heartbeat_timer(self, peers):
        heartbeat_timer = {}
        for peer in peers:
            heartbeat_timer[self._get_id_tuple(peer)] = \
                RaftTimer(0.075, self._heartbeat, args=(peer,))
        return heartbeat_timer

    def _init_rpc_lock(self, peers):
        rpc_lock = {}
        for peer in peers:
            rpc_lock[self._get_id_tuple(peer)] = threading.Lock()
        return rpc_lock

    def start_raft(self):
        self.election_timer.start()

    """
    Election handler
    """
    def time_out(self):
        self.beats_blocker = False
        if self.state is State.LEADER:
            return
        else:
            # Start an election
            print("The raft server http://{}:{}/ has an election timeout".format(self.id['host'], self.id['port']))
            self.vote = 0
            self.currentTerm += 1
            # Goes to CANDIDATE state
            self.state = State.CANDIDATE
            # Vote for itself
            self.votedFor = self.id
            self.vote = self.vote + 1
            # Start the timer election
            self.election_timer.reset()
            # get the peers and send a VoteRequest
            for peer in self.fc.get_peers():
                threading.Thread(target=self.run_election,
                                 args=(self.currentTerm,
                                       self.index,
                                       peer)).start()

    def run_election(self, term, index, peer):
        message = VoteRequest(term, self.id, index, self.fc.current_stage_index).get_message()
        # Post method
        url = "vote_request"
        while self.state is State.CANDIDATE and term is self.currentTerm:
            reply = send_post(peer, url, message)
            if reply is not None and self.state is State.CANDIDATE:
                if reply.json()['voteGranted']:
                    # A follower said yes to this candidate
                    with self.increment_vote_lock:
                        self.vote = self.vote + 1
                        if self.state is State.CANDIDATE\
                        and self.vote >= self.majority:
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
        self._check_consistent_vote(request_json['candidateID']) and\
        self.index <= request_json['index']:
            # The raft server grant this candidate
            print("Raft server http://{}:{} voted for the raft server http://{}:{}"\
            .format(self.id['host'],
                    self.id['port'],
                    request_json['candidateID']['host'],
                    request_json['candidateID']['port']))
            self.currentTerm = request_json['term']
            self.votedFor = request_json['candidateID']
            self.election_timer.reset()
            answer = VoteAnswer(True, self.currentTerm,self.fc.current_stage_index).get_message()
        else:
            # The FOLLOWER raft server cannot grant this candidate
            answer = VoteAnswer(False, self.currentTerm, self.fc.current_stage_index).get_message()

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
        self.election_timer.reset()

    def _become_leader(self):
        if self.state == State.CANDIDATE:
            print("Raft server {}:{} is now a leader. Congrats."\
                                    .format(self.id['host'], self.id['port']))
            # Update variables
            self.state = State.LEADER
            for peer in self.fc.get_peers():
                # Start heartbeat
                self.heartbeat_timer[self._get_id_tuple(peer)]\
                                         .start_with_time(0)


    def _check_consistent_vote(self, candidateID):
        if self.votedFor is None or self.votedFor is candidateID:
            # The raft server has not voted yet, or already voted for this candidate
            return True
        # The raft server cannot vote for this candidate
        return False


    """
    Heartbeat Handler
    """
    def _heartbeat(self, peer):
        url = 'heartbeat'
        if self.beats_blocker:
            self.heartbeat_timer[self._get_id_tuple(peer)].reset()
            return
        message = Heartbeat(self.currentTerm, self.index, self.id, self.fc.current_stage_index).get_message()
        with self.rpc_lock[self._get_id_tuple(peer)]:
            reply = send_post(peer, url, message)
            if reply is not None and self.state is State.LEADER:
                # Check if the leader is considered as a leader
                if reply.json()['term'] > self.currentTerm:
                    self._become_follower(reply.json()['term'])
                    return
            # If everything is fine, reset the timer
            self.heartbeat_timer[self._get_id_tuple(peer)].reset()

    def process_heartbeat(self, heartbeat_request):
        #print('heartbeat received: {}'.format(heartbeat_request))
        # Update The term if needed
        if heartbeat_request['term'] > self.currentTerm:
            self._become_follower(heartbeat_request['term'])
            self.votedFor = heartbeat_request['id']

            # Update to actual term
            self.currentTerm = heartbeat_request['term']

        if heartbeat_request['term'] < self.currentTerm:
            # Oups, i don't trust him
            return HeartbeatAnswer(self.currentTerm,
                                   self.index,
                                   self.id,
                                   False
                                   ,self.fc.current_stage_index).get_message()
        # Yes he is my antoine Oh god!!.
        self.election_timer.reset()
        return HeartbeatAnswer(self.currentTerm,
                               self.index,
                               self.id,
                               True
                               ,self.fc.current_stage_index).get_message()


    def process_action_consensus(self, request):
        self.followers_actions = {}
        self.beats_blocker = True
        leader_action = self.process_sample_next_action()
        self.beats_blocker = False

        self.followers_actions[str(self.id['port'])] = leader_action

        for peer in self.fc.get_peers():
            threading.Thread(target=self._process_what_to_do,
                             args=(peer, )).start()

        majority = False
        decided_action = {}
        while not majority:
            tmp_what_to_do = {}
            # Make a copy to analyze
            with self.followers_what_to_do_loc[self._get_id_tuple(peer)]:
                tmp_what_to_do = self.followers_actions.copy()

            tmp_actions = []
            tmp_counter = []

            for ky in tmp_what_to_do.keys():
                if tmp_what_to_do[ky] in tmp_actions:
                    for i in range(0, len(tmp_actions)):
                        if tmp_what_to_do[ky] == tmp_actions[i]:
                            tmp_counter[i] += 1
                            break
                else:
                    tmp_actions.append(tmp_what_to_do[ky])
                    tmp_counter.append(1)

            # Check majority
            for i in range(0, len(tmp_counter)):
                if tmp_counter[i] > len(self.fc.peers) / 2:
                    majority = True
                    decided_action = tmp_actions[i]
                    """
                    print('P_action_consensus: Done')
                    print('action type : {}'.format(tmp_actions[i]))
                    print('len of tmp_action: {}'.format(len(tmp_actions)))
                    print('tmp actions array: {}'.format(tmp_actions))
                    print('tmp_counter array: {}'.format(tmp_counter))
                    print('best: {}'.format(decided_action))
                    """
                    # Test
                    print('========== Consensus Checking ============')
                    print('tmp_actions: {}'.format(tmp_actions))
                    print('tmp_counter: {}'.format(tmp_counter))


        # Broadcast action to each others

        self.follower_exec_action = []
        for peer in self.fc.get_peers():
            threading.Thread(target=self._process_execute_action,
                            args=(peer, decided_action)).start()

        majority = False
        while not majority:
            with self.followers_actions_loc[self._get_id_tuple(peer)]:
                if len(self.follower_exec_action) > len(self.fc.get_peers()) / 2:
                    majority = True

        self.fc.deliver_action(decided_action)

        return decided_action


    def _process_execute_action(self, peer, action):
        with self.followers_actions_loc[self._get_id_tuple(peer)]:
            req = action
            req['term'] = self.currentTerm
            url = 'excute_action'

            reply = send_post(peer, url, req, TIMEOUT=0.075)

            if reply is None or reply.json()['asw'] is False:
                return
            else:
                self.follower_exec_action.append(True)
                self.heartbeat_timer[self._get_id_tuple(peer)].reset()


    def _process_what_to_do(self, peer):

        req = {}
        req['term'] = self.currentTerm
        req['message'] = {}
        url = 'what_to_do'
        reply = send_post(peer, url, req, TIMEOUT=0.075)
        if reply is None or reply.json()['asw'] is False:
            return
        with self.followers_what_to_do_loc[self._get_id_tuple(peer)]:
            self.followers_actions[str(peer['port'])] = reply.json()['action']



    def process_decide_on_command(self, request_json):
        # Ask to everyone if state is ok !
        if self.state is State.LEADER:
            if 'state' in request_json:
                acceptable_function = self._process_replicate_state
                deliver_function = self._deliver_state
                fc_deliver_function = self.fc.deliver_state
                key = 'state'
            else:
                #return (False, "Bad command")
                return None
            self.command_answer.clear()
            for peer in self.fc.get_peers():
                threading.Thread(target=acceptable_function,
                                 args=(peer, request_json)).start()
            # Wait all responses
            self.command_answer[self._get_id_tuple(self.id)] = True
            while len(self.command_answer) != (len(self.fc.get_peers()) + 1):
                continue

            decided = sum(self.command_answer.values()) >= self.majority

            if decided:
                 # Deliver state
                 self.command_answer.clear()
                 for peer in self.fc.get_peers():
                     threading.Thread(target=deliver_function,
                                      args=(peer, request_json)).start()
                 # Wait responses
                 fc_deliver_function(request_json[key])
                 self.index += 1
                 self.command_answer[self._get_id_tuple(self.id)] = True
                 while len(self.command_answer) != (len(self.fc.get_peers()) + 1):
                     continue
            else:
                # Leader boude
                self._become_follower(self.currentTerm)
                # Leader grumble because he is not reliable
                self.election_timer.reset_grumble()
            return decided

    def _process_replicate_state(self, peer, state):
        with self.rpc_lock[self._get_id_tuple(peer)]:
            url = 'acceptable_state'
            message = state
            reply = send_post(peer, url, message)
            if reply is None:
                self.heartbeat_timer[self._get_id_tuple(peer)].reset()
                self.command_answer[self._get_id_tuple(peer)] = False
            else:
                self.command_answer[self._get_id_tuple(peer)] = True

    def _deliver_state(self, peer, state):
        with self.rpc_lock[self._get_id_tuple(peer)]:
            url = 'deliver_state'
            message = state
            reply = send_post(peer, url, message)
            if reply is not None:
                self.heartbeat_timer[self._get_id_tuple(peer)].reset()
            self.command_answer[self._get_id_tuple(peer)] = True

    def process_acceptable_state(self, request_state):
        # Need to simulate heartbeat
        self.election_timer.reset()
        return self.fc.acceptable_state(request_state)

    def process_deliver_state(self, state_request):
        # Need to simulate heartbeat
        self.election_timer.reset()
        self.fc.deliver_state(state_request['state'])
        self.index += 1
        return True



    def process_acceptable_action(self, request_action):
        try:
            self.election_timer.reset()
            return ActionAnswer(self.fc.acceptable_action(request_action['action']),self.fc.current_stage_index).get_message()
        except Exception as e:
            print(e)
            print("IT'S A TRAP")
            os._exit(-1)

    def process_deliver_action(self, action_request):
        # Need to simulate heartbeat
        self.election_timer.reset()
        self.fc.deliver_action(action_request['action'])
        self.index += 1
        return True

    """
    When leader ask for sample_next_action
    """
    def process_sample_next_action(self):
        if self.state is State.LEADER:
            try:
                return self.fc.sample_next_action()
            except Exception as e:
                print(e)
                print("IT'S A TRAP")
                os._exit(-1)

    """
    Various function
    """

    def _get_id_tuple(self, peer):
        return (peer['host'], peer['port'])
