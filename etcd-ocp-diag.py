#!/usr/bin/env python3
"""Parses OpenShift Must-Gathers to review etcd performance and errors."""

import argparse
import json
import mimetypes
import re
import shlex
import signal
import subprocess
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from statistics import median
from typing import Any, Iterator, Optional


def extract_json_objects(text: str) -> Iterator[Any]:
    """Find JSON objects in text, and yield the decoded JSON data.

    Args:
        text: Error text to be found by RegEx

    Yields:
        JSON results from etcd pods that match the RegEx
    """
    for match in re.finditer(r"{.*}", text):
        try:
            yield json.loads(match.group())
        except ValueError:
            pass


def get_etcd_pod(directory_path: Path) -> str:
    """Returns the etcd Pod Name.

    Args:
        directory_path: Directory path to etcd pod

    Returns:
        etcd pod name
    """
    path = str(directory_path)
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
    # Sort directories alphabetically by pod name
    sorted_directories = sorted(directories, key=lambda d: get_etcd_pod(Path(d)))

    for directory in sorted_directories:
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
        # Sort by POD name alphabetically
        etcd_output.sort(key=lambda x: x["POD"])
        print_rows(etcd_output)
    else:
        print("No errors found.")


def _convert_took_to_ms(took_time: str) -> float:
    """Convert took time string to milliseconds

    Args:
        took_time: Time string (e.g., "100ms", "1.5s", "1m30s")

    Returns:
        Time in milliseconds as float
    """
    # Check if the time is in ms and convert
    if "ms" in took_time:
        return float(took_time.removesuffix("ms"))
    # Check if the time is in minutes and convert
    elif "m" in took_time:
        took_min, took_sec = took_time.split("m")
        took_sec = took_sec.removesuffix("s")
        return (float(took_min) * 60000) + (float(took_sec) * 1000)
    # Check if the time is in seconds and convert
    elif "s" in took_time:
        return float(took_time.removesuffix("s")) * 1000
    return 0.0


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
    # Sort directories alphabetically by pod name
    sorted_directories = sorted(directories, key=lambda d: get_etcd_pod(Path(d)))
    for directory in sorted_directories:
        directory_path = Path(directory)
        json_dates: dict = Counter()
        # Track max time per minute when date search is enabled
        max_times: dict = {}
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
                                if err_date_search:
                                    if error_txt in line:
                                        if err_date in line:
                                            for result in extract_json_objects(line):
                                                _, ts_time = result.get(
                                                    "ts", "Unknown"
                                                ).split("T")
                                                hr, minute, _ = ts_time.split(":")
                                                time_key = ":".join([hr, minute])
                                                json_dates[time_key] += 1
                                                # Track max time for this minute
                                                if "took" in result:
                                                    took_time = result["took"]
                                                    took_ms = _convert_took_to_ms(took_time)
                                                    if time_key not in max_times or took_ms > max_times[time_key]:
                                                        max_times[time_key] = took_ms
                                elif error_txt in line:
                                    for result in extract_json_objects(line):
                                        ts_date, _ = result.get("ts", "Unknown").split(
                                            "T"
                                        )
                                        json_dates[ts_date] += 1
                for date, count in json_dates.items():
                    if err_date_search and date in max_times:
                        errors.append({"POD": etcd_pod_name, "DATE": date, "COUNT": count, "MAX_TIME": f"{max_times[date]:.4f}ms"})
                    else:
                        errors.append({"POD": etcd_pod_name, "DATE": date, "COUNT": count})
                json_dates.clear()
                max_times.clear()

        log_file_path = (
            directory_path / "etcd" / "etcd" / "logs" / f"{pod_log_version}.log"
        )
        with log_file_path.open(encoding="utf-8", mode="r") as file:
            for line in file:
                if err_date_search:
                    if error_txt in line:
                        if err_date in line:
                            for result in extract_json_objects(line):
                                _, ts_time = result.get("ts", "Unknown").split("T")
                                hr, minute, _ = ts_time.split(":")
                                time_key = ":".join([hr, minute])
                                json_dates[time_key] += 1
                                # Track max time for this minute
                                if "took" in result:
                                    took_time = result["took"]
                                    took_ms = _convert_took_to_ms(took_time)
                                    if time_key not in max_times or took_ms > max_times[time_key]:
                                        max_times[time_key] = took_ms
                elif error_txt in line:
                    for result in extract_json_objects(line):
                        ts_date, _ = result.get("ts", "Unknown").split("T")
                        json_dates[ts_date] += 1
            for date, count in json_dates.items():
                if err_date_search and date in max_times:
                    errors.append({"POD": etcd_pod_name, "DATE": date, "COUNT": count, "MAX_TIME": f"{max_times[date]:.4f}ms"})
                else:
                    errors.append({"POD": etcd_pod_name, "DATE": date, "COUNT": count})
            json_dates.clear()
            max_times.clear()
    if len(errors) != 0:
        # Sort by POD name alphabetically
        errors.sort(key=lambda x: x["POD"])
        if compare_times is True:
            compare(errors)
        else:
            print_rows(errors)
    else:
        print(f'No errors for "{error_txt}".')


