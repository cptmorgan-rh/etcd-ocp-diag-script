#!/usr/bin/env python3

import os, glob, sys, json, re, getopt
from datetime import datetime
from collections import Counter
from statistics import median

def extract_json_objects(text):
    '''Find JSON objects in text, and yield the decoded JSON data'''
    for match in re.finditer(r'{.*}', text):
        try:
            yield json.loads(match.group())
        except ValueError:
            pass

def get_etcd_pod(path: str):
    '''Returns the etcd Pod Name'''
    path_elements = path.split('/')
    return path_elements[-1]

def etcd_errors(directories: str):
    '''Searches for common errors in the etcd_errors list'''
    global pod_known
    global etcd_pod
    global rotated_logs
    etcd_errors = [
        'waiting for ReadIndex response took too long, retrying',
        'etcdserver: request timed out',
        'slow fdatasync',
        'apply request took too long',
        'leader is overloaded likely from slow disk',
        'local node might have slow network',
        'elected leader',
        'lost leader',
        'wal: sync duration',
        'the clock difference against peer',
        'lease not found',
        'rafthttp: failed to read',
        'server is likely overloaded',
        'lost the tcp streaming',
        'sending buffer is full',
        'health errors'
    ]
    etcd_output = []
    etcd_count = {}

    for directory in directories:
        if not pod_known:
            etcd_pod = get_etcd_pod(directory)

        if rotated_logs:
            # Check to see if rotated logs exist
            rotated_logs_list = get_rotated_logs(directory)
            if rotated_logs_list:
                # Parse rotated logs if they do exist
                for log in rotated_logs_list:
                    with open(f'{log}', 'r') as file:
                        content = file.read()
                        for error_text in etcd_errors:
                            count = content.count(error_text)
                            if count > 0:
                                key = (etcd_pod, error_text)
                                if key in etcd_count:
                                    etcd_count[key] += count
                                else:
                                    etcd_count[key] = count

        with open(f'{directory}/etcd/etcd/logs/{pod_log_version}.log', 'r') as file:
            content = file.read()
            for error_text in etcd_errors:
                count = content.count(error_text)
                if count > 0:
                    key = (etcd_pod, error_text)
                    if key in etcd_count:
                        etcd_count[key] += count
                    else:
                        etcd_count[key] = count
    if len(etcd_count) != 0:
        etcd_output = [{'POD': pod, 'ERROR': error, 'COUNT': count} for (pod, error), count in etcd_count.items()]
        print_rows(etcd_output)
    else:
        print('No errors found.')
        sys.exit(0)

def msg_count(directories: str, error_txt: str, err_date: str):
    '''Search etcd pod logs for error_txt and returns count'''
    global pod_known
    global etcd_pod
    global rotated_logs
    errors = []
    for directory in directories:
        json_dates: dict = Counter()
        if pod_known != True:
            etcd_pod = get_etcd_pod(directory)
        if rotated_logs:
            #Check to see if rotated logs exist
            rotated_logs_list = get_rotated_logs(directory)
            if rotated_logs_list != []:
                #Parse rotated logs if they do exist
                for log in rotated_logs_list:
                    with open(f'{log}', 'r') as file:
                        for line in file:
                            if err_date_search:
                                if error_txt in line:
                                    if err_date in line:
                                        for result in extract_json_objects(line):
                                            _, ts_time = result.get('ts', 'Unknown').split('T')
                                            hr, min, _ = ts_time.split(':')
                                            json_dates[':'.join([hr, min])] += 1
                            else:
                                if error_txt in line:
                                    for result in extract_json_objects(line):
                                        ts_date, _ = result.get('ts', 'Unknown').split('T')
                                        json_dates[ts_date] += 1
        with open(f'{directory}/etcd/etcd/logs/{pod_log_version}.log', 'r') as file:
            for line in file:
                if err_date_search:
                    if error_txt in line:
                        if err_date in line:
                            for result in extract_json_objects(line):
                                _, ts_time = result.get('ts', 'Unknown').split('T')
                                hr, min, _ = ts_time.split(':')
                                json_dates[':'.join([hr, min])] += 1
                else:
                    if error_txt in line:
                        for result in extract_json_objects(line):
                            ts_date, _ = result.get('ts', 'Unknown').split('T')
                            json_dates[ts_date] += 1
    for date, count in json_dates.items():
        errors.append({
            'POD': etcd_pod,
            'DATE': date,
            'COUNT': count
        })
    if len(errors) != 0:
        print_rows(errors)
    else:
        print(f'No errors for "{error_txt}".')
        sys.exit(0)

def print_rows(errors_list):
    '''Prints results in a fixed width tab format'''
    max_widths = {}
    # Get Max Width of Keys
    for row in errors_list:
        for key, value in row.items():
            max_widths[key] = max(max_widths.get(key, 0), len(str(value)))

    # Print headers
    for key in errors_list[0].keys():
        print(f'{key:{max_widths[key]}}', end='\t')
    print()

    # Print data
    for row in errors_list:
        for key in row.keys():
            print(f'{row[key]:{max_widths[key]}}', end='\t')
        print()

