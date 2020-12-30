import math
import threading
import time
import os
from Tools.tools import *
from Abstraction.timer import *
from Abstraction.send import *

class Raft:

    def __init__(self, fc, id, peers=[]):
        """
        Raft object instance
        :param fc: A flight computer object
        :param id: Identification of the new flight computer. In this project,
            the computer id is the port who will be use
        :param peers: A list who contain id of each others computers.
        """
        # Computer identification
        self.id = id
        self.host = '127.0.0.1'

        # The flight computer instance
        self.fc = fc

        # The state of the computer: FOLLOWER, LEADER or CANDIDATE
        self.state = FOLLOWER

        # Election timer: an new election start when fall to zero
        self.t_min = 0.150
        self.t_max = 0.500
        self.election_timer = RaftRandomTime(self.t_min, self.t_max, self.election_time_out, args=())

        # Heartbeats timer
        self.heartbeat_timer = {}
        for peer in peers:
            self.heartbeat_timer[str(peer)] = RaftTimer(0.075, self.heartbeat, args=(peer, ))

        # Vote counter: Count the number of nodes who vote for this node during elections
        self.vote = 0
        # The id of the node who receive his vote
        self.votedFor = None
        # The id of the leader that we are following
        self.leader_following = self.id
        # Term counter: A new term begin at each elections
        self.term = 0
        # Index: the numbr of executed actions
        self.index = 0

        # Adding others peers in the flight computer:
        for peer in peers:
            self.fc.add_peer(peer)

        # Number of node who represent the majority
        self.majority = (len(peers) + 1) / 2

        # Count the number of follower who have replicated the send state
        self.state_replic_counter = 0

        # Store reply from each follower with her action choice
        self.follower_actions = []

        # Count the number of deliver state acknowledgment receive
        self.deliver_ack = 0

        # This value block heart beats
        self.beats_blocker = False

        # Locks
        self.vote_counter_lock = threading.Lock()
        self.heartbeat_lock = {}
        for peer in peers:
            self.heartbeat_lock[str(peer)] = threading.Lock()
        self.state_replic_counter_lock = threading.Lock()
        self.follower_actions_lock = threading.Lock()
        self.deliver_ack_lock = threading.Lock()

        # Debug printer options
        self.debug_A = False
        self.debug_B = False
        self.debug_C = False         # Check heartbeats reply
        self.debug_D = True         # Action consensus general printer
        self.debug_E = True         # Advanced consensus pringer

    def election_time_out(self):
        """
        This method is triggered when a follower node stop to receive
        heartbeats or others messages from the leader.
        """
        # No effect if the node is actually leader
        if self.state == LEADER:
            self.election_timer.reset()
            return

        # Start new elections
        print("The raft server http://{}:{}/ has an election timeout".format(self.host, self.id))
        # Init the vote counter and vote for himself
        self.vote = 1
        self.vote_id = self.id
        # Increment the actual term
        self.term += 1
        actual_term = self.term
        # Change the state
        self.state = CANDIDATE
        # Reset the timer: have to collect the majority in the given time
        self.election_timer.reset()
        # Send a vote request to each other peers
        for peer in self.fc.get_peers():
            # Start a thread for each peer
            threading.Thread(target=self.ask_for_vote,
                             args=(actual_term,
                                   self.index,
                                   peer)).start()

        # Wait for a majority of positive answers
        majority = False
        while not majority and actual_term == self.term and self.state == CANDIDATE:
            time.sleep(0.05)
            with self.vote_counter_lock:
                if self.vote >= self.majority:
                    if self.debug_B:
                        print('Vote majority reach')
                    self.become_leader()
                    return
        if self.state == FOLLOWER:
            print('Aborted elections: follow the new leader')

    def heartbeat(self, peer):
        """
        Leader Function:
        An heartbeat is send to each followers by the leader to maintain
        his leader position
        :param peer: the follower to send heartbeat
        """
        # If we are sampling an action
        if self.beats_blocker:
            return

        # Formulate the request
        msg = {
            'obj': HEARTBEAT,
            'id': self.id,
            'term': self.term,
            'index': self.index
        }
        # Targeted end poind
        url = 'heartbeat'
        # Send the request:
        if self.state == LEADER:
            with self.heartbeat_lock[str(peer)]:
                reply = send_post(peer, url, msg)

            # If no reply before time out:
            if reply is None:
                if self.debug_C:
                    print('None heartbeat reply from {} to the leader {}'.format(peer, self.id))
                return

            # Translate the answer:
            if not isinstance(reply, dict):
                reply = reply.json()

            # If post exception is return
            if 'Exception' in reply.keys():
                if self.debug_C:
                    print('Exception during heartbeat request from {} to {}'.format(self.id, peer))
                    print('e: {} -- json: {}'.format(reply['track'], reply['json']))
                return

            if reply['term'] > self.term:
                if self.debug_A:
                    print('Heartbeat break: target term higher than leader term: {} vs {}'.format(reply['term'],
                                                                                                  self.term))
                self.become_follower(reply['term'])
                return

            # Restart the timer
            self.heartbeat_timer[str(peer)].reset()

    def process_heartbeat(self, request):
        """
        Follower function: analyze and answer to heartbeats
        :param request: The received request in the heartbeat
        """
        # If the node is out of term:
        if self.term < request['term']:
            self.term = request['term']
        # If leader is out of term:
        if self.term > request['term']:
            asw = {'term': self.term,
                   'index': self.index,
                   'id': self.id}
            return asw
        asw = {'term': self.term,
               'index': self.index,
               'id': self.id}
        if request['id'] != self.leader_following:
            self.leader_following = request['id']
            print('Following a new leader: {}'.format(self.leader_following))

        if self.state is not FOLLOWER:
            self.become_follower(self.term)
        self.election_timer.reset()
        return asw


    def ask_for_vote(self, term, index, peer):
        """
        Candidate function
        This method ask to the given peer a vote to begin leader
        :param term: The actual term of the node
        :param index: The actual number of executed action. Work like a time unit
        """
        # The target end point
        url = 'vote_request'
        msg = {
            'obj': VOTE_REQ,
            'id': self.id,
            'term': term,
            'index': index,
        }
        # Send the request
        reply = send_post(peer, url, msg)
        if reply is None:
            if self.debug_A:
                print('Ask_for_vote None reply from {} to {}'.format(self.id, peer))
            return
        # Translate the answer
        if not isinstance(reply, dict):
            reply = reply.json()
        # Handle exceptions:
        if 'Exception' in reply.keys():
            if self.debug_A:
                print('POST exception during ask_for_vote from {} to {}'.format(self.id, peer))
                print('e: {}'.format(reply['track']))
                print('json: {}'.format(reply['json']))
            return
        # Increment the number of vote received:
        if self.state == CANDIDATE and 'vote_state' in reply.keys():
            # If the peer accept to vote for the node
            if 'accepted' in reply['vote_state']:
                with self.vote_counter_lock:
                    self.vote += 1
            # If the peer already already voted:
            if 'to_late' in reply['vote_state']:
                return
            # If the node who receive the request have an higher term:
            if 'out_of_date' in reply['vote_state']:
                if self.debug_A:
                    print('ask_for_vote refused by {} for {}: out of date.'
                          'term:  {} - index: {} vs {} - {}'.format(peer, self.id, term, index,
                                                                    reply['term'], reply['index']))
                self.become_follower(reply['term'])


    def process_ask_for_vote(self, request):
        """
        Elector function
        This method decide if the elector vote for the candidate
        or not
        :param request: the vote request
        """

        # If candidate term is higher than follower term:
        if self.term < request['term']:
            self.become_follower(request['term'])

        # General answer
        asw = {
            'obj': VOTE_ASW,
            'id': self.id,
            'term': self.term,
            "index": self.index,
            'vote_state': 'out_of_date'
        }
        # If Candidate out of date:
        if self.term > request['term']:
            return asw
        # If node already voted
        if self.votedFor is not None:
            asw['vote_state'] = 'to_late'
            return asw
        else:
            self.votedFor = request['id']
            asw['vote_state'] = 'accepted'
            self.election_timer.reset()
            if self.debug_B:
                print('Node {} vote for {}'.format(self.id, request['id']))
            return asw


    def become_follower(self, term):

        self.term = term
        self.state = FOLLOWER
        self.votedFor = None
        self.vote = 0
        self.election_timer.reset()
        print('Become follower: id {}, term {}, index {}'.format(self.id, self.term, self.index))

    def become_leader(self):

        if self.state == CANDIDATE:
            print('Raft server {} is now a leader'.format(self.id))
            # Update status:
            self.state = LEADER
            self.leader_following = self.id

            # Start to send heartbeats to keep the lead
            for peer in self.fc.get_peers():
                self.heartbeat_timer[str(peer)].start_with_time(0)

    def start_raft(self):
        self.election_timer.start()

    def state_consensus(self, state):
        """
        This method is triggered by the dicide on state end point if the
        node is leader and organize the replication of the given state
        to all followers
        """
        # Initialize reply counter to 1 (because we consider his own acknolegment
        self.state_replic_counter = 1

        # Start threads
        for peer in self.fc.get_peers():
            threading.Thread(target=self.process_state_consensus,
                             args=(peer, state)).start()
        # Wait for a majority of acknoledgment:
        secu_idx = 0
        while secu_idx < 10:
            # A time sleep to let the time to answer:
            time.sleep(0.02)
            with self.state_replic_counter_lock:
                # If majority of acknowledgments:
                if self.state_replic_counter >= self.majority:
                    # Apply to him
                    self.fc.deliver_state(state)
                    reply = {'status': 'succes'}
                    return reply
            secu_idx += 1
        # If no majority reach:
        reply = {'status': 'no_majority'}
        return reply

    def process_state_consensus(self, peer, state):
        """
        This method is use by threads who give the state to replicate
        to each follower.
        :param peer: the target follower
        :param state: the state to replicate
        """
        # Send the request
        reply = send_post(peer, 'replic_state', state)
        if reply is None:
            return
        # If connection fail:
        if isinstance(reply, dict):
            return
        reply = reply.json()
        if 'ack' in reply.keys():
            with self.state_replic_counter_lock:
                self.state_replic_counter += 1

    def action_consensus(self):
        """
        This method organize the action consensus, and the democratic
        decided action replication on each flight computer
        """
        if self.debug_D:
            print('---------------------')
            print('ACTION CONSENSUS: start')

        # Initialize answers array:
        self.follower_actions = []


        # Block heartbeats during the sampling
        self.beats_blocker = True
        # We first start by a sample next action of the leader himself. If slow computer, time out will be reach
        personal_action = self.fc.sample_next_action()
        self.follower_actions.append(personal_action)
        # Reactive hearbeats
        self.beats_blocker = False
        for peer in self.fc.get_peers():
            self.heartbeat(peer)

        # Start threads for each others peer:
        for peer in self.fc.get_peers():
            threading.Thread(target=self.process_action_consensus,
                             args=(peer, )).start()

        # Wait for the majority
        majority = False
        security = 0
        consensus_action = {}
        while not majority:
            # A small time sleep to wait answers
            time.sleep(0.01)

            # Copy the answer array:
            tmp_what_to_do = []
            with self.follower_actions_lock:
                tmp_what_to_do = self.follower_actions.copy()

            # Two counter arrays to count each type of answers
            tmp_action = []
            tmp_counter = []

            for act in tmp_what_to_do:
                if act in tmp_action:
                    idx = tmp_action.index(act)
                    tmp_counter[idx] += 1
                else:
                    tmp_counter.append(1)
                    tmp_action.append(act)

            # Check if an action have the majority:
            idx = 0
            for item in tmp_counter:
                if item >= self.majority:
                    if self.debug_D:
                        print('Majority reach: ')
                        print('tmp_action: {}'.format(tmp_action))
                        print('tmp_counter: {}'.format(tmp_counter))
                    consensus_action = tmp_action[idx]
                    majority = True
                    break
                idx += 1

            # A security to avoid ininite loops:
            if security >= 3 * len(self.fc.get_peers()):
                if self.debug_E:
                    print('Error: no consensus majority before security break')
                return {'Error': 'security_break'}
            security += 1

        # We can now apply the consensus action
        self.deliver_ack = 1
        security = 0
        deliver_validation = False

        # Start threads
        for peer in self.fc.get_peers():
            threading.Thread(target=self.process_exec_consensus_action,
                             args=(peer, consensus_action)).start()

        # Check if majority of follower have deliver
        while not deliver_validation:
            # A small time sleep to let the time to deliver
            time.sleep(0.01)

            # Check if majority of delivery
            with self.deliver_ack_lock:
                if self.deliver_ack >= self.majority:
                    return consensus_action
            # Infinity loop security:
            if security >= 3 * len(self.fc.get_peers()):
                if self.debug_E:
                    print('Error: no state deliver majority receive before security break')
                return {'Error': 'security_break'}
            security += 1

    def process_action_consensus(self, peer):
        """
        This method is use by each thread who ask the action
        decision of a follower node
        :param peer: the target follower
        """
        # Initialize the request
        req = {
            'obj': 'what_to_do',
            'term': self.term
        }
        # Send the request
        reply = send_post(peer, 'what_to_do', req, TIMEOUT=0.075)
        # If no reply
        if reply is None:
            if self.debug_E:
                print('No action advice answer from {}'.format(peer))
            return
        # If connection fail:
        if isinstance(reply, dict):
            return
        reply = reply.json()

        # Add the answer action to the array:
        with self.follower_actions_lock:
            self.follower_actions.append(reply)

    def process_exec_consensus_action(self, peer, action):
        """
        This method order to each followers to apply action from consensus
        :param peer: the target peer of the thread
        :param action: the action from the consensus
        """
        # Init the request:
        req = action
        # Send the request
        reply = send_post(peer, 'apply_action', req, TIMEOUT=0.075)
        # If no reply
        if reply is None:
            if self.debug_E:
                print('No apply_action answer from {}'.format(peer))
        # If connection error:
        if isinstance(reply, dict):
            return
        # Translate the reply
        reply = reply.json()
        # Handle errors:
        if 'state' not in reply.keys():
            if self.debug_E:
                print('Error during action_delivery. Reply: {}'.format(reply))
            return
        # If deliver is done:
        with self.deliver_ack_lock:
            self.deliver_ack += 1







