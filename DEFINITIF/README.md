## General info
This project is the implementation a consensus algorithm to ensure the redundancy of several flight computers responsible for controlling a rocket.


## Setup
Before starting the system, the file peering.json have to be completed with the number of 
flight computer that you want to include in your cluster. By default, the file is ready
for a cluster of 7 flight computers. Computers have all the same ip adress and are identify
py the port. The ports number start from 8001.

## Starting computers
Before the take off process, each flight computer need to be start in separate consoles
by executing the run_server file as follow:

```
$ python run_server --port 8001
$ python run_server --port 8002
$ python run_server --port 8003
$ python run_server --port 8004
$ python run_server --port 8005
$ python run_server --port 8006
$ python run_server --port 8007
$ ...
```

Started flight computers have to respect the peering.json list (number and port).
As soon as a majority of the cluster's computers are started, computers find a leader and
the system may work. 

## Take-off 
In order to simulate the rocket flight, the following file can be executed without arguments.

```
$ python test_consensus.py
```


## Custom execution

To run a random faulty computer, as describe in the initial implementation of the project,
 the following arguments can be used while starting a flight computer.
```
$ python run_server --port 8001 --flight-computers-type 1
```

In order to perform more specific tests, a new type argument is introduce:

```
$ python run_server --port 8001 --type 0
```

The value given in the --type argument are the following:

1. Full throttle: 0
1. random throttle: 1
1. slow throttle: 2
1. craching throttle: 3

Note: Using the --type argument imply to not use the --flight-computer-type argument.


