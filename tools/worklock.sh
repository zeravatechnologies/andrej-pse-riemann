#!/usr/bin/env bash
# Autonomous-build lock. Prevents two Claude sessions working at once.
#   tools/worklock.sh beat    -> refresh heartbeat (call often while working)
#   tools/worklock.sh check   -> exit 0 if lock is FREE (stale >20 min or absent), 1 if someone is working
#   tools/worklock.sh release -> remove lock
L="$(dirname "$0")/../.worklock"
case "$1" in
  beat)    date +%s > "$L" ;;
  release) rm -f "$L" ;;
  check)   [ -f "$L" ] || exit 0
           age=$(( $(date +%s) - $(cat "$L" 2>/dev/null || echo 0) ))
           [ "$age" -gt 1200 ] && exit 0 || { echo "locked ($age s old)"; exit 1; } ;;
  *) echo "usage: beat|check|release"; exit 2 ;;
esac