def print_rows(errors_list: list[dict[str, Any]]) -> None:
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


def compare(errors_list: list[dict[str, Any]]) -> None:
    """Compares error counts for the same DATE across different PODs"""
    # Create a dictionary to group counts by DATE
    date_groups = {}

    # Group counts by date
    for entry in errors_list:
        date = entry["DATE"]
        if date not in date_groups:
            date_groups[date] = []
        date_groups[date].append(entry)

    # Check if MAX_TIME column exists
    has_max_time = len(errors_list) > 0 and "MAX_TIME" in errors_list[0]

    # Print results for each date with more than one pod
    for date, entries in date_groups.items():
        if len(entries) > 1:  # Only compare if there are multiple pods
            print(f"Date: {date}")
            if has_max_time:
                print(f"{'POD':<30} {'COUNT':<10} {'MAX_TIME':<15}")
            else:
                print(f"{'POD':<30} {'COUNT':<10}")
            # Sort entries by POD name alphabetically
            sorted_entries = sorted(entries, key=lambda x: x["POD"])
            for entry in sorted_entries:
                if has_max_time:
                    print(f"{entry['POD']:<30} {entry['COUNT']:<10} {entry.get('MAX_TIME', 'N/A'):<15}")
                else:
                    print(f"{entry['POD']:<30} {entry['COUNT']:<10}")
            print()


def get_dirs(mg_path: str, pod_glob: str) -> list[str]:
    """Returns the directory for etcd pods"""
    input_dir = Path(mg_path)
    pod_list = list(input_dir.rglob(pod_glob))
    pattern = r"^etcd-(?!guard(-.*)?$)(?!quorum-guard(-.*)?$)"
    return [pod for pod in pod_list if re.search(pattern, pod.name)]


def get_rotated_logs(dir_path: str) -> list[str]:
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


