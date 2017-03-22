# coding: utf-8
import logging
import re
import subprocess
import threading
import time
from datetime import datetime

import pykube
from .nodes_trace import NodesTrace


class Benchmark:
    """
    Author: Jocelyn Thode

    A class in charge of Setting up and running a benchmark
    """

    def __init__(self, job_config, cluster_config, local, tracker_config=None,
                 churn=None,
                 client=None):
        if client is None:
            self.client = pykube.HTTPClient(pykube.KubeConfig.from_file(
                cluster_config['k8s_config']))
        else:
            self.client = client
        self.job_config = job_config
        self.cluster_config = cluster_config
        self.local = local
        self.logger = logging.getLogger('benchmarks')
        self.churn = churn
        self.tracker_config = tracker_config
        self.job = None
        self.tracker = None

    def run(self, time_add, time_to_run, runs=1):
        """
        Run the benchmark

        :param time_add: How much time before starting the benchmark
        :param time_to_run: How much time to run the benchmark for
        :param runs: RUn the benchmark how many time
        """
        time_add *= 1000
        time_to_run *= 1000
        peer_number = self.job_config['spec']['completions']
        log_storage = self.job_config['spec']['template']['spec']['volumes'][0]['hostPath']['path']

        for run_nb, _ in enumerate(range(runs), 1):
            if self.tracker_config:
                self.tracker = self._create_service()

            time_to_start = int((time.time() * 1000) + time_add)
            self.logger.debug(
                datetime.utcfromtimestamp(
                    time_to_start /
                    1000).isoformat())
            environment_vars = [{'name': 'PEER_NUMBER',
                                 'value': str(peer_number)},
                                {'name': 'TIME', 'value': str(time_to_start)},
                                {'name': 'TIME_TO_RUN',
                                 'value': str(time_to_run)}]
            self.job_config['spec']['template']['spec']['containers'][0]['env'] += environment_vars
            self.job = self._create_job()

            self.logger.info(
                'Running Benchmark -> Experiment: {:d}/{:d}'.format(
                    run_nb, runs))
            if self.churn:
                thread = threading.Thread(
                    target=self._run_churn, args=[
                        time_to_start + self.churn.delay], daemon=True)
                thread.start()
                self._wait_on_service(
                    self.job_config['service']['name'], 0, inverse=True)
                self.logger.info('Running with churn')
                if self.churn.synthetic:
                    # Wait for some peers to at least start
                    time.sleep(120)
                    total = [sum(x) for x
                             in zip(*self.churn.churn_params['synthetic'])]
                    # Wait until only stopped containers are still alive
                    self._wait_on_service(
                        self.job_config['service']['name'],
                        containers_nb=total[0],
                        total_nb=total[1])
                else:
                    # TODO not the most elegant solution
                    thread.join()  # Wait for churn to finish
                    time.sleep(300)  # Wait 5 more minutes

            else:
                self.logger.info('Running without churn')
                self._wait_on_job_completion()
            if self.tracker_config:
                self.stop()
            else:
                self.stop()

            self.logger.info('Services removed')
            time.sleep(10)

            if not self.local:
                subprocess.call(
                    'parallel-ssh -t 0 -h config/hosts'
                    ' "mkdir -p {path}/test-{nb}/capture &&'
                    ' mv {path}/*.txt {path}/test-{nb}/ &&'
                    ' mv {path}/capture/*.csv {path}/test-{nb}/capture/"'
                        .format(path=self.cluster_config['cluster_data'],
                                nb=run_nb),
                    shell=True)

            subprocess.call(
                'mkdir -p {path}/test-{nb}/capture'.format(path=log_storage,
                                                           nb=run_nb),
                shell=True)
            subprocess.call(
                'mv {path}/*.txt {path}/test-{nb}/'.format(path=log_storage,
                                                           nb=run_nb),
                shell=True)
            subprocess.call(
                'mv {path}/capture/*.csv {path}/test-{nb}/capture/'.format(
                    path=log_storage, nb=run_nb), shell=True)

        self.logger.info('Benchmark done!')

    def stop(self, is_signal=False):
        """
        Stop the benchmark and get every logs

        :return:
        """
        self.job.delete()
        self.logger.info("Job {:s} was deleted"
                         .format(self.job_config['metadata']['name']))
        if self.tracker_config and self.tracker is not None:
            self.tracker.delete()
            self.logger.info("Deployment {:s} was deleted"
                             .format(self.tracker_config['metadata']['name']))
            process = subprocess.run(['kubectl', 'delete', 'service',
                            self.tracker_config['metadata']['name']],
                           stdout=subprocess.PIPE, encoding='utf-8')
            self.logger.info(process.stdout)
        if not self.local and is_signal:
            time.sleep(15)
            with open('config/hosts', 'r') as file:
                for host in file.read().splitlines():
                    subprocess.call('rsync --remove-source-files '
                                    '-av {:s}:{:s}/*.txt ../data'
                                    .format(host, self.cluster_config['cluster_data']),
                                    shell=True)
                    subprocess.call(
                        'rsync --remove-source-files '
                        '-av {:s}:{:s}/capture/*.csv ../data/capture'
                            .format(host, self.cluster_config['cluster_data']),
                        shell=True)

    def set_logger_level(self, log_level):
        """
        Set the logger level of the object

        :param log_level: The logger level
        :return:
        """
        self.logger.setLevel(log_level)

    def _run_churn(self, time_to_start):
        self.logger.debug('Time to start churn: {:d}'.format(time_to_start))
        if self.churn.synthetic:
            self.logger.info(self.churn.churn_params['synthetic'])
            nodes_trace = NodesTrace(
                synthetic=self.churn.churn_params['synthetic'])
        else:
            real_churn_params = self.churn.churn_params['real_churn']
            nodes_trace = NodesTrace(
                database=real_churn_params['database'],
                min_time=real_churn_params['epoch']
                         + real_churn_params['start_time'],
                max_time=real_churn_params['epoch']
                         + real_churn_params['start_time']
                         + real_churn_params['duration'],
                time_factor=real_churn_params['time_factor'])

        delta = self.churn.period

        # Add initial cluster
        self.logger.debug(
            'Initial size: {}'.format(
                nodes_trace.initial_size()))
        self.churn.add_processes(nodes_trace.initial_size())
        delay = int((time_to_start - (time.time() * 1000)) / 1000)
        self.logger.debug('Delay: {:d}'.format(delay))
        self.logger.info(
            'Starting churn at {:s} UTC' .format(
                datetime.utcfromtimestamp(
                    time_to_start //
                    1000).isoformat()))
        time.sleep(delay)
        self.logger.info('Starting churn')
        nodes_trace.next()
        for size, to_kill, to_create in nodes_trace:
            self.logger.debug('curr_size: {:d}, to_kill: {:d}, to_create {:d}'
                              .format(size, len(to_kill), len(to_create)))
            self.churn.add_suspend_processes(len(to_kill), len(to_create))
            time.sleep(delta / 1000)

        self.logger.info('Churn finished')

    def _create_service(
            self):
        tracker = pykube.Deployment(self.client, self.tracker_config)
        tracker.create()
        self.logger.info("Deployment {:s} was created"
                         .format(self.tracker_config['metadata']['name']))
        # TODO check if it can  be improved
        process = subprocess.run(['kubectl', 'expose', 'deployment',
                       self.tracker_config['metadata']['name']],
                       stdout=subprocess.PIPE, encoding='utf-8')
        self.logger.info(process.stdout)
        return tracker

    def _wait_on_service(self, service_name, containers_nb,
                         total_nb=None, inverse=False):
        def get_nb():
            output = subprocess.check_output(['docker',
                                              'service',
                                              'ls',
                                              '-f',
                                              'name={:s}'.format(service_name)],
                                             universal_newlines=True).splitlines()[1]
            match = re.match(r'.+ (\d+)/(\d+)', output)
            return int(match.group(1)), int(match.group(2))

        if inverse:  # Wait while current nb is equal to containers_nb
            current_nb = containers_nb
            while current_nb == containers_nb:
                self.logger.debug(
                    'current_nb={:d}, containers_nb={:d}'.format(
                        current_nb, containers_nb))
                time.sleep(1)
                current_nb = get_nb()[0]
        else:
            current_nb = -1
            current_total_nb = -1
            while current_nb > containers_nb or current_total_nb != total_nb:
                self.logger.debug(
                    'current_nb={:d}, containers_nb={:d}'.format(
                        current_nb, containers_nb))
                self.logger.debug(
                    'current_total_nb={:d}'.format(current_total_nb))
                time.sleep(5)
                current_nb, current_total_nb = get_nb()
                if not total_nb:
                    total_nb = current_total_nb
                else:
                    self.logger.debug(
                        'current_total_nb={:d}, total_nb={:d}'.format(
                            current_total_nb, total_nb))

    def _wait_on_job_completion(self):
        # TODO improve this code
        needed_completions = self.job_config['spec']['completions']
        completed_process = (subprocess
            .check_output('kubectl get job jgroups-job | '
                          'tail -1 | '
                          'awk \'{print $3}\'',
                          shell=True, universal_newlines=True).strip())
        while int(completed_process) != needed_completions:
            self.logger.debug("Completed processes: {}"
                              .format(completed_process))
            time.sleep(10)
            completed_process = (subprocess
                                 .check_output('kubectl get job jgroups-job | '
                                               'tail -1 | '
                                               'awk \'{print $3}\'',
                                               shell=True,
                                               universal_newlines=True).strip())
        self.logger.info("All processes are completed")
        return

    def _create_job(self):
        job = pykube.Job(self.client, self.job_config)
        job.create()
        self.logger.info("Job {:s} was created"
                         .format(self.job_config['metadata']['name']))
        return job
