# Raft uses random timer for election

import threading
import random

class RaftRandomTime:
    def __init__(self, min_time, max_time, function, args=None):
        self.min_time = min_time
        self.max_time = max_time
        self.function = function
        self.args = args
        self.timer = threading.Timer

    def _set_raft_time(self):
        return random.random()*(self.max_time - self.min_time) + self.min_time

    def start(self):
        self.timer = threading.Timer(self._set_raft_time(),
                                    self.function,
                                    args=self.args)
        self.timer.start()

    def reset(self):
        self.timer.cancel()
        self.start()


class RaftTimer:
    def __init__(self, time, function, args=None):
        self.time = time
        self.function = function
        self.args = args
        self.timer = threading.Timer

    def start(self):
        self.time = threading.Timer(self.time,
                                    self.function,
                                    args=self.args)

    def reset(self):
        self.timer.cancel()
        self.start()