def extract_datetime(file_path: str) -> datetime:
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
    # Sort directories alphabetically by pod name
    sorted_directories = sorted(directories, key=lambda d: get_etcd_pod(Path(d)))

    for directory in sorted_directories:
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
                # Get timestamp from JSON
                timestamp = result.get("ts", "Unknown")
                # Extract just the datetime portion (remove fractional seconds and Z)
                if "T" in timestamp:
                    timestamp = timestamp.split(".")[0] if "." in timestamp else timestamp.rstrip("Z")
                # Collect the expected time
                expected_time = result["expected-duration"]
                # Check if the time is in ms and convert
                if "ms" in took_time:
                    etcd_error_stats.append((float(took_time.removesuffix("ms")), timestamp))
                # Check if the time is in minutes and convert
                elif "m" in took_time:
                    took_min, took_sec = took_time.split("m")
                    took_sec = took_sec.removesuffix("s")
                    etcd_error_stats.append(
                        (((float(took_min) * 60000) + (float(took_sec) * 1000)), timestamp)
                    )
                # Check if the time is in seconds and convert
                elif "s" in took_time:
                    etcd_error_stats.append((float(took_time.removesuffix("s")) * 1000, timestamp))

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

    # Find maximum with timestamp
    max_entry = max(etcd_error_stats, key=lambda x: float(x[0]))
    max_value = max_entry[0]
    max_timestamp = max_entry[1]
    print(f"\tMaximum: {max_value:.4f}ms {max_timestamp}")

    # Extract just the values for other calculations
    values_only = [x[0] for x in etcd_error_stats]
    print(f"\tMinimum: {min(values_only):.4f}ms")
    print(f"\tMedian: {median(values_only):.4f}ms")
    print(f"\tAverage: {sum(values_only) / (len(values_only) + 1):.4f}ms")
    print(f"\tCount: {error_count}")
    print(f"\tExpected: {expected_time}", end="\n\n")


def validate_date(date_string: str) -> datetime:
    """Validate the date string is in YYYY-MM-DD format."""
    try:
        # Attempt to parse the date string
        datetime.strptime(date_string, "%Y-%m-%d")
        return date_string
    except ValueError as e:
        raise argparse.ArgumentTypeError(
            f"Date must be in YYYY-MM-DD format: '{date_string}'"
        ) from e


def signal_handler(_sig, _frame):
    """Handle Ctrl+C gracefully"""
    print("\n\nExiting etcd-ocp-diag...")
    sys.exit(0)


def show_help():
    """Display interactive help"""
    help_text = """
Available commands (no -- required in interactive mode):
  path <path>               Path to the must-gather (if not set, uses current directory)
  ttl                       Check apply request took too long
  heartbeat                 Check failed to send out heartbeat
  election                  Checks for leader elections messages
  lost_leader               Checks for lost leader errors
  fdatasync                 Check slow fdatasync
  buffer                    Check sending buffer is full
  overloaded                Check leader is overloaded likely from slow disk
  etcd_timeout              Check etcdserver: request timed out
  pod <pod_name>            Specify the pod to analyze
  date <YYYY-MM-DD>         Specify date for error search
  compare                   Display only dates or times that happen in all pods
  errors                    Display etcd errors
  stats                     Display etcd stats
  previous                  Use previous logs
  rotated                   Use rotated logs
  back, navigate, dirs      Return to folder navigation mode
  help                      Show this help message
  exit, quit                Exit the program

Examples:
  errors                    (analyze errors in current directory)
  ttl pod etcd-master-1     (check ttl for specific pod)
  overloaded                (check for overloaded leader messages)
  stats                     (show performance statistics)
  errors previous           (check errors in previous logs)
"""
    print(help_text)


