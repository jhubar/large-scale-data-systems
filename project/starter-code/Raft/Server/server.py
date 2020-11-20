# Flask for each FLight Computer. The server implements Raft Consensus Algorithm

from Server.state import State
from State_Machine.log import Log

class Server:
    def __init__(self, rocket, host, port):
        # Common to all server
        self.state = State.FOLLOWER
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
