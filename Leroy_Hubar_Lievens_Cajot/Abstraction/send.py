import requests
from enum import Enum
from flask import jsonify

"""
    Abstraction of failure detection with the module 'requests'. The module
    throws an exception when the answer is to slow (Slower than TIMEOUT).
    In Raft, the leader continue to send heartbeat even if Follower is known
    to have failed.
"""

def send_get(peer, endpoint, params, TIMEOUT=0.05):
    url = get_url(peer, endpoint)
    try:
        reply = requests.get(url, params=params, timeout=TIMEOUT)
    except Exception as e:
        # Any error between the two servers (Failure, reply too slow, ...)
        return None

    return reply_handler(reply)

def send_post(peer, endpoint, json, TIMEOUT=0.05):
    url = get_url(peer, endpoint)
    try:
        reply = requests.post(url, json=json)
    except Exception as e:
        reply = {
            'Exception': 'EXCEPTION IN SEND_POST',
            'track': e,
            'json': json
        }
        # Any error between the two servers (Failure, reply too slow, ...)
        return reply

    return reply_handler(reply)

def get_url(peer, endpoint):
    return 'http://127.0.0.1:{}/{}'.format(peer, endpoint)

def reply_handler(reply):
    if reply.status_code == 200:
        return reply
    else:
        return None
