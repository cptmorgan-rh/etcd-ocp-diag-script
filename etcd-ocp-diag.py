#!/usr/bin/env python3
"""Parses OpenShift Must-Gathers to review etcd performance and errors."""

import argparse
import json
import mimetypes
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from statistics import median


def extract_json_objects(text: str) -> json.loads:
    """Find JSON objects in text, and yield the decoded JSON data

    Args:
        text (str): Error Text to be found by RegEx

    Yields:
        Iterator[json.loads]: Returns json results from etcd pods that match the RegEx
    """
    for match in re.finditer(r"{.*}", text):
        try:
            yield json.loads(match.group())
        except ValueError:
            pass


def get_etcd_pod(path: str) -> str:
    """Returns the etcd Pod Name

    Args:
        path (str): Directory Path to etcd pod

    Returns:
        str: etcd pod name
    """
    path_elements = path.split("/")
    return path_elements[-1]


def etcd_errors(
    directories: list,
    pod_known: bool,
    etcd_pod_name: str,
    pod_log_version: str,
    rotated_logs: bool,
) -> None:
    """Searches for common errors in the etcd_errors list

    Args:
        directories (list): List of directories for the etcd pods
        pod_known (bool): If True; the etcd pod name is known
        etcd_pod_name (str): Name of the etcd Pod
        pod_log_version (str): If the pod is Current or Previous
        rotated_logs (bool): If True; look at rotated log files
    """
    etcd_error_list = [
        "waiting for ReadIndex response took too long, retrying",
        "etcdserver: request timed out",
        "slow fdatasync",
        "apply request took too long",
        "leader is overloaded likely from slow disk",
        "local node might have slow network",
        "elected leader",
        "lost leader",
        "wal: sync duration",
        "the clock difference against peer",
        "lease not found",
        "rafthttp: failed to read",
        "server is likely overloaded",
        "lost the tcp streaming",
        "sending buffer is full",
        "health errors",
        "request stats",
    ]
    etcd_output = []
    etcd_count = {}

    for directory in directories:
        directory_path = Path(directory)
        if not pod_known:
            etcd_pod_name = get_etcd_pod(directory_path)

        if rotated_logs:
            # Check to see if rotated logs exist
            rotated_logs_list = get_rotated_logs(directory_path)
            if rotated_logs_list:
                # Parse rotated logs if they do exist
                for log in rotated_logs_list:
                    log_path = Path(log)
                    mime_type, _ = mimetypes.guess_type(log)
                    if mime_type == "text/plain":
                        with log_path.open(encoding="utf-8", mode="r") as file:
                            content = file.read()
                            for error_text in etcd_error_list:
                                count = content.count(error_text)
                                if count > 0:
                                    key = (etcd_pod_name, error_text)
                                    if key in etcd_count:
                                        etcd_count[key] += count
                                    else:
                                        etcd_count[key] = count

        log_file_path = (
            directory_path / "etcd" / "etcd" / "logs" / f"{pod_log_version}.log"
        )
        with log_file_path.open(encoding="utf-8", mode="r") as file:
            content = file.read()
            for error_text in etcd_error_list:
                count = content.count(error_text)
                if count > 0:
                    key = (etcd_pod_name, error_text)
                    if key in etcd_count:
                        etcd_count[key] += count
                    else:
                        etcd_count[key] = count
    if len(etcd_count) != 0:
        etcd_output = [
            {"POD": pod, "ERROR": error, "COUNT": count}
            for (pod, error), count in etcd_count.items()
        ]
        print_rows(etcd_output)
    else:
        print("No errors found.")
        sys.exit(0)


