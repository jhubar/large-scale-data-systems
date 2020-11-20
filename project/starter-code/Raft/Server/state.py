from enum import Enum

# Simple enumeration for managing state in Raft consensus algorithm
class State(Enum):
    FOLLOWER = 1
    CANDIDATE = 2
    LEADER = 3
