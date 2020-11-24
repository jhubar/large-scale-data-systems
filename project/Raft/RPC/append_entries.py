
class AppendEntriesRequest():
    """
    term: leader’s term
    leaderId: so follower can redirect clients
    prevLogIndex: index of log entry immediately preceding new ones
    predLogTerm: term of prevLogIndex entry
    entries: log entries to store (empty for heartbeat; may send more than one for efficiency)
    leaderCommit: leader’s commitIndex
    """
    def __init__(self, term, leaderId, prevLogIndex, prevLogTerm, entries, commitIndex):
        self.term = term
        self.leaderId = leaderId
        self.prevLogIndex = prevLogIndex
        self.prevLogTerm = prevLogTerm
        self.entries = entries
        self.commitIndex = commitIndex

    def get_message(self):
        message = {}
        message['term'] = self.term
        message['leaderId'] = self.leaderId
        message['prevLogIndex'] = self.prevLogIndex
        message['prevLogTerm'] = self.prevLogTerm
        message['commitIndex'] = self.commitIndex
        message['entries'] = [entry.__dict__ for entry in self.entries]

        return message

class AppendEntriesAnswer():
    """
    term: currentTerm, for leader to update itself
    success: true if follower contained entry matching prevLogIndex and prevLogTerm
    """
    def __init__(self, term, success, index):
        self.term = term
        self.success = success
        self.index = index