def get_dirs():
    '''Returns the directory for etcd pods'''
    input_dir = os.path.join(mg_path, pod_glob)
    pod_list = glob.glob(input_dir, recursive=True)
    pattern = r'etcd-(?!guard)(?!quorum-guard)'
    return [pod for pod in pod_list if re.search(pattern,pod)]

def get_rotated_logs(dir_path: str):
    '''Returns rotated logs if they exist'''
    if os.listdir(dir_path):
        rotated_logs = []
        rotated_files = glob.glob(f'{dir_path}/etcd/etcd/logs/rotated/*', recursive=True)
        pattern = r'[0-9]\.log\.+(?!\.gz)'
        for log in rotated_files:
            if re.search(pattern, log):
                rotated_logs.append(log)
        sorted_roated_logs = sorted(rotated_logs, key=extract_datetime)
        return sorted_roated_logs

def extract_datetime(file_path):
    date_pattern = re.compile(r'\d{8}-\d{6}')
    # Extract the date and time part
    match = date_pattern.search(file_path)
    if match:
        date_str = match.group()
        # Convert the date string to a datetime object
        return datetime.strptime(date_str, '%Y%m%d-%H%M%S')
    return datetime.min  # Return the earliest datetime if no match is found

def parse_file(file_path: str, error_txt: str):
    '''Determines if the error_txt exists in the file and then parses if true'''
    with open(file_path, 'r') as file:
        file_contents = file.read()
        if error_txt in file_contents:
            return True
        else:
            return False

def etcd_stats(directories: str, error_txt: str):
    '''Returns the performance stats of the etcd pod'''
    global rotated_logs
    for directory in directories:
        # Set Variables
        first_err = None
        last_err = None
        etcd_pod = get_etcd_pod(directory)
        error_count = 0
        etcd_error_stats: list = []
        if rotated_logs:
            #Check to see if rotated logs exist
            rotated_logs_list = get_rotated_logs(directory)
            if rotated_logs_list != []:
                #Parse rotated logs if they do exist
                for log in rotated_logs_list:
                    with open(f'{log}', 'r') as file:
                        for line in file:
                            # Check if the line contains the following error
                            if error_txt in line:
                                #Count the amount of took too long errors
                                error_count += 1
                                # Find the last error's timestamp
                                last_err = re.findall(r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?=\.\d+Z|\s|\Z)', line)
                                # Find the first error's timestamp
                                if first_err == None:
                                    first_err = re.findall(r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?=\.\d+Z|\s|\Z)', line)
                                # Sending the data to have the JSON Extracted
                                for result in extract_json_objects(line):
                                    # Set the variable based on the took results
                                    took_time = result['took']
                                    # Collect the expected time
                                    expected_time = result['expected-duration']
                                    # Check if the time is in ms and convert
                                    if 'ms' in took_time:
                                        etcd_error_stats.append(float(took_time.removesuffix('ms')))
                                    # Check if the time is in seconds and convert
                                    elif 's' in took_time:
                                        etcd_error_stats.append(float(took_time.removesuffix('s')) * 1000)
                                    # Check if the time is in minutes and convert
                                    elif 'm' in took_time:
                                        took_min, took_sec = took_time.split('m')
                                        etcd_error_stats.append(((float(took_min) * 60000) + (float(took_sec) * 1000)))
        #Check to see if the error_txt exists prior to parsing the file
        if parse_file(f'{directory}/etcd/etcd/logs/{pod_log_version}.log', error_txt):
            # Open each pod log (current.log, previous.log) file to be read
            with open(f'{directory}/etcd/etcd/logs/{pod_log_version}.log', 'r') as file:
                for line in file:
                    # Check if the line contains the following error
                    if error_txt in line:
                        #Count the amount of took too long errors
                        error_count += 1
                        # Find the last error's timestamp
                        last_err = re.findall(r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?=\.\d+Z|\s|\Z)', line)
                        # Find the first error's timestamp
                        if first_err == None:
                            first_err = re.findall(r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?=\.\d+Z|\s|\Z)', line)
                        # Sending the data to have the JSON Extracted
                        for result in extract_json_objects(line):
                            # Set the variable based on the took results
                            took_time = result['took']
                            # Collect the expected time
                            expected_time = result['expected-duration']
                            # Check if the time is in ms and convert
                            if 'ms' in took_time:
                                etcd_error_stats.append(float(took_time.removesuffix('ms')))
                            # Check if the time is in seconds and convert
                            elif 's' in took_time:
                                etcd_error_stats.append(float(took_time.removesuffix('s')) * 1000)
                            # Check if the time is in minutes and convert
                            elif 'm' in took_time:
                                took_min, took_sec = took_time.split('m')
                                etcd_error_stats.append(((float(took_min) * 60000) + (float(took_sec) * 1000)))
        print_stats(error_txt, etcd_pod, first_err, last_err, etcd_error_stats, error_count, expected_time)