def msg_count(
    directories: list,
    error_txt: str,
    err_date: str,
    pod_known: bool,
    err_date_search: bool,
    etcd_pod_name: str,
    pod_log_version: str,
    rotated_logs: bool,
    compare_times: bool,
) -> None:
    """Search etcd pod logs for error_txt and returns count

    Args:
        directories (list): List of directories for the etcd pods
        error_txt (str): Error Text to search for
        err_date (str): Error Date to search for
        pod_known (bool): If true; etcd pod name is known
        err_date_search (bool): _description_
        etcd_pod_name (str): _description_
        pod_log_version (str): _description_
        rotated_logs (bool): _description_
        compare_times (bool): _description_
    """
    errors = []
    for directory in directories:
        directory_path = Path(directory)
        json_dates: dict = Counter()
        if not pod_known:
            etcd_pod_name = get_etcd_pod(directory_path)

        if rotated_logs:
            # Check to see if rotated logs exist
            rotated_logs_list = get_rotated_logs(directory_path)

            if rotated_logs_list:
                # Parse rotated logs if they exist
                for log in rotated_logs_list:
                    log_path = Path(log)
                    mime_type, _ = mimetypes.guess_type(log)

                    if mime_type == "text/plain":
                        with log_path.open(encoding="utf-8") as file:
                            for line in file:
                                if (
                                    err_date_search
                                    and error_txt in line
                                    and err_date in line
                                ) or (
                                    not err_date_search
                                    and error_txt in line
                                    ):
                                    for result in extract_json_objects(line):
                                        ts_date = result.get("ts", "Unknown").split("T")[0]
                                        json_dates[ts_date] += 1
                        for date, count in json_dates.items():
                            errors.append(
                                {"POD": etcd_pod_name, "DATE": date, "COUNT": count}
                            )
                        json_dates.clear()

        log_file_path = (
            directory_path / "etcd" / "etcd" / "logs" / f"{pod_log_version}.log"
        )
        with log_file_path.open(encoding="utf-8", mode="r") as file:
            for line in file:
                if (err_date_search and error_txt in line and err_date in line) or (
                    not err_date_search and error_txt in line
                ):
                    for result in extract_json_objects(line):
                        ts_date = result.get("ts", "Unknown").split("T")[0]
                        json_dates[ts_date] += 1
        for date, count in json_dates.items():
            errors.append({"POD": etcd_pod_name, "DATE": date, "COUNT": count})
        json_dates.clear()
    if len(errors) != 0:
        if compare_times is True:
            compare(errors)
        else:
            print_rows(errors)
    else:
        print(f'No errors for "{error_txt}".')
        sys.exit(0)


def print_rows(errors_list: list) -> None:
    """Prints results in a fixed width tab format"""
    max_widths = {}
    # Get Max Width of Keys
    for row in errors_list:
        for key, value in row.items():
            max_widths[key] = max(max_widths.get(key, 0), len(str(value)))

    # Print headers
    for key in errors_list[0].keys():
        print(f"{key:{max_widths[key]}}", end="\t")
    print()

    # Print data
    for row in errors_list:
        for key in row.keys():
            print(f"{row[key]:{max_widths[key]}}", end="\t")
        print()


def compare(errors_list: list) -> None:
    """Compares error counts for the same DATE across different PODs"""
    # Create a dictionary to group counts by DATE
    date_groups = {}

    # Group counts by date
    for entry in errors_list:
        date = entry["DATE"]
        if date not in date_groups:
            date_groups[date] = []
        date_groups[date].append(entry)

    # Print results for each date with more than one pod
    for date, entries in date_groups.items():
        if len(entries) > 1:  # Only compare if there are multiple pods
            print(f"Date: {date}")
            print(f"{'POD':<30} {'COUNT':<10}")
            for entry in entries:
                print(f"{entry['POD']:<30} {entry['COUNT']:<10}")
            print()


def get_dirs(mg_path: str, pod_glob: str) -> list[str]:
    """Returns the directory for etcd pods"""
    input_dir = Path(mg_path) / pod_glob
    pod_list = list(input_dir.rglob("*"))
    pattern = r"etcd-(?!guard)(?!quorum-guard)"
    return [pod for pod in pod_list if re.search(pattern, pod.name)]


def get_rotated_logs(dir_path: str) -> list:
    """Returns rotated logs if they exist"""
    dir_path = Path(dir_path)

    if any(dir_path.iterdir()):  # Check if the directory is not empty
        rotated_log_names = []
        rotated_file_list = dir_path.glob("etcd/etcd/logs/rotated/*")

        pattern = r"[0-9]\.log\.+(?!\.gz)"
        for log in rotated_file_list:
            if re.search(pattern, log.name):  # Use log.name to get the filename
                rotated_log_names.append(str(log))  # Convert Path to string

        sorted_rotated_logs = sorted(rotated_log_names, key=extract_datetime)
        return sorted_rotated_logs


