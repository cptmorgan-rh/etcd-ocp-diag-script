etcd Diagnostics
===========================================

DESCRIPTION
------------

The purpose of this script is to quickly search logs for known etcd issues in an Openpyift Must-Gather.

INSTALLATION
------------
* Copy etcd-ocp-diag.py to a location inside of your $PATH

USAGE
------------

```bash
usage: etcd-ocp-diag.py [-h] --path PATH [--ttl] [--heartbeat] [--election] [--lost-leader] [--fdatasync] [--buffer] [--etcd_timeout] [--pod POD] [--date DATE] [--compare] [--errors] [--stats] [--previous] [--rotated]

Process etcd logs and gather statistics.

options:
  -h, --help      show this help message and exit
  --path PATH     Path to the must-gather
  --ttl           Check apply request took too long
  --heartbeat     Check failed to send out heartbeat
  --election      Checks for leader elections messages
  --lost_leader   Checks for lost leader errors
  --fdatasync     Check slow fdatasync
  --buffer        Check sending buffer is full
  --etcd_timeout  Check etcdserver: request timed out
  --pod POD       Specify the pod to analyze
  --date DATE     Specify date for error search in YYYY-MM-DD format
  --compare       Display only dates or times that happen in all pods
  --errors        Display etcd errors
  --stats         Display etcd stats
  --previous      Use previous logs
  --rotated       Use rotated logs
```