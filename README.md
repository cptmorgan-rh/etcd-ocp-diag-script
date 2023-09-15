etcd Diagnostics
===========================================

DESCRIPTION
------------

The purpose of this script is to quickly search logs for known etcd issues in an OpenShift Must-Gather.

PREREQUISITES
------------

LINUX:
This script requires jq. The jq package is avaiable in all common Linux Distributions.

INSTALLATION
------------
* Copy etcd-ocp-diag.sh to a location inside of your $PATH

USAGE
------------

```bash
Options:
  --errors       Displays known errors in the etcd logs along with their count
  --stats        Displays Stats and Calculates Avg, Max, Min, and Median times for etcd errors
  --ttl          Displays 'took too long' errors
  --heartbeart   Displays 'leader failed to send out heartbeat on time' errors
  --election     Displays 'elected leader' and 'lost leader' errors
  --fdatasync    Displays 'slow fdatasync' errors
  --buffer       Displays 'sending buffer is full' errors
  --previous     Displays output using the 'previous' log if it exists
  --pod          Specify the name of the pod to search
                 Example: etcd-ocp-diag.sh --ttl --pod etcd-ocp-master2
  --date         Specify the date in YYYY-MM-DD format
                 Example: etcd-ocp-diag.sh --ttl --pod etcd-ocp-master2 --date 2023-08-30
                 Example: etcd-ocp-diag.sh --election --date 2023-08-30
  --time         Opens Pod Logs in less with specified time; Specify the time HH:MM format
                 etcd-ocp-diag.sh --ttl --pod etcd-ocp-master2 --date 2023-08-30 --time 02:00
  --help         Shows this help message
```

SAMPLE OUTPUT
------------

```bash
$ etcd-ocp-diag.sh --errors
NAMESPACE       POD                      ERROR                                                                                                     COUNT
openshift-etcd  etcd-ocp-master0  waiting for ReadIndex response took too long, retrying                                                    33
openshift-etcd  etcd-ocp-master0  "apply request took too long"                                                                             696
openshift-etcd  etcd-ocp-master0  "leader failed to send out heartbeat on time; took too long, leader is overloaded likely from slow disk"  28
openshift-etcd  etcd-ocp-master0  elected leader                                                                                            1
openshift-etcd  etcd-ocp-master0  lost leader                                                                                               1
openshift-etcd  etcd-ocp-master0  lease not found                                                                                           4
openshift-etcd  etcd-ocp-master1  waiting for ReadIndex response took too long, retrying                                                    3
openshift-etcd  etcd-ocp-master1  "apply request took too long"                                                                             58
openshift-etcd  etcd-ocp-master2  waiting for ReadIndex response took too long, retrying                                                    313
openshift-etcd  etcd-ocp-master2  etcdserver: request timed out                                                                             4
openshift-etcd  etcd-ocp-master2  slow fdatasync                                                                                            12
openshift-etcd  etcd-ocp-master2  "apply request took too long"                                                                             9582
openshift-etcd  etcd-ocp-master2  elected leader                                                                                            6
openshift-etcd  etcd-ocp-master2  lost leader                                                                                               5
openshift-etcd  etcd-ocp-master2  lease not found                                                                                           4
openshift-etcd  etcd-ocp-master2  sending buffer is full                                                                                    100
```

```bash
$ etcd-ocp-diag.sh --stats
Stats about etcd 'took long' messages: etcd-ocp-master0
	First Occurance: 2023-09-06T15:01:14.434319112Z
	Last Occurance: 2023-09-12T22:10:59.843223535Z
	Maximum: 3522.91903ms
	Minimum: 201.846969ms
	Median: 980ms
	Average: 1175ms
	Count: 696
	Expected: 200ms

Stats about etcd 'took long' messages: etcd-ocp-master1
	First Occurance: 2023-09-12T20:25:33.972726480Z
	Last Occurance: 2023-09-12T22:10:59.837938805Z
	Maximum: 1141.97292ms
	Minimum: 203.934898ms
	Median: 532.362165ms
	Average: 583ms
	Count: 313
	Expected: 200ms

Stats about etcd 'took long' messages: etcd-ocp-master2
	First Occurance: 2023-08-01T13:36:34.433175702Z
	Last Occurance: 2023-09-13T14:22:00.580271701Z
	Maximum: 11511.24381ms
	Minimum: 200.016363ms
	Median: 482.516943ms
	Average: 853ms
	Count: 9582
	Expected: 200ms

Stats about etcd 'slow fdatasync' messages: etcd-ocp-master2
	First Occurance: 2023-08-01T13:36:25.005072189Z
	Last Occurance: 2023-08-17T02:02:04.049603261Z
	Maximum: 11679.21919ms
	Minimum: 1002.78933ms
	Median: 1519ms
	Average: 4480ms
	Count: 12
	Expected: 1s

etcd DB Compaction times: etcd-ocp-np-sth-master0
	Maximum: 2918.12808ms
	Minimum: 1820.23331ms
	Median: 2041ms
	Average: 2060
	Count: 492ms

etcd DB Compaction times: etcd-ocp-np-sth-master1
	Maximum: 2409.09816ms
	Minimum: 1670.84453ms
	Median: 1861ms
	Average: 1876
	Count: 494ms

etcd DB Compaction times: etcd-ocp-np-sth-master2
	Maximum: 2664.11661ms
	Minimum: 1717.23653ms
	Median: 1982ms
	Average: 2000
	Count: 496ms
```