def extract_datetime(file_path) -> datetime:
    """Extracts Date / Time for Rotated Logs"""
    date_pattern = re.compile(r"\d{8}-\d{6}")
    # Extract the date and time part
    match = date_pattern.search(file_path)
    if match:
        date_str = match.group()
        # Convert the date string to a datetime object
        return datetime.strptime(date_str, "%Y%m%d-%H%M%S")
    return datetime.min  # Return the earliest datetime if no match is found


def parse_file(file_path: str, error_txt: str) -> bool:
    """Determines if the error_txt exists in the file and then parses if true"""
    file_path = Path(file_path)

    with file_path.open(encoding="utf-8") as file:
        file_contents = file.read()
        return error_txt in file_contents


def etcd_stats(
    directories: list, error_txt: str, pod_log_version: str, rotated_logs: bool
) -> None:
    """Returns the performance stats of the etcd pod"""

    for directory in directories:
        etcd_pod_name = get_etcd_pod(directory)
        directory_path = Path(directory)  # Convert to Path object

        if rotated_logs:
            # Check to see if rotated logs exist
            rotated_logs_list = get_rotated_logs(directory)
            if rotated_logs_list:
                # Parse rotated logs if they do exist
                for log in rotated_logs_list:
                    if parse_file(log, error_txt):
                        with log.open(encoding="utf-8") as file:
                            calc_etcd_stats(
                                error_txt, file, etcd_pod_name, rotated=True
                            )

        # Check to see if the error_txt exists prior to parsing the file
        pod_log_path = (
            directory_path / "etcd" / "etcd" / "logs" / f"{pod_log_version}.log"
        )
        if parse_file(pod_log_path, error_txt):
            # Open each pod log (current.log, previous.log) file to be read
            with pod_log_path.open(encoding="utf-8") as file:
                calc_etcd_stats(error_txt, file, etcd_pod_name, rotated=False)


def calc_etcd_stats(error_txt: str, file, etcd_pod_name: str, rotated: bool) -> None:
    """Calculate the First and Last error timestamp, and Max, Mediam and Average time and count"""
    # Set Variables
    first_err = None
    last_err = None
    expected_time = None
    error_count = 0
    etcd_error_stats: list = []
    for line in file:
        # Check if the line contains the following error
        if error_txt in line:
            # Count the amount of took too long errors
            error_count += 1
            # Find the last error's timestamp
            last_err = re.findall(
                r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?=\.\d+Z|\s|\Z)", line
            )
            # Find the first error's timestamp
            if first_err is None:
                first_err = re.findall(
                    r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?=\.\d+Z|\s|\Z)", line
                )
            # Sending the data to have the JSON Extracted
            for result in extract_json_objects(line):
                # Set the variable based on the took results
                took_time = result["took"]
                # Collect the expected time
                expected_time = result["expected-duration"]
                # Check if the time is in ms and convert
                if "ms" in took_time:
                    etcd_error_stats.append(float(took_time.removesuffix("ms")))
                # Check if the time is in minutes and convert
                elif "m" in took_time:
                    took_min, took_sec = took_time.split("m")
                    took_sec = took_sec.removesuffix("s")
                    etcd_error_stats.append(
                        ((float(took_min) * 60000) + (float(took_sec) * 1000))
                    )
                # Check if the time is in seconds and convert
                elif "s" in took_time:
                    etcd_error_stats.append(float(took_time.removesuffix("s")) * 1000)

    print_stats(
        error_txt,
        etcd_pod_name,
        first_err,
        last_err,
        etcd_error_stats,
        error_count,
        expected_time,
        rotated,
    )


def print_stats(
    error_txt: str,
    etcd_pod_name: str,
    first_err: str,
    last_err: list,
    etcd_error_stats: list,
    error_count: int,
    expected_time: str,
    rotated: bool,
) -> None:
    """Prints the etcd stats provided by etcd_stats function"""
    # Print out the data
    if not rotated:
        print(f'Stats about etcd "{error_txt}" messages: {etcd_pod_name}')
    else:
        print(
            f'Stats about etcd "{error_txt}" messages: {etcd_pod_name}\'s rotated log:'
        )
    print(f"\tFirst Occurrence: {first_err[0]}")
    print(f"\tLast Occurrence: {last_err[0]}")
    print(f"\tMaximum: {max(etcd_error_stats, key=lambda x: float(x)):.4f}ms")
    print(f"\tMinimum: {min(etcd_error_stats, key=lambda x: float(x)):.4f}ms")
    print(f"\tMedian: {median(etcd_error_stats):.4f}ms")
    print(f"\tAverage: {sum(etcd_error_stats) / (len(etcd_error_stats) + 1):.4f}ms")
    print(f"\tCount: {error_count}")
    print(f"\tExpected: {expected_time}", end="\n\n")


