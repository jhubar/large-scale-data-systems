from .message import Message

class VoteRequest(Message):
    """
    term : condidate's term
    candidateID: candidate requesting vote
    lastLogIndex: index of candidate's last log entry
    lastLogTerm: term of candidate's last log entry
    """
    def __init__(self, term, candidateID, index, handleStage):
        super(VoteRequest, self).__init__()
        self.candidateID = candidateID
        self.index = index
        self.term = term
        self.handleStage = handleStage



class VoteAnswer(Message):
    """
    voteGranted: The response for the candidate
    term : condidate's term
    candidateID: candidate requesting vote
    lastLogIndex index of candidate's last log entry
    lastLogTerm: term of candidate's last log entry
    """
    def __init__(self, voteGranted, term, handleStage):
        super(VoteAnswer, self).__init__()
        self.voteGranted = voteGranted
        self.term = term
        self.handleStage = handleStage
