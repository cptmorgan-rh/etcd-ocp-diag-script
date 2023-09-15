#!/bin/bash

run() {

  options=$(getopt -n "etcd-ocp-diag.sh" -o cfhl --long errors,kubeapi,stats,ttl,heartbeat,election,fdatasync,buffer,help,previous,pod:,date:,time: -- "$@")

  if [[ $? != 0 ]]; then
    printf "\n"
    show_help
    exit 1
  fi

  eval set -- "$options"

  while true; do
    case "$1" in
       --previous)
        previous=true; shift;;
      --errors)
        errors=true; shift;;
      --stats)
        stats=true; shift;;
      --pod)
        pod=$2; shift 2;;
      --date)
        date=$2; shift 2;;
      --time)
        time=$2; shift 2;;
      --ttl)
        search_etcd_cmd="ttl"; shift;;
      --heartbeat)
        search_etcd_cmd="heartbeat"; shift;;
      --election)
        search_etcd_cmd="election"; shift;;
      --fdatasync)
        search_etcd_cmd="fdatasync"; shift;;
      --buffer)
        search_etcd_cmd="buffer"; shift;;
      -h | --help)
        shift; echo; show_help; exit 0;;
      --)
        shift;;
      *)
        if [[ -z "$1" ]]; then break; else echo; show_help; exit 1; fi;;
    esac
  done

  if [[ "$previous" = true ]]; then
    logs="previous"
  else
    logs="current"
  fi

  if [[ "$errors" = true ]]; then
   errors
  fi

  if [[ "$stats" = true ]]; then
   stats
  fi

  case "$search_etcd_cmd" in
    ttl)
      search_etcd 'apply request took too long.*expec';;
    heartbeat)
      search_etcd 'failed to send out heartbeat';;
    election)
      search_etcd 'lost leader|elected leader';;
    fdatasync)
      search_etcd 'slow fdatasync';;
    buffer)
      search_etcd 'sending buffer is full';;
  esac


}

show_help(){

cat  << ENDHELP
USAGE: $(basename "$0")
etcd-ocp-diag is a simple script which provides reporting on etcd errors
in a must-gather/inspect to pinpoint when slowness is occuring.

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
                 Example: etcd-ocp-diag.sh --ttl --pod etcd-ocp-np-sth-master2
  --date         Specify the date in YYYY-MM-DD format
                 Example: etcd-ocp-diag.sh --ttl --pod etcd-ocp-np-sth-master2 --date 2023-08-30
                 Example: etcd-ocp-diag.sh --election --date 2023-08-30
  --time         Opens Pod Logs in less with specified time; Specify the time HH:MM format
                 etcd-ocp-diag.sh --ttl --pod etcd-ocp-np-sth-master2 --date 2023-08-30 --time 02:00
  --help         Shows this help message

ENDHELP

}

dep_check(){

if [ ! $(command -v jq) ]; then
  echo "jq not found. Please install jq."
  exit 1
fi

}

