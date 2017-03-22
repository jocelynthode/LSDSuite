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
2. Have Minikube running (`minikube start`)
2. Fill out `scripts/container-start-script.sh` with the command to start your app. Look for the comments
3. Fill out `lsdsuite/config/app.yaml` and optionally `lsdsuite/config/tracker.yaml` with the desired parameters. Look for the comments
4. Build using `./gradlew docker`
5. Modify in `run_benchmarks.py` the constant `K8S_CONFIG` to your kube config
6. Run `run_benchmarks.py` with the `--local` option (An help is available through the command line)

### On a cluster
1. Have a cluster ready with Docker running on every hosts and Kubernetes setup on them
2. Fill out `scripts/container-start-script.sh` with the command to start your app. Look for the comments
3. Change your desired app name in the gradle files
4. Fill out `lsdsuite/config/app.yaml` and optionally `lsdsuite/config/tracker.yaml` with the desired parameters. Look for the comments
5. Build using `./gradlew docker`
6. Modify in `run_benchmarks.py` the constant `K8S_CONFIG` to your kube config
7. Run `run_benchmarks.py` (An help is available through the command line)
