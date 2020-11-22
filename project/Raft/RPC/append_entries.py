
class AppendEntriesRequest():
    """
    term: leader’s term
    leaderId: so follower can redirect clients
    prevLogIndex: index of log entry immediately preceding new ones
    predLogTerm: term of prevLogIndex entry
    entries: log entries to store (empty for heartbeat; may send more than one for efficiency)
    leaderCommit: leader’s commitIndex
    """
    def __init__(self, term, leaderId, prevLogIndex, predLogTerm, entries, leaderCommit):
        self.term = term
        self.leaderId = leaderId
        self.prevLogIndex = prevLogIndex
        self.predLogTerm = predLogTerm
        self.entries = entries
        self.leaderCommit = leaderCommit

class AppendEntriesAnswer():
    """
    term: currentTerm, for leader to update itself
    success: true if follower contained entry matching prevLogIndex and prevLogTerm
    """
    def __init__(self, term, success):
        self.term = term
        self.succes = success
