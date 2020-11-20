# Flask for each FLight Computer. The server implements Raft Consensus Algorithm

from Server.state import State
from State_Machine.log import Log
from ..Abstraction.timer import RaftRandomTime, RaftTime

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

    """
    peer = tuple (host, port)
    """
    def start_server(self, peers=[]):
        for peer in peers:
            self.add_peer(peer)
        app.run(debug=True, host=self.host, port=self.port)

    def time_out(self):
        if(self.state is State.LEADER):
            return
        else:
            self.state = State.CANDIDATE
            self.election_timer.reset()


    def add_peer(self, peer):
        self.rocket.add_peer(peer)

    def starting_lection(self):
        pass

    def election_procedure(self):
        pass


    '''
    def electionSafety:
        pass
    def appendOnly:
        pass
    def LeaderCompleness:
        pass
    def StateMachineSafety:
        pass
    '''
