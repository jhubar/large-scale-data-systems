from .message import Message

class ActionAnswer(Message):
    """
    term : condidate's term
    candidateID: candidate requesting vote
    lastLogIndex: index of candidate's last log entry
    lastLogTerm: term of candidate's last log entry
    """
    def __init__(self, answer):
        super(ActionAnswer, self).__init__()
        self.answer = answer