```bash
$ etcd-ocp-diag.sh --ttl
POD                      DAY         COUNT
etcd-ocp-master0  2023-09-06  383
etcd-ocp-master0  2023-09-07  210
etcd-ocp-master0  2023-09-08  30
etcd-ocp-master0  2023-09-09  16
etcd-ocp-master0  2023-09-10  17
etcd-ocp-master0  2023-09-11  23
etcd-ocp-master0  2023-09-12  17
etcd-ocp-master1  2023-09-12  58
etcd-ocp-master2  2023-08-01  815
etcd-ocp-master2  2023-08-02  42
etcd-ocp-master2  2023-08-03  51
etcd-ocp-master2  2023-08-04  47
etcd-ocp-master2  2023-08-05  34
etcd-ocp-master2  2023-08-06  67
etcd-ocp-master2  2023-08-07  40
etcd-ocp-master2  2023-08-08  49
etcd-ocp-master2  2023-08-09  61
etcd-ocp-master2  2023-08-10  95
etcd-ocp-master2  2023-08-11  115
etcd-ocp-master2  2023-08-12  49
etcd-ocp-master2  2023-08-13  53
etcd-ocp-master2  2023-08-14  45
etcd-ocp-master2  2023-08-15  118
etcd-ocp-master2  2023-08-16  1361
etcd-ocp-master2  2023-08-17  954
etcd-ocp-master2  2023-08-18  574
etcd-ocp-master2  2023-08-19  118
etcd-ocp-master2  2023-08-20  156
etcd-ocp-master2  2023-08-21  298
etcd-ocp-master2  2023-08-22  283
etcd-ocp-master2  2023-08-23  233
etcd-ocp-master2  2023-08-24  228
etcd-ocp-master2  2023-08-25  232
etcd-ocp-master2  2023-08-26  252
etcd-ocp-master2  2023-08-27  225
etcd-ocp-master2  2023-08-28  254
etcd-ocp-master2  2023-08-29  335
etcd-ocp-master2  2023-08-30  145
etcd-ocp-master2  2023-08-31  234
etcd-ocp-master2  2023-09-01  197
etcd-ocp-master2  2023-09-02  135
etcd-ocp-master2  2023-09-03  93
etcd-ocp-master2  2023-09-04  249
etcd-ocp-master2  2023-09-05  123
etcd-ocp-master2  2023-09-06  716
etcd-ocp-master2  2023-09-07  172
etcd-ocp-master2  2023-09-08  60
etcd-ocp-master2  2023-09-09  56
etcd-ocp-master2  2023-09-10  65
etcd-ocp-master2  2023-09-11  105
etcd-ocp-master2  2023-09-12  45
etcd-ocp-master2  2023-09-13  3
```

```bash
$ etcd-ocp-diag.sh --ttl --pod etcd-ocp-master2
POD                      DAY         COUNT
etcd-ocp-master2  2023-08-01  815
etcd-ocp-master2  2023-08-02  42
etcd-ocp-master2  2023-08-03  51
etcd-ocp-master2  2023-08-04  47
etcd-ocp-master2  2023-08-05  34
etcd-ocp-master2  2023-08-06  67
etcd-ocp-master2  2023-08-07  40
etcd-ocp-master2  2023-08-08  49
etcd-ocp-master2  2023-08-09  61
etcd-ocp-master2  2023-08-10  95
etcd-ocp-master2  2023-08-11  115
etcd-ocp-master2  2023-08-12  49
etcd-ocp-master2  2023-08-13  53
etcd-ocp-master2  2023-08-14  45
etcd-ocp-master2  2023-08-15  118
etcd-ocp-master2  2023-08-16  1361
etcd-ocp-master2  2023-08-17  954
etcd-ocp-master2  2023-08-18  574
etcd-ocp-master2  2023-08-19  118
etcd-ocp-master2  2023-08-20  156
etcd-ocp-master2  2023-08-21  298
etcd-ocp-master2  2023-08-22  283
etcd-ocp-master2  2023-08-23  233
etcd-ocp-master2  2023-08-24  228
etcd-ocp-master2  2023-08-25  232
etcd-ocp-master2  2023-08-26  252
etcd-ocp-master2  2023-08-27  225
etcd-ocp-master2  2023-08-28  254
etcd-ocp-master2  2023-08-29  335
etcd-ocp-master2  2023-08-30  145
etcd-ocp-master2  2023-08-31  234
etcd-ocp-master2  2023-09-01  197
etcd-ocp-master2  2023-09-02  135
etcd-ocp-master2  2023-09-03  93
etcd-ocp-master2  2023-09-04  249
etcd-ocp-master2  2023-09-05  123
etcd-ocp-master2  2023-09-06  716
etcd-ocp-master2  2023-09-07  172
etcd-ocp-master2  2023-09-08  60
etcd-ocp-master2  2023-09-09  56
etcd-ocp-master2  2023-09-10  65
etcd-ocp-master2  2023-09-11  105
etcd-ocp-master2  2023-09-12  45
etcd-ocp-master2  2023-09-13  3
```
```bash
$ etcd-ocp-diag.sh --ttl --pod etcd-ocp-master2 --date 2023-08-16
TIME   COUNT
00:00  236
02:00  1111
02:01  490
02:02  686
02:03  78
02:13  80
08:12  2
15:21  102
22:06  190
22:27  344
```

AUTHOR
------
Morgan Peterman