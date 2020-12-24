from subprocess import Popen
import argparse
import math
import random

def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("--flight-computers", type=int, default=10, help="Number of flight computers in the cluster (default: 10)")
    parser.add_argument("--correct-fraction", type=float, default=1, help="Fraction of correct computers in the cluster (default: 1)")
    return parser.parse_known_args()

# Parse and check argument consistency
(args, _) = parse_arguments()
assert(args.correct_fraction <= 1)
assert(args.flight_computers >= 1)

# Initialize the cluster, computer by computer
lastPort = 8001
numIncorrect = math.ceil(args.flight_computers * args.correct_fraction)
print(numIncorrect)
for i in range(args.flight_computers):
    compType = random.randint(0, 3) if numIncorrect > i else -1
    Popen(["python", "run_server.py", "--port", "{}".format(lastPort), "--type", "{}".format(compType)])
    lastPort += 1
