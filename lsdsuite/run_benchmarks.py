#!/usr/bin/env python3
"""
Author: Jocelyn Thode

This script is in charge of running the benchmarks either locally or
on the cluster.

It creates the network, services and the churn if we need it.

"""
import argparse
import logging
import signal
from logging import config

import yaml
from lsdssuite import Benchmark
from lsdssuite import Churn

with open('config/config.yaml', 'r') as f:
    CLUSTER_PARAMETERS = yaml.load(f)


def create_logger():
    with open('config/logger.yaml') as f:
        conf = yaml.load(f)
        logging.config.dictConfig(conf)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Run benchmarks',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument(
        'peer_number',
        type=int,
        help='With how many peer should it be ran')
    parser.add_argument(
        'time_add',
        type=int,
        help='Delay experiments start in seconds')
    parser.add_argument(
        'time_to_run',
        type=int,
        help='For how long should the experiment run in seconds')
    parser.add_argument(
        'app_config',
        type=argparse.FileType('r'),
        help='Application configuration file')
    parser.add_argument('-l', '--local', action='store_true',
                        help='Run locally')
    parser.add_argument(
        '-n',
        '--runs',
        type=int,
        default=1,
        help='How many experiments should be ran')
    parser.add_argument(
        '--verbose',
        '-v',
        action='store_true',
        help='Switch DEBUG logging on')

    subparsers = parser.add_subparsers(
        dest='churn', help='Specify churn and its arguments')

    churn_parser = subparsers.add_parser('churn', help='Activate churn')
    churn_parser.add_argument(
        'period',
        type=int,
        help='The interval between killing/adding new containers in ms')
    churn_parser.add_argument(
        '--synthetic',
        '-s',
        action='store_true',
        help='Whether to use synthetic churn or not')
    churn_parser.add_argument(
        '--delay',
        '-d',
        type=int,
        default=0,
        help='With how much delay compared to the tester '
             'should the tester start in ms')

    args = parser.parse_args()
    APP_CONFIG = yaml.load(args.app_config)
    use_tracker = True if 'tracker' in APP_CONFIG else False

    if args.verbose:
        log_level = logging.DEBUG
    else:
        log_level = logging.INFO
    create_logger()
    logger = logging.getLogger('benchmarks')
    logger.setLevel(log_level)

    logger.info('START')
    if args.local:
        hosts_fname = None
        repository = ''
    else:
        hosts_fname = 'config/hosts'
        repository = APP_CONFIG['repository']['name']

    if args.churn:
        churn = Churn(
            hosts_filename=hosts_fname,
            service_name=APP_CONFIG['service']['name'],
            repository=repository,
            period=args.period,
            delay=args.delay,
            synthetic=args.synthetic)
        churn.set_logger_level(log_level)
    else:
        churn = None
    benchmark = Benchmark(
        APP_CONFIG,
        CLUSTER_PARAMETERS,
        args.local,
        use_tracker,
        churn)
    benchmark.set_logger_level(log_level)

    def signal_handler(signal, frame):
        logger.info('Stopping Benchmarks')
        benchmark.stop(is_signal=True)
        exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    benchmark.run(args.time_add, args.time_to_run, args.peer_number, args.runs)
