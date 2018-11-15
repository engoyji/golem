import os
import pathlib
import queue
import re
import subprocess
import sys
import threading
import tempfile

from . import tasks


def mkdatadir(role: str):
    return tempfile.mkdtemp(prefix='golem-{}-'.format(role.lower()))


def report_termination(exit_code, node_type):
    if exit_code:
        print("%s subprocess exited with: %s" % (node_type, exit_code))


def gracefully_shutdown(process: subprocess.Popen, node_type: str):
    process.terminate()
    try:
        print("Waiting for the %s subprocess to shut-down" % node_type)
        exit_code = process.wait(60)
        report_termination(exit_code, node_type)
    except subprocess.TimeoutExpired:
        print(
            "%s graceful shutdown timed-out, issuing sigkill." % node_type)
        process.kill()


def run_golem_node(node_type: str, *args):
    node_file = node_type + '.py'
    cwd = pathlib.Path(os.path.realpath(__file__)).parent
    node_process = subprocess.Popen(
        args=['python', str(cwd / 'nodes' / node_file), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    return node_process


def get_output_queue(process: subprocess.Popen):
    def output_queue(stream, q):
        for line in iter(stream.readline, b''):
            q.put(line)

    q: queue.Queue = queue.Queue()  # wth mypy?
    qt = threading.Thread(target=output_queue, args=[process.stdout, q])
    qt.daemon = True
    qt.start()
    return q


def print_output(q: queue.Queue, prefix):
    try:
        for line in iter(q.get_nowait, None):
            if line is None:
                break
            sys.stdout.write(prefix + line.decode('utf-8'))
    except queue.Empty:
        pass


def clear_output(q: queue.Queue):
    try:
        while True:
            q.get_nowait()
    except queue.Empty:
        pass


def search_output(q: queue.Queue, pattern):
    try:
        for line in iter(q.get_nowait, None):
            if line:
                line = line.decode('utf-8')
                m = re.match(pattern, line)
                if m:
                    return m
    except queue.Empty:
        pass
    return None


def construct_test_task(task_package_name, output_path, task_settings):
    settings = tasks.get_settings(task_settings)
    cwd = pathlib.Path(os.path.realpath(__file__)).parent
    tasks_path = (cwd / 'tasks' / task_package_name).glob('*')
    settings['resources'] = [str(f) for f in tasks_path]
    settings['options']['output_path'] = output_path
    return settings
