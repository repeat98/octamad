#!/bin/sh
# The twelve-kit gate (MACHINEDRUM_WORKPACKETS.md, section 1): for each
# capture, the plain replay (the baseline), then relocate to the layout with
# the placement plan, assemble the driver, and replay relocated with it.
#
#   tools/harness/md_reference/md_gate.sh [plan.json]
#
# The hot split comes from the fetch profiles in out/md_fetch/*/fetch.txt
# (md_replay MD_REPLAY_FETCH=2 on the cap4 kits, interpreter build); the plan
# from md_flip.py --plan (default out/machinedrum/plan.json). Prints one line
# per kit: plain and relocated block counts. Exit 1 when a relocated count
# differs from its own plain baseline.
set -eu
ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
PLAN=${1:-$ROOT/out/machinedrum/plan.json}
REPLAY=$ROOT/out/md_reference/md_replay
HOT=$(ls -d "$ROOT"/out/md_fetch/c* | paste -sd, -)
bad=0
for d in "$ROOT"/out/md_profile/cap4/c* "$ROOT"/out/md_profile/cap5/c*; do
	plain=$("$REPLAY" "$d" 2>&1 | grep 'blocks:' || echo 'blocks: failed')
	python3 "$ROOT/tools/harness/md_reference/md_relocate.py" --hot "$HOT" --plan "$PLAN" "$d" > "$d/relocate.log" 2>&1 \
		|| { echo "$(basename "$d"): relocate failed"; tail -3 "$d/relocate.log"; bad=1; continue; }
	python3 "$ROOT/tools/harness/md_reference/md_driver.py" "$d" --reloc > "$d/driver.log" 2>&1 \
		|| { echo "$(basename "$d"): driver failed"; tail -3 "$d/driver.log"; bad=1; continue; }
	moved=$("$REPLAY" "$d" --reloc --driver 2>&1 | grep 'blocks:' || echo 'blocks: failed')
	p=$(echo "$plain" | sed 's/.*blocks: //')
	m=$(echo "$moved" | sed 's/.*blocks: //')
	flag=""
	[ "$p" = "$m" ] || { flag="  <-- differs"; bad=1; }
	printf '%-7s plain %s\n        moved %s%s\n' "$(basename "$d")" "$p" "$m" "$flag"
done
exit $bad