def print_stats(error_txt: str, etcd_pod: str, first_err: str, last_err: list, etcd_error_stats: list, error_count: int, expected_time: str):
    '''Prints the etcd stats provided by etcd_stats function'''
    # Print out the data
    print(f'Stats about etcd "{error_txt}" messages: {etcd_pod}')
    print(f'\tFirst Occurance: {first_err[0]}')
    print(f'\tLast Occurance: {last_err[0]}')
    print(f'\tMaximum: {max(etcd_error_stats,key=lambda x:float(x)):.4f}ms')
    print(f'\tMinimum: {min(etcd_error_stats,key=lambda x:float(x)):.4f}ms')
    print(f'\tMedian: {median(etcd_error_stats):.4f}ms')
    print(f'\tAverage: {sum(etcd_error_stats) / (len(etcd_error_stats) + 1):.4f}ms')
    print(f'\tCount: {error_count}')
    print(f'\tExpected: {expected_time}',end='\n\n')

def usage():
    '''Prints the usage information for the program'''
    print('''
USAGE: etcd-ocp-diag.py
etcd-ocp-diag is a simple script which provides reporting on etcd errors
in a must-gather/inspect to pinpoint when slowness is occuring.

Options:
--path         Sets the path of the must-gather
                Example: etcd-ocp-diag.py --path <MG_PATH>
--errors       Displays known errors in the etcd logs along with their count
--stats        Displays Stats and Calculates Avg, Max, Min, and Median times for etcd errors
--ttl          Displays 'took too long' errors
--heartbeat    Displays 'leader failed to send out heartbeat on time' errors
--election     Displays 'elected leader' and 'lost leader' errors
--fdatasync    Displays 'slow fdatasync' errors
--buffer       Displays 'sending buffer is full' errors
--pod          Specify the name of the pod to search
                Example: etcd-ocp-diag.py --path <MG_PATH> --ttl --pod etcd-ocp-master2
--date         Specify the date in YYYY-MM-DD format
                Example: etcd-ocp-diag.py --path <MG_PATH> --ttl --pod etcd-ocp-master2 --date 2023-08-30
                Example: etcd-ocp-diag.py --path <MG_PATH> --election --date 2023-08-30
--previous     Uses the previous.log. Can't not be combined with --rotated
--rotated      Includes checking rotated logs for errors and stats. Rotated logs *MUST* be previously extracted.
--help         Shows this help message
''')

def main():

    global mg_path
    global pod_glob
    global err_date_search
    global err_date
    global pod_known
    global etcd_pod
    global pod_log_version
    global rotated_logs

    pod_log_version = 'current'
    pod_glob = '**/openshift-etcd/pods/etcd-*'

    args, values = getopt.getopt(sys.argv[1:],'', ['path=', 'ttl', 'heartbeat', 'election', 'fdatasync', 'buffer', 'pod=', 'date=', 'help', 'errors', 'stats', 'previous', 'rotated'])

    if any(arg[0] == '--path' for arg in args):
        if len(args) == 1:
            print('Please provide an option along with the path to the must-gather')
            print('Example: etcd-ocp-diag.py --path <MG_PATH> --ttl ')
            usage()
            sys.exit(1)

        if any(arg[0] == '--previous' for arg in args):
            pod_log_version = 'previous'
        else:
            pod_log_version = 'current'

        if any(arg[0] == '--rotated' for arg in args):
            rotated_logs = True

        if any(arg[0] == '--rotated' for arg in args) and any(arg[0] == '--previous' for arg in args):
            print('ERROR: Please select previous or rotated option.')
            sys.exit(1)

        for currentArgument, currentValue in args:
            if currentArgument in '--stats':
                for value in ['apply request took too long', 'slow fdatasync']:
                    etcd_stats(get_dirs(), value)
                sys.exit(0)
            elif currentArgument in '--path':
                mg_path = currentValue
            elif currentArgument in '--ttl':
                error_txt = 'apply request took too long'
            elif currentArgument in '--heartbeat':
                error_txt = 'failed to send out heartbeat'
            elif currentArgument in '--election':
                error_txt = 'election'
            elif currentArgument in '--fdatasync':
                error_txt = 'slow fdatasync'
            elif currentArgument in '--buffer':
                error_txt = 'sending buffer is full'
            elif currentArgument in '--pod':
                pod_glob = f'**/namespaces/openshift-etcd/pods/{currentValue}'
                pod_known = True
                etcd_pod = currentValue
            elif currentArgument in '--date':
                err_date = currentValue
                err_date_search = True
            elif currentArgument in '--errors':
                etcd_errors(get_dirs())
                sys.exit(0)
            elif currentArgument in '--help':
                usage()
                sys.exit(1)
        msg_count(get_dirs(),error_txt, err_date)
    else:
        print('Please provide a path for the must-gather')
        usage()
        sys.exit(1)

if __name__ == '__main__':
    mg_path: str = ''
    pod_glob: str = ''
    pod_known = False
    etcd_pod: str = ''
    pod_log_version: str = ''
    err_date_search = False
    err_date: str = ''
    rotated_logs = False
    main()
