## General info
This project is the implementation a consensus algorithm to ensure the redundancy of several flight computers responsible for controlling a rocket.


## Setup
you have to run run run_server as many times (each time with the incremented port number) as the desired flight computer, e.g. 4.

```
$ python run_server --port 8001
$ python run_server --port 8002
$ python run_server --port 8003
$ python run_server --port 8004
```
Then you have to update the json file (peering.json). In this one, you just have to update the number of flight computer chosen before.


Then you have to update the json file. In this one, you just have to update the number of flight computer chosen before.

```
$ python test_consensus.py
```

## Custom execution

To run a random faulty computer, you have to pass the argument
```
$ python test_consensus.py --flights-computers-type 1
```

And if we want to select particular flight computer
1. Full throttle: 0
1. random throttle: 1
1. slow throttle: 2
1. craching throttle: 3

```
$ python test_consensus.py --flights-computers-type 1
```
