#!/bin/bash
# VPS-side SSH hang diagnostic. Captures tcpdump + per-second /proc snapshots
# of every sshd process aged 6-50s (= hung handshakes + own control session
# first 50s + lingering bots). No strace: /proc/PID/{wchan,syscall,stack} are
# passive snapshots that pinpoint where a stuck process is blocked in-kernel.
CLIENT_IP="${1:?need client ip}"
DUR="${2:-220}"
D=/tmp/sshdiag
rm -rf "$D"; mkdir -p "$D"
echo "start $(date -u '+%F %H:%M:%S')Z client=$CLIENT_IP dur=${DUR}s" > "$D/run.log"

if command -v tcpdump >/dev/null 2>&1; then
  ( timeout "$DUR" tcpdump -ni any "tcp port 22 and host $CLIENT_IP" -w "$D/cap.pcap" ) >"$D/tcpdump.log" 2>&1 &
  echo "tcpdump started pid $!" >> "$D/run.log"
else
  echo "tcpdump NOT available" >> "$D/run.log"
fi

END=$(( $(date +%s) + DUR ))
while [ "$(date +%s)" -lt "$END" ]; do
  ts=$(date -u '+%H:%M:%S')
  ps -eo pid,ppid,etimes,stat,comm,args 2>/dev/null | grep -E 'sshd' | grep -v grep | \
  while read -r pid ppid et stat comm args; do
    case "$et" in ''|*[!0-9]*) continue;; esac
    if [ "$et" -ge 6 ] && [ "$et" -le 50 ]; then
      {
        echo "--- ${ts}Z pid=$pid ppid=$ppid et=${et}s stat=$stat comm=$comm"
        echo "    args: $args"
        echo "    wchan: $(cat /proc/$pid/wchan 2>/dev/null)"
        echo "    syscall: $(cat /proc/$pid/syscall 2>/dev/null)"
        echo "    stack: $(cat /proc/$pid/stack 2>/dev/null | tr '\n' '|')"
      } >> "$D/stuck.log"
    fi
  done
  echo "${ts}Z sshd_session_total=$(pgrep -c -x sshd-session 2>/dev/null || echo 0) syn_recv=$(ss -tnH state syn-recv 'sport = :22' 2>/dev/null | wc -l) estab=$(ss -tnH state established 'sport = :22' 2>/dev/null | wc -l)" >> "$D/conns.log"
  sleep 1
done
echo "end $(date -u '+%F %H:%M:%S')Z" >> "$D/run.log"