def parse_interactive_input(user_input: str) -> Optional[argparse.Namespace]:
    """Parse user input and return argparse Namespace object"""
    # Split the input into arguments, respecting quoted strings
    try:
        args_list = shlex.split(user_input.strip())
    except ValueError as e:
        print(f"Error parsing input: {e}")
        return None

    # Convert simple commands to --commands format for compatibility
    converted_args = []
    i = 0
    while i < len(args_list):
        arg = args_list[i]

        # Handle commands that need values
        if arg in ["path", "pod", "date"]:
            converted_args.append(f"--{arg}")
            if i + 1 < len(args_list):
                converted_args.append(args_list[i + 1])
                i += 1
        # Handle boolean flags
        elif arg in [
            "ttl",
            "heartbeat",
            "election",
            "lost_leader",
            "fdatasync",
            "buffer",
            "overloaded",
            "etcd_timeout",
            "compare",
            "errors",
            "stats",
            "previous",
            "rotated",
        ]:
            converted_args.append(f"--{arg}")
        # Handle arguments that already have -- prefix
        elif arg.startswith("--"):
            converted_args.append(arg)
        # Handle unrecognized arguments (pass through)
        else:
            converted_args.append(arg)

        i += 1

    # Create a new parser for interactive mode
    parser = argparse.ArgumentParser(
        description="Process etcd logs and gather statistics.",
        add_help=False,  # Disable built-in help to handle it ourselves
    )

    # Adding arguments
    parser.add_argument(
        "--path",
        type=str,
        help="Path to the must-gather (optional in interactive mode)",
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
        "--overloaded", action="store_true", help="Check leader is overloaded likely from slow disk"
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

    try:
        args = parser.parse_args(converted_args)
        return args
    except SystemExit:
        # argparse calls sys.exit on error, catch it to continue interactive mode
        return None


def execute_command(args: argparse.Namespace) -> None:
    """Execute the etcd diagnostic command based on parsed arguments"""
    if not args:
        return

    # Set Vars - similar to original main() function
    compare_times: bool = False
    error_txt = None
    err_date: str = ""
    err_date_search: bool = False
    etcd_pod: str = ""
    pod_glob: str = "**/openshift-etcd/pods/etcd-*"
    pod_known: bool = False
    pod_log_version: str = "current"
    rotated_logs: bool = False

    # Validate required arguments
    validation_errors = _validate_command_args(args)
    if validation_errors:
        print(validation_errors)
        return

    # Process arguments
    if args.previous:
        pod_log_version = "previous"
    if args.rotated:
        rotated_logs = True
    if args.compare:
        compare_times = True

    mg_path = args.path if args.path else ""

    # Set the error text based on the selected options
    error_options = {
        "ttl": "apply request took too long",
        "heartbeat": "failed to send out heartbeat",
        "election": "elected leader",
        "lost_leader": "lost leader",
        "fdatasync": "slow fdatasync",
        "buffer": "sending buffer is full",
        "overloaded": "leader is overloaded likely from slow disk",
        "etcd_timeout": "etcdserver: request timed out",
    }

    for option, error_query in error_options.items():
        if getattr(args, option, False):
            error_txt = error_query

    if args.pod:
        pod_glob = f"**/namespaces/openshift-etcd/pods/{args.pod}"
        pod_known = True
        etcd_pod = args.pod

    if args.date:
        err_date = args.date
        err_date_search = True

    try:
        _execute_operation(
            args,
            mg_path,
            pod_glob,
            pod_log_version,
            rotated_logs,
            error_txt,
            err_date,
            pod_known,
            err_date_search,
            etcd_pod,
            compare_times,
        )
    except Exception as e:
        print(f"Error executing command: {e}")


def _validate_command_args(args: argparse.Namespace) -> Optional[str]:
    """Validate command arguments and return error message if invalid"""
    if not args.path and not (args.errors or args.stats):
        return "ERROR: --path is required for most operations."

    if args.previous and args.rotated:
        return "ERROR: Please select either previous or rotated option."

    return ""


def _execute_operation(
    args,
    mg_path,
    pod_glob,
    pod_log_version,
    rotated_logs,
    error_txt,
    err_date,
    pod_known,
    err_date_search,
    etcd_pod,
    compare_times,
):
    """Execute the specific operation based on arguments"""
    if args.stats:
        if not mg_path:
            print("ERROR: --path is required for --stats")
            return
        for value in ["apply request took too long", "slow fdatasync"]:
            etcd_stats(
                get_dirs(mg_path, pod_glob), value, pod_log_version, rotated_logs
            )
    elif args.errors:
        if not mg_path:
            print("ERROR: --path is required for --errors")
            return
        etcd_errors(
            get_dirs(mg_path, pod_glob),
            pod_known,
            etcd_pod,
            pod_log_version,
            rotated_logs,
        )
    elif error_txt and mg_path:
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
    elif not error_txt and not args.errors and not args.stats:
        print(
            "ERROR: Please specify an operation (--ttl, --heartbeat, --election, etc.)"
        )


def clear_screen():
    """Clear the terminal screen"""
    try:
        # Try Unix/Linux/macOS clear command first
        result = subprocess.run(["clear"], check=False)
        if result.returncode != 0:
            # Try Windows cls command
            subprocess.run(["cls"], shell=True, check=False)
    except (subprocess.SubprocessError, FileNotFoundError):
        # Fallback: just print newlines if clear command fails
        print("\n" * 50)


def list_directories(path: str) -> list[str]:
    """List directories in the given path"""
    try:
        path_obj = Path(path)
        items = []
        for item in sorted(path_obj.iterdir()):
            if item.is_dir() and not item.name.startswith("."):
                items.append(item.name)
        return items
    except (OSError, PermissionError):
        return []


def show_folder_navigation_help():
    """Show help for folder navigation mode"""
    help_text = """
Folder Navigation Mode:
  [number]           Navigate to the folder with that number
                     (Last number goes to Previous Directory if available)
  ls                 List current directory contents again
  pwd                Show current directory path
  ..                 Go up one directory level
  run commands       Switch to command mode for etcd analysis
  help               Show this help message
  exit, quit         Exit the program
"""
    print(help_text)


def folder_navigation_mode(current_path: Optional[str] = None, initial_previous_path: Optional[str] = None) -> Optional[str]:
    """Handle folder navigation and return the selected path for analysis"""
    if current_path is None:
        current_path = str(Path.cwd())

    # Track directory history
    previous_path = initial_previous_path

    def show_navigation_screen():
        """Display the navigation screen with current directory and options"""
        clear_screen()
        print("=== etcd-ocp-diag Folder Navigation ===")
        print(
            "Navigate to your must-gather directory, then type 'run commands' to start analysis"
        )
        print()

        # Show current directory
        print(f"Current directory: {current_path}")

        # List directories
        directories = list_directories(current_path)
        display_options = []

        if directories:
            print("\nAvailable directories:")
            for i, dir_name in enumerate(directories, 1):
                print(f"  {i:2d}. {dir_name}")
                display_options.append(("directory", dir_name))
        else:
            print("\nNo subdirectories found in current location.")

        # Add Previous Directory option if we have a previous path
        if previous_path and previous_path != current_path:
            option_num = len(directories) + 1
            prev_dir_name = Path(previous_path).name or previous_path
            print(f"  {option_num:2d}. Previous Directory ({prev_dir_name})")
            display_options.append(("previous", previous_path))

        print("\nOptions: [number], 'ls', 'pwd', '..', 'run commands', 'help', 'exit'")
        return display_options

    # Initial screen display
    display_options = show_navigation_screen()

    while True:
        try:
            user_input = input("navigate> ").strip()

            if not user_input:
                show_folder_navigation_help()
                continue

            if user_input.lower() in ["exit", "quit"]:
                print("Exiting etcd-ocp-diag...")
                return None

            if user_input.lower() == "help":
                show_folder_navigation_help()
                continue

            if user_input.lower() == "ls":
                display_options = show_navigation_screen()
                continue

            if user_input.lower() == "pwd":
                print(f"Current path: {current_path}")
                continue

            if user_input == "..":
                current_path_obj = Path(current_path)
                parent_path = str(current_path_obj.parent)
                if parent_path != current_path:  # Not at root
                    previous_path = current_path  # Save current as previous
                    current_path = parent_path
                    display_options = show_navigation_screen()
                continue

            if user_input.lower() in ["run commands", "commands"]:
                return current_path

            # Check if input is a number for directory/option selection
            try:
                choice = int(user_input)
                if 1 <= choice <= len(display_options):
                    option_type, option_value = display_options[choice - 1]

                    if option_type == "directory":
                        # Navigate to selected directory
                        selected_dir = option_value
                        new_path = Path(current_path) / selected_dir
                        if new_path.is_dir():
                            previous_path = current_path  # Save current as previous
                            current_path = str(new_path)
                            display_options = show_navigation_screen()
                        else:
                            print(f"Error: {selected_dir} is not accessible")

                    elif option_type == "previous":
                        # Navigate to previous directory
                        temp_path = current_path
                        current_path = option_value
                        previous_path = temp_path  # Swap paths
                        display_options = show_navigation_screen()

                else:
                    print(
                        f"Error: Please enter a number between 1 and {len(display_options)}"
                    )
            except ValueError:
                print("Error: Invalid input. Type 'help' for available options.")

        except KeyboardInterrupt:
            print("\n\nExiting etcd-ocp-diag...")
            return None
        except EOFError:
            print("\nExiting etcd-ocp-diag...")
            return None


def command_mode(base_path: str):
    """Run the command mode for etcd analysis"""
    clear_screen()
    print("=== etcd-ocp-diag Command Mode ===")
    print(f"Working directory: {base_path}")
    print()
    print(
        "💡 Navigation: Type 'back', 'navigate', or 'dirs' to return to folder navigation"
    )
    print("💡 Help: Type 'help' for commands, 'exit' to quit")
    print("💡 Commands: No '--' prefixes needed (e.g., 'errors', 'ttl pod my-pod')")
    print()

    while True:
        try:
            user_input = input("etcd-diag> ").strip()

            if not user_input:
                show_help()
                continue

            if user_input.lower() in ["exit", "quit"]:
                print("Exiting etcd-ocp-diag...")
                break

            if user_input.lower() in ["back", "navigate", "directories", "dirs", "nav"]:
                # Navigate to parent directory with current directory as previous
                base_path_obj = Path(base_path)
                parent_path = str(base_path_obj.parent)

                # If we're at root or parent is same, stay at current directory
                if parent_path == base_path:
                    return folder_navigation_mode(base_path)
                else:
                    # Navigate to parent with current as previous directory
                    return folder_navigation_mode(parent_path, base_path)

            if user_input.lower() == "help":
                show_help()
                continue

            # Parse and execute the command
            args = parse_interactive_input(user_input)
            if args:
                # If no path specified, use the current working directory
                if not args.path:
                    args.path = base_path
                clear_screen()
                print("=== etcd-ocp-diag Command Mode ===")
                print(f"Working directory: {base_path}")
                print(f"Running: {user_input}")
                print("=" * 50)
                execute_command(args)
                print("=" * 50)
                print(
                    "Command completed. Enter another command, 'help' for options, or 'back' to navigate directories."
                )
                print()

        except KeyboardInterrupt:
            print("\n\nExiting etcd-ocp-diag...")
            break
        except EOFError:
            print("\nExiting etcd-ocp-diag...")
            break


def interactive_mode():
    """Run the script in interactive mode with folder navigation"""
    while True:
        try:
            # Start with folder navigation
            selected_path = folder_navigation_mode()

            # If folder_navigation_mode returns None, user chose to exit
            if selected_path is None:
                break

            # Switch to command mode
            command_mode(selected_path)
            # When command_mode returns, we'll go back to folder navigation
        except KeyboardInterrupt:
            print("\nExiting etcd-ocp-diag...")
            break


def main():
    """Primary function"""
    # Set up signal handler for Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)

    # Check if any command line arguments were provided
    if len(sys.argv) == 1:
        # No arguments provided, run in interactive mode
        interactive_mode()
        return

    # Check for interactive flag
    INTERACTIVE_ARG_COUNT = 2
    if len(sys.argv) == INTERACTIVE_ARG_COUNT and sys.argv[1] in [
        "-i",
        "--interactive",
    ]:
        interactive_mode()
        return

    # Command line mode - original functionality
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
        "--overloaded", action="store_true", help="Check leader is overloaded likely from slow disk"
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
    parser.add_argument(
        "-i", "--interactive", action="store_true", help="Run in interactive mode"
    )

    args = parser.parse_args()

    if args.interactive:
        interactive_mode()
        return

    # Execute the command using the refactored function
    execute_command(args)


if __name__ == "__main__":
    main()
