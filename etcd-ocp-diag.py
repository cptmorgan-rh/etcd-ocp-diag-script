#!/usr/bin/env python3

import os, glob, sys, json, re, getopt, argparse
from datetime import datetime
from collections import Counter
from statistics import median
from datetime import datetime

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
                for date, count in json_dates.items():
                    errors.append({
                    'POD': etcd_pod,
                    'DATE': date,
                    'COUNT': count
                })
                json_dates.clear()
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
            json_dates.clear()
    if len(errors) != 0:
        if compare_times == True:
            compare(errors)
        else:
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

def compare(errors_list):
    '''Compares error counts for the same DATE across different PODs'''
    # Create a dictionary to group counts by DATE
    date_groups = {}

    # Group counts by date
    for entry in errors_list:
        date = entry['DATE']
        if date not in date_groups:
            date_groups[date] = []
        date_groups[date].append(entry)

    # Print results for each date with more than one pod
    for date, entries in date_groups.items():
        if len(entries) > 1:  # Only compare if there are multiple pods
            print(f'Date: {date}')
            print(f'{"POD":<30} {"COUNT":<10}')
            for entry in entries:
                print(f'{entry["POD"]:<30} {entry["COUNT"]:<10}')
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
        etcd_pod = get_etcd_pod(directory)
        if rotated_logs:
            #Check to see if rotated logs exist
            rotated_logs_list = get_rotated_logs(directory)
            if rotated_logs_list != []:
                #Parse rotated logs if they do exist
                for log in rotated_logs_list:
                    with open(f'{log}', 'r') as file:
                        calc_etcd_stats(error_txt,file,etcd_pod)
        #Check to see if the error_txt exists prior to parsing the file
        if parse_file(f'{directory}/etcd/etcd/logs/{pod_log_version}.log', error_txt):
            # Open each pod log (current.log, previous.log) file to be read
            with open(f'{directory}/etcd/etcd/logs/{pod_log_version}.log', 'r') as file:
                calc_etcd_stats(error_txt,file,etcd_pod)


def calc_etcd_stats(error_txt, file, etcd_pod):
    '''Calculate the First and Last error timestamp, and Max, Mediam and Average time and count'''
    # Set Variables
    first_err = None
    last_err = None
    error_count = 0
    etcd_error_stats: list = []
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
    print(f'\tFirst Occurrence: {first_err[0]}')
    print(f'\tLast Occurrence: {last_err[0]}')
    print(f'\tMaximum: {max(etcd_error_stats,key=lambda x:float(x)):.4f}ms')
    print(f'\tMinimum: {min(etcd_error_stats,key=lambda x:float(x)):.4f}ms')
    print(f'\tMedian: {median(etcd_error_stats):.4f}ms')
    print(f'\tAverage: {sum(etcd_error_stats) / (len(etcd_error_stats) + 1):.4f}ms')
    print(f'\tCount: {error_count}')
    print(f'\tExpected: {expected_time}',end='\n\n')


def validate_date(date_string):
    """Validate the date string is in YYYY-MM-DD format."""
    try:
        # Attempt to parse the date string
        datetime.strptime(date_string, '%Y-%m-%d')
        return date_string
    except ValueError:
        raise argparse.ArgumentTypeError(f"Date must be in YYYY-MM-DD format: '{date_string}'")

def main():
    global mg_path, pod_glob, err_date_search, err_date, pod_known, etcd_pod, pod_log_version, rotated_logs, compare_times

    pod_log_version = 'current'
    pod_glob = '**/openshift-etcd/pods/etcd-*'
    error_txt = None

    parser = argparse.ArgumentParser(description='Process etcd logs and gather statistics.')

    # Adding arguments
    parser.add_argument('--path', type=str, required=True, help='Path to the must-gather')
    parser.add_argument('--ttl', action='store_true', help='Check apply request took too long')
    parser.add_argument('--heartbeat', action='store_true', help='Check failed to send out heartbeat')
    parser.add_argument('--election', action='store_true', help='Check election issues')
    parser.add_argument('--fdatasync', action='store_true', help='Check slow fdatasync')
    parser.add_argument('--buffer', action='store_true', help='Check sending buffer is full')
    parser.add_argument('--etcd_timeout', action='store_true', help='Check etcdserver: request timed out')
    parser.add_argument('--pod', type=str, help='Specify the pod to analyze')
    parser.add_argument('--date', type=validate_date, help='Specify date for error search in YYYY-MM-DD format')
    parser.add_argument('--compare', action='store_true', help='Display only dates or times that happen in all pods')
    parser.add_argument('--errors', action='store_true', help='Display etcd errors')
    parser.add_argument('--stats', action='store_true', help='Display etcd stats')
    parser.add_argument('--previous', action='store_true', help='Use previous logs')
    parser.add_argument('--rotated', action='store_true', help='Use rotated logs')

    args = parser.parse_args()

    if args.previous and args.rotated:
        print('ERROR: Please select either previous or rotated option.')
        sys.exit(1)

    if args.previous:
        pod_log_version = 'previous'
    if args.rotated:
        rotated_logs = True

    if args.compare:
        compare_times = True
    mg_path = args.path

    # Set the error text based on the selected options
    error_options = {
        '--ttl': 'apply request took too long',
        '--heartbeat': 'failed to send out heartbeat',
        '--election': 'election',
        '--fdatasync': 'slow fdatasync',
        '--buffer': 'sending buffer is full',
        '--etcd_timeout': 'etcdserver: request timed out',
    }

    for option in error_options.keys():
        if getattr(args, option[2:]):  # Remove the '--' and check if it's True
            error_txt = error_options[option]

    if args.pod:
        pod_glob = f'**/namespaces/openshift-etcd/pods/{args.pod}'
        pod_known = True
        etcd_pod = args.pod

    if args.date:
        err_date = args.date
        err_date_search = True

    if args.stats:
        for value in ['apply request took too long', 'slow fdatasync']:
            etcd_stats(get_dirs(), value)
        sys.exit(0)

    if args.errors:
        etcd_errors(get_dirs())
        sys.exit(0)

    msg_count(get_dirs(), error_txt, err_date)


if __name__ == '__main__':
    mg_path: str = ''
    pod_glob: str = ''
    pod_known = False
    etcd_pod: str = ''
    pod_log_version: str = ''
    err_date_search = False
    err_date: str = ''
    rotated_logs = False
    compare_times = False
    main()
