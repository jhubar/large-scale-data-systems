from ..Server.state import State
import json


class VoteRequest:
    """
    term : condidate's term
    candidateID: candidate requesting vote
    lastLogIndex: index of candidate's last log entry
    lastLogTerm: term of candidate's last log entry
    """
    def __init__(self, term, candidateID, lastLogIndex, lastLogTerm):
        self.term = term
        self.candidateID = candidateID
        self.lastLogIndex = lastLogIndex
        self.lastLogTerm = lastLogTerm

    

class VoteAnswer:
    """
    voteGranted: The response for the candidate
    term : condidate's term
    candidateID: candidate requesting vote
    lastLogIndex index of candidate's last log entry
    lastLogTerm: term of candidate's last log entry
    """
    def __init__(self, voteGranted, term, candidateID, lastLogIndex, lastLogTerm):
        self.voteGranted = voteGranted
        self.term = term
        self.candidateID = term
        self.lastLogIndex = term
        self.lastLogTerm = lastLogTerm
