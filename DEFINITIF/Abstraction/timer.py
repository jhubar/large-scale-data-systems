import threading
import random

"""
    Abstraction of timer in the Raft algorithm.
    For timeout election, each server has a random timeout.
"""

class RaftRandomTime:
    def __init__(self, min_time, max_time, function, args=None):
        self.min_time = min_time
        self.max_time = max_time
        self.function = function
        self.args = args
        self.timer = threading.Timer(self._set_raft_time(), self.exec_function)

    def _set_raft_time(self):
        return random.random()*(self.max_time - self.min_time) + self.min_time

    def start(self):
        self.timer = threading.Timer(self._set_raft_time(), self.exec_function)
        self.timer.start()

    def start_grumble(self):
        self.timer = threading.Timer(self.max_time, self.exec_function)
        self.timer.start()

    def reset_grumble(self):
        self.timer.cancel()
        self.start_grumble()

    def exec_function(self):
        threading.Thread(target=self.function, args=self.args).start()

    def reset(self):
        self.timer.cancel()
        self.start()


class RaftTimer:
    def __init__(self, time, function, args=None):
        self.time = time
        self.function = function
        self.args = args
        self.timer = threading.Timer(time, self.exec_function)

    def start(self):
        self.timer = threading.Timer(self.time, self.exec_function)
        self.timer.start()

    def reset(self):
        self.timer.cancel()
        self.start()

    def exec_function(self):
        threading.Thread(target=self.function, args=self.args).start()

    def reset_with_time(self, time):
        self.timer.cancel()
        self.start_with_time(time)

    def start_with_time(self, time):
        self.timer = threading.Timer(time, self.exec_function)
        self.timer.start()