errors(){

#Check to make sure the openshift-etcd namespace exits
if [ ! -d "namespaces/openshift-etcd/pods/" ]; then
  echo -e "openshift-etcd not found.\n"
  return 1
fi

# set column names
etcd_output_arr=("NAMESPACE|POD|ERROR|COUNT")

# etcd pod errors
etcd_etcd_errors_arr=("waiting for ReadIndex response took too long, retrying" "etcdserver: request timed out" "slow fdatasync" "\"apply request took too long\"" "\"leader failed to send out heartbeat on time; took too long, leader is overloaded likely from slow disk\"" "local no
de might have slow network" "elected leader" "lost leader" "wal: sync duration" "the clock difference against peer" "lease not found" "rafthttp: failed to read" "server is likely overloaded" "lost the tcp streaming" "sending buffer is full" "health errors")

for i in namespaces/openshift-etcd/pods/etcd*/etcd/etcd/logs/"$logs"*log; do
  for val in "${etcd_etcd_errors_arr[@]}"; do
    if [[ "$(grep -wc "$val" "$i")" != "0" ]]; then
     etcd_output_arr+=("$(echo "$i" | awk -F/ '{ print $2 }')|$(echo "$i" | awk -F/ '{ print $4 }')|$(echo "$val")|$(grep -wc "$val" "$i")")
    fi
  done
done

if [ "${#etcd_output_arr[1]}" != 0 ]; then
  printf '%s\n' "${etcd_output_arr[@]}" | column -t -s '|'
  printf "\n"
fi

unset etcd_output_arr

}


stats(){

for i in namespaces/openshift-etcd/pods/etcd*/etcd/etcd/logs/"$logs".log; do
    expected=$(grep -m1 'took too long.*expec' "$i" | grep -o "\{.*\}" | jq -r '."expected-duration"' 2>/dev/null)
    if grep 'took too long.*expec' "$i" > /dev/null 2>&1;
    then

      first=$(grep -m1 'took too long.*expec' "$i" 2>/dev/null | awk '{ print $1}')
      last=$(grep 'took too long.*expec' "$i" 2>/dev/null | tail -n1 | awk '{ print $1}')

      for x in $(grep 'took too long.*expec' "$i" | grep -Ev 'leader|waiting for ReadIndex response took too long' | grep -o "\{.*\}"  | jq -r '.took' 2>/dev/null | grep -Ev 'T|Z' 2>/dev/null); do
        if [[ $x =~ [1-9]m[0-9] ]];
        then
          compact_min=$(echo "scale=5;($(echo $x | grep -Eo '[1-9]m' | sed 's/m//')*60000)/1" | bc)
          compact_sec=$(echo "scale=5;($(echo $x | sed -E 's/[1-9]+m//' | grep -Eo '[1-9]?\.[0-9]+')*1000)/1" | bc)
          compact_time=$(echo "scale=5;$compact_min + $compact_sec" | bc)
        elif [[ $x =~ [1-9]s ]];
        then
          compact_time=$(echo "scale=5;($(echo $x | sed 's/s//')*1000)/1" | bc)
        else
          compact_time=$(echo $x | sed 's/ms//')
        fi
        median_arr+=(${compact_time})
      done
      printf "Stats about etcd 'took long' messages: $(echo "$i" | awk -F/ '{ print $4 }')\n"
      printf "\tFirst Occurance: ${first}\n"
      printf "\tLast Occurance: ${last}\n"
      printf "\tMaximum: $(echo ${median_arr[@]} | jq -s '{maximum:max}' | jq -r '.maximum')ms\n"
      printf "\tMinimum: $(echo ${median_arr[@]} | jq -s '{minimum:min}' | jq -r '.minimum')ms\n"
      printf "\tMedian: $(echo ${median_arr[@]} | jq -s '{median:(sort|if length%2==1 then.[length/2|floor]else[.[length/2-1,length/2]]|add/2|round end)}' | jq -r '.median')ms\n"
      printf "\tAverage: $(echo ${median_arr[@]} | jq -s '{average:(add/length|round)}' | jq -r '.average')ms\n"
      printf "\tExpected: ${expected}\n"
      printf "\n"

      unset median_arr
    fi
done

for i in namespaces/openshift-etcd/pods/etcd*/etcd/etcd/logs/"$logs".log; do
    expected=$(grep -m1 'slow fdatasync' "$i" | grep -o "\{.*\}" | jq -r '."expected-duration"' 2>/dev/null)
    if grep 'slow fdatasync' "$i" > /dev/null 2>&1;
    then

      first=$(grep -m1 'slow fdatasync' "$i" 2>/dev/null | awk '{ print $1}')
      last=$(grep 'slow fdatasync' "$i" 2>/dev/null | tail -n1 | awk '{ print $1}')

      for x in $(grep 'slow fdatasync' "$i" | grep -o "\{.*\}"  | jq -r '.took' 2>/dev/null); do
        if [[ $x =~ [1-9]m[0-9] ]];
        then
          compact_min=$(echo "scale=5;($(echo $x | grep -Eo '[1-9]m' | sed 's/m//')*60000)/1" | bc)
          compact_sec=$(echo "scale=5;($(echo $x | sed -E 's/[1-9]+m//' | grep -Eo '[1-9]?\.[0-9]+')*1000)/1" | bc)
          compact_time=$(echo "scale=5;$compact_min + $compact_sec" | bc)
        elif [[ $x =~ [1-9]s ]];
        then
          compact_time=$(echo "scale=5;($(echo $x | sed 's/s//')*1000)/1" | bc)
        else
          compact_time=$(echo $x | sed 's/ms//')
        fi
        median_arr+=(${compact_time})
      done
      printf "Stats about etcd 'slow fdatasync' messages: $(echo "$i" | awk -F/ '{ print $4 }')\n"
      printf "\tFirst Occurance: ${first}\n"
      printf "\tLast Occurance: ${last}\n"
      printf "\tMaximum: $(echo ${median_arr[@]} | jq -s '{maximum:max}' | jq -r '.maximum')ms\n"
      printf "\tMinimum: $(echo ${median_arr[@]} | jq -s '{minimum:min}' | jq -r '.minimum')ms\n"
      printf "\tMedian: $(echo ${median_arr[@]} | jq -s '{median:(sort|if length%2==1 then.[length/2|floor]else[.[length/2-1,length/2]]|add/2|round end)}' | jq -r '.median')ms\n"
      printf "\tAverage: $(echo ${median_arr[@]} | jq -s '{average:(add/length|round)}' | jq -r '.average')ms\n"
      printf "\tExpected: ${expected}\n"
      printf "\n"

      unset median_arr
    fi
done

for i in namespaces/openshift-etcd/pods/etcd*/etcd/etcd/logs/"$logs".log; do
    if grep -m1 "finished scheduled compaction" "$i" | grep '"took"'  > /dev/null 2>&1;
    then
      for x in $(grep "finished scheduled compaction" "$i" | grep -o "\{.*\}" | jq -r '.took'); do
        if [[ $x =~ [1-9]m[0-9] ]];
        then
          compact_min=$(echo "scale=5;($(echo $x | grep -Eo '[1-9]m' | sed 's/m//')*60000)/1" | bc)
          compact_sec=$(echo "scale=5;($(echo $x | sed -E 's/[1-9]+m//' | grep -Eo '[1-9]?\.[0-9]+')*1000)/1" | bc)
          compact_time=$(echo "scale=5;$compact_min + $compact_sec" | bc)
        elif [[ $x =~ [1-9]s ]];
        then
          compact_time=$(echo "scale=5;($(echo $x | sed 's/s//')*1000)/1" | bc)
        else
          compact_time=$(echo $x | sed 's/ms//')
        fi
        median_arr+=(${compact_time})
      done
      printf "etcd DB Compaction times: $(echo "$i" | awk -F/ '{ print $4 }')\n"
      printf "\tMaximum: $(echo ${median_arr[@]} | jq -s '{maximum:max}' | jq -r '.maximum')ms\n"
      printf "\tMinimum: $(echo ${median_arr[@]} | jq -s '{minimum:min}' | jq -r '.minimum')ms\n"
      printf "\tMedian: $(echo ${median_arr[@]} | jq -s '{median:(sort|if length%2==1 then.[length/2|floor]else[.[length/2-1,length/2]]|add/2|round end)}' | jq -r '.median')ms\n"
      printf "\tAverage: $(echo ${median_arr[@]} | jq -s '{average:(add/length|round)}' | jq -r '.average')ms\n"
      printf "\n"

      unset median_arr
    fi
done

}

search_etcd(){

#Prints all pods, days, and error count
#Example: etcd-ocp-diag.sh --ttl
if [[ "$pod" == "" && "$date" == "" ]]; then
  # set column names
  etcd_search_arr=("POD|DAY|COUNT")
  for n in $(realpath namespaces/openshift-etcd/pods/*/etcd/etcd/logs/ | awk -F/ '{ print $(NF-3) }'); do
    for i in $(grep -E "$1" namespaces/openshift-etcd/pods/$n/etcd/etcd/logs/"$logs"*log | grep -o "\{.*\}" | jq -r '.ts' | awk -FT '{ print $1 }' | sort -u); do
      etcd_search_arr+=("$(echo "$n")|$(echo "$i")|$(grep -E "$1" namespaces/openshift-etcd/pods/$n/etcd/etcd/logs/"$logs"*log | grep "$i" | wc -l)")
    done
  done
fi

#Prints Speficied Pod, all days, and error count
#Example: etcd-ocp-diag.sh --ttl --pod etcd-ocp-np-sth-master2
if [[ "$pod" != "" && "$date" == "" ]]; then
  if [ -d namespaces/openshift-etcd/pods/"$pod"/etcd/etcd/logs/ ]; then
    # set column names
    etcd_search_arr=("POD|DAY|COUNT")
    for i in $(grep -E "$1" namespaces/openshift-etcd/pods/"$pod"/etcd/etcd/logs/"$logs"*log | grep -o "\{.*\}" | jq -r '.ts' | awk -FT '{ print $1 }' | sort -u); do
      etcd_search_arr+=("$(echo "$pod")|$(echo "$i")|$(grep -E "$1" namespaces/openshift-etcd/pods/"$pod"/etcd/etcd/logs/"$logs"*log | grep "$i" | wc -l)")
    done
  fi
fi

#Prints all pods, days, and error count
#Example: etcd-ocp-diag.sh --ttl --date 2023-08-29
if [[ "$pod" == "" && "$date" != "" ]]; then
  # set column names
  etcd_search_arr=("POD|DAY|COUNT")
  for n in $(realpath namespaces/openshift-etcd/pods/*/etcd/etcd/logs/ | awk -F/ '{ print $(NF-3) }'); do
      etcd_search_arr+=("$(echo "$n")|$(echo "$date")|$(grep -E "$1" namespaces/openshift-etcd/pods/$n/etcd/etcd/logs/"$logs"*log | grep "$date" | wc -l)")
  done
fi

#Prints specified pod, day, and error count by hour
#Example: etcd-ocp-diag.sh --ttl --pod etcd-ocp-np-sth-master2 --date 2023-08-29
if [[ "$pod" != "" && "$date" != "" && "$time" == "" ]]; then
  # set column names
  etcd_search_arr=("TIME|COUNT")
  for i in $(grep -E "$1" namespaces/openshift-etcd/pods/"$pod"/etcd/etcd/logs/"$logs"*log | grep "$date" | grep -o "\{.*\}" | jq -r '.ts' | awk -FT '{ print $2 }' | sort -u | awk -F: '{ print $1":"$2 }' | sort -u); do
    etcd_search_arr+=("$(echo "$i")|$(grep -E "$1" namespaces/openshift-etcd/pods/"$pod"/etcd/etcd/logs/"$logs"*log | grep "$i" | wc -l)")
  done
fi

#Prints specified pod, day, and error count by hour
#Example: etcd-ocp-diag.sh --ttl --pod etcd-ocp-np-sth-master2 --date 2023-08-29 --time 02:00
if [[ "$pod" != "" && "$date" != "" && "$time" != "" ]]; then
  if [ -f namespaces/openshift-etcd/pods/"$pod"/etcd/etcd/logs/"$logs"*log ]; then
    grep -E "$date" namespaces/openshift-etcd/pods/"$pod"/etcd/etcd/logs/"$logs"*log | grep -C10 "$time" | less
  fi
fi

if [ "${#etcd_search_arr[1]}" != 0 ]; then
  printf '%s\n' "${etcd_search_arr[@]}" | column -t -s '|'
  printf "\n"
fi

unset etcd_search_arr

}

kube-api(){

#Check to make sure the openshift-kube-apiserver namespace exits
if [ ! -d "namespaces/openshift-kube-apiserver/pods/" ]; then
  echo -e "openshift-kube-apiserver not found.\n"
  return 1
fi

# set column names
kubeapi_output_arr=("NAMESPACE|POD|ERROR|COUNT")

# kube-apiserver pod errors
kubeapi_errors_arr=("timeout or abort while handling" "Failed calling webhook" "invalid bearer token, token lookup failed" "etcdserver: mvcc: required revision has been compacted")

for i in namespaces/openshift-kube-apiserver/pods/kube-apiserver-*/kube-apiserver/kube-apiserver/logs/"$logs"*log; do
  for val in "${kubeapi_errors_arr[@]}"; do
    if [[ "$(grep -wc "$val" "$i")" != "0" ]]; then
     kubeapi_output_arr+=("$(echo "$i" | awk -F/ '{ print $2 }')|$(echo "$i" | awk -F/ '{ print $4 }')|$(echo "$val")|$(grep -wc "$val" "$i")")
    fi
  done
done

if [ "${#kubeapi_output_arr[1]}" != 0 ]; then
  printf '%s\n' "${kubeapi_output_arr[@]}" | column -t -s '|'
  printf "\n"
fi

unset kubeapi_output_arr

}


main(){

#Check if in must-gather folder
if [ ! -d namespaces ]
then
    printf "WARNING: Namespaces not found.\n"
    printf "Please run $(basename "$0") from inside a must-gather folder.\n"
    printf "\n"
    show_help
    exit 1
fi

#Verify jq is installed
dep_check

run "$@"

}

main "$@"