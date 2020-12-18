from .message import Message

class Heartbeat(Message):
    def __init__(self, term, index, id, handleStage):
        super(Heartbeat, self).__init__()
        self.term = term
        self.index = index
        self.id = id
        self.handleStage = handleStage

class HeartbeatAnswer(Message):
    def __init__(self, term , index, id, answer, handleStage):
        super(HeartbeatAnswer, self).__init__()
        self.term = term
        self.index = index
        self.id = id
        self.answer = answer
        self.handleStage = handleStage
