#!/bin/sh
# Build md_replay with a read hook, in a scratch tree, and record which memory
# space (P, X, Y) the MD's voice DSP reads each external word through.
#
#   tools/harness/md_reference/md_reads.sh <scratch dir> <capture dir>...
#
# The hook goes into a COPY of vendor/gearmulator-md-mm's dsp56300 (one line in
# Memory::get, before the address translation, so the space is the one the
# instruction named). The copy is built with the interpreter: JIT code reads
# memory without calling Memory::get, so a JIT build would see nothing. The
# shared vendor tree and out/md_reference stay untouched. Each capture is
# replayed plain (MD addresses) from a directory of symlinks, since md_replay
# rewrites written.txt. Then:
#
#   python3 tools/harness/md_reference/md_reads.py <scratch dir>/reads/*/reads.txt
set -eu
ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
S=$1; shift
mkdir -p "$S"
if [ ! -x "$S/build/md_replay_reads" ]; then
	rsync -a --exclude wxWidgets --exclude .git --exclude .DS_Store \
		"$ROOT/vendor/gearmulator-md-mm/source/dsp56300/" "$S/dsp56300/"
	python3 - "$S/dsp56300/source/dsp56kEmu" <<'EOF'
import sys
from pathlib import Path
d = Path(sys.argv[1])
c = d / "memory.cpp"; t = c.read_text()
a = "\tTWord Memory::get( EMemArea _area, TWord _offset ) const\n\t{\n"
assert a in t
t = t.replace(a, a + "\t\tif(g_mdReadHook) g_mdReadHook(_area, _offset);\n", 1)
t = t.replace("namespace dsp56k\n{\n", "namespace dsp56k\n{\n\tvoid (*g_mdReadHook)(EMemArea, TWord) = nullptr;\n", 1)
c.write_text(t)
h = d / "memory.h"; t = h.read_text()
a = "\tclass IMemoryValidator\n"
assert a in t
h.write_text(t.replace(a, "\textern void (*g_mdReadHook)(EMemArea, TWord);\n\n" + a, 1))
EOF
	cat > "$S/CMakeLists.txt" <<EOF
cmake_minimum_required(VERSION 3.15)
project(mdreads CXX C)
set(CMAKE_CXX_STANDARD 17)
set(DSP56K_FORCE_INTERPRETER ON CACHE BOOL "" FORCE)
set(BUILD_TESTING OFF CACHE BOOL "" FORCE)
include($S/dsp56300/source/base.cmake)
add_subdirectory($S/dsp56300/source/asmjit asmjit)
add_subdirectory($S/dsp56300/source/dsp56kBase dsp56kBase)
add_subdirectory($S/dsp56300/source/dsp56kEmu dsp56kEmu)
add_executable(md_replay_reads $ROOT/tools/harness/md_reference/md_replay.cpp)
target_compile_definitions(md_replay_reads PRIVATE MD_REPLAY_READS=1)
target_link_libraries(md_replay_reads PRIVATE dsp56kEmu)
EOF
	cmake -S "$S" -B "$S/build" -DCMAKE_BUILD_TYPE=Release >/dev/null
	cmake --build "$S/build" --target md_replay_reads -j8 >/dev/null
fi
for src in "$@"; do
	d="$S/reads/$(basename "$src")"
	rm -rf "$d"; mkdir -p "$d"
	for f in "$src"/*; do
		[ "$(basename "$f")" = written.txt ] || ln -s "$(cd "$(dirname "$f")" && pwd)/$(basename "$f")" "$d/"
	done
	r=$(MD_REPLAY_READS="$d/reads.txt" "$S/build/md_replay_reads" "$d" 2>&1 | grep blocks: || true)
	echo "$src $r"
done
