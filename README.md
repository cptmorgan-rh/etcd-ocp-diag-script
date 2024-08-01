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
```