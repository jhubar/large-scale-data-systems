from .message import Message

class Heartbeat(Message):
    def __init__(self, term, index, id):
        super(Heartbeat, self).__init__()
        self.term = term
        self.index = index
        self.id = id

class HeartbeatAnswer(Message):
    def __init__(self, term , index, id, answer):
        super(HeartbeatAnswer, self).__init__()
        self.term = term
        self.index = index
        self.id = id
        self.answer = answer
