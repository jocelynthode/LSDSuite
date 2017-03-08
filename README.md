# LSDSuite

Benchmarking Framework for Large-Scale Distributed Systems (LSDS)

## Requirements
* Docker >= 1.12
* OpenJDK or OracleJDK >= 8
* Python >= 3.5
* pip >= 9.0.1
* GNU bash

## How to use
### Locally
1. Have a Docker client/daemon up and running on your computer
2. Fill out `scripts/container-start-script.sh` with the command to start your app
3. Fill out `lsdsuite/config/app.yaml` and `lsdsuite/config/config.yaml` with the desired parameters
4. Build using `./gradlew docker`
5. Run `run_benchmarks.py` with the `--local` option (An help is available through the command line)

### On a cluster
1. Have a cluster ready with Docker running on every hosts
2. Fill out `scripts/container-start-script.sh` with the command to start your app
3. Fill out `lsdsuite/config/app.yaml` and `lsdsuite/config/config.yaml` with the desired parameters
4. Fill out `lsdsuite/config/hosts.example` with your `user@hostname` hosts and rename as `hosts` 
5. Build using `./gradlew docker`
6. Run `run_benchmarks.py` (An help is available through the command line)