def validate_date(date_string) -> datetime:
    """Validate the date string is in YYYY-MM-DD format."""
    try:
        # Attempt to parse the date string
        datetime.strptime(date_string, "%Y-%m-%d")
        return date_string
    except ValueError as e:
        raise argparse.ArgumentTypeError(
            f"Date must be in YYYY-MM-DD format: '{date_string}'"
        ) from e


def main():
    """Primary function"""
    # Set Vars
    compare_times: bool = False
    error_txt = None
    err_date: str = ""
    err_date_search: bool = False
    etcd_pod: str = ""
    mg_path: str = ""
    pod_glob: str = "**/openshift-etcd/pods/etcd-*"
    pod_known: bool = False
    pod_log_version: str = "current"
    rotated_logs: bool = False

    parser = argparse.ArgumentParser(
        description="Process etcd logs and gather statistics."
    )

    # Adding arguments
    parser.add_argument(
        "--path", type=str, required=True, help="Path to the must-gather"
    )
    parser.add_argument(
        "--ttl", action="store_true", help="Check apply request took too long"
    )
    parser.add_argument(
        "--heartbeat", action="store_true", help="Check failed to send out heartbeat"
    )
    parser.add_argument(
        "--election", action="store_true", help="Checks for leader elections messages"
    )
    parser.add_argument(
        "--lost_leader", action="store_true", help="Checks for lost leader errors"
    )
    parser.add_argument("--fdatasync", action="store_true", help="Check slow fdatasync")
    parser.add_argument(
        "--buffer", action="store_true", help="Check sending buffer is full"
    )
    parser.add_argument(
        "--etcd_timeout",
        action="store_true",
        help="Check etcdserver: request timed out",
    )
    parser.add_argument("--pod", type=str, help="Specify the pod to analyze")
    parser.add_argument(
        "--date",
        type=validate_date,
        help="Specify date for error search in YYYY-MM-DD format",
    )
    parser.add_argument(
        "--compare",
        action="store_true",
        help="Display only dates or times that happen in all pods",
    )
    parser.add_argument("--errors", action="store_true", help="Display etcd errors")
    parser.add_argument("--stats", action="store_true", help="Display etcd stats")
    parser.add_argument("--previous", action="store_true", help="Use previous logs")
    parser.add_argument("--rotated", action="store_true", help="Use rotated logs")

    args = parser.parse_args()

    if args.previous and args.rotated:
        print("ERROR: Please select either previous or rotated option.")
        sys.exit(1)

    if args.previous:
        pod_log_version = "previous"
    if args.rotated:
        rotated_logs = True

    if args.compare:
        compare_times = True
    mg_path = args.path

    # Set the error text based on the selected options
    error_options = {
        "--ttl": "apply request took too long",
        "--heartbeat": "failed to send out heartbeat",
        "--election": "elected leader",
        "--lost_leader": "lost leader",
        "--fdatasync": "slow fdatasync",
        "--buffer": "sending buffer is full",
        "--etcd_timeout": "etcdserver: request timed out",
    }

    for option, error_query in error_options.items():
        if getattr(args, option[2:]):  # Remove the '--' and check if it's True
            error_txt = error_query

    if args.pod:
        pod_glob = f"**/namespaces/openshift-etcd/pods/{args.pod}"
        pod_known = True
        etcd_pod = args.pod

    if args.date:
        err_date = args.date
        err_date_search = True

    if args.stats:
        for value in ["apply request took too long", "slow fdatasync"]:
            etcd_stats(
                get_dirs(mg_path, pod_glob), value, pod_log_version, rotated_logs
            )
        sys.exit(0)

    if args.errors:
        etcd_errors(
            get_dirs(mg_path, pod_glob),
            pod_known,
            etcd_pod,
            pod_log_version,
            rotated_logs,
        )
        sys.exit(0)

    msg_count(
        get_dirs(mg_path, pod_glob),
        error_txt,
        err_date,
        pod_known,
        err_date_search,
        etcd_pod,
        pod_log_version,
        rotated_logs,
        compare_times,
    )


if __name__ == "__main__":
    main()
