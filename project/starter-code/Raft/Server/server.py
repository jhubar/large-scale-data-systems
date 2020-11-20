# Flask for each FLight Computer. The server implements Raft Consensus Algorithm

from Server.state import State
from State_Machine.log import Log
from ..Abstraction.timer import RaftRandomTime, RaftTime
import request
from flask import Flask


app = Flask(__name__)

class Server:
    def __init__(self, rocket, host, port):
        # Common to all server
        self.state = State.FOLLOWER
        self.election_timer = RaftRandomTime(0.15, 0.3, self.time_out)
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
        self.host = host
        self.port = port
        self.vote = 0

    """
    peer = tuple (host, port)
    """
    def start_server(self, peers=[]):
        for peer in peers:
            self.add_peer(peer)
        app.run(debug=True, host=self.host, port=self.port)

    def init_vote(self):
        self.vote = 0

    def time_out(self):
        self.init_vote()
        if(self.state is State.LEADER):
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
                if not self.log:
                    jsonPayload = json.dumps(VoteRequest(self.currentTerm,
                                                         (self.host, self.port),
                                                         self.log[-1].index,
                                                         self.log[-1].term).__dict__)
                else:
                    jsonPayload = json.dumps(VoteRequest(self.currentTerm,
                                                         (self.host, self.port),
                                                         0,
                                                         0).__dict__)
                requests.get('http:{}:{}/requestVote'.format(host, port),
                             data=jsonPayload)




    def add_peer(self, peer):
        self.rocket.add_peer(peer)

    def starting_lection(self):
        pass

    def election_procedure(self):
        pass

    @app.

    @app.route('/appendEntries/')
    def receiver_implementation(self):
        content = request
        if content['term'] < content['currentTerm']






    """
    def electionSafety:
        pass
    def appendOnly:
        pass
    def LeaderCompleness:
        pass
    def StateMachineSafety:
        pass
    """
