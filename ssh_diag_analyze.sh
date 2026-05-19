#!/bin/bash
# Analyze the captured SSH-hang diagnostic data on the VPS.
D=/tmp/sshdiag

echo "########## A. per-pid summary of stuck.log (sshd procs aged 6-50s) ##########"
awk '
/^--- / {
  ts=$2; pid=""; et=0; stat=""; comm=""
  for(i=1;i<=NF;i++){
    if($i~/^pid=/)pid=substr($i,5)
    else if($i~/^et=/){et=substr($i,4); sub(/s$/,"",et)}
    else if($i~/^stat=/)stat=substr($i,6)
    else if($i~/^comm=/)comm=substr($i,6)
  }
  if(!(pid in first))first[pid]=ts
  last[pid]=ts; cnt[pid]++; cm[pid]=comm
  if(et+0>maxet[pid])maxet[pid]=et+0
  if(index("/"allstat[pid]"/","/"stat"/")==0)allstat[pid]=allstat[pid]"/"stat
  cur=pid
}
/^    wchan:/ { v=($2==""?"(empty)":$2); k=cur"|"v; if(cur!=""&&!(k in sw)){sw[k]=1; wl[cur]=wl[cur] v ","} }
/^    syscall:/ { v=($2==""?"(none)":$2); k=cur"|"v; if(cur!=""&&!(k in ss)){ss[k]=1; sl[cur]=sl[cur] v ","} }
END { for(p in first) printf "pid=%-8s %-13s first=%s last=%s maxet=%-3ss n=%-4s stat=%s wchan={%s} sysc={%s}\n", p,cm[p],first[p],last[p],maxet[p],cnt[p],allstat[p],wl[p],sl[p] }
' "$D/stuck.log" | sort -t= -k4

echo
echo "########## B. raw stuck.log lines for pids with maxet >= 25 (the genuine hangs) ##########"
# find pids whose maxet >= 25
hangpids=$(awk '
/^--- / { for(i=1;i<=NF;i++){ if($i~/^pid=/)pid=substr($i,5); if($i~/^et=/){et=substr($i,4);sub(/s$/,"",et)} } if(et+0>m[pid])m[pid]=et+0 }
END { for(p in m) if(m[p]>=25) print p }
' "$D/stuck.log")
echo "hang pids (maxet>=25): $hangpids"
for p in $hangpids; do
  echo "----- pid $p full timeline -----"
  grep -A3 "pid=$p " "$D/stuck.log" | grep -E "(pid=$p |wchan|syscall|stack)"
done

echo
echo "########## C. conns.log (sshd-session count / syn-recv over time) ##########"
cat "$D/conns.log"

echo
echo "########## D. pcap SYN packets (connection starts) ##########"
tcpdump -nn -tttt -r "$D/cap.pcap" 'tcp[tcpflags] & tcp-syn != 0' 2>/dev/null

echo
echo "########## E. full pcap text dump ##########"
tcpdump -nn -tttt -S -r "$D/cap.pcap" 2>/dev/null
