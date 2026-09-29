#!/usr/bin/env bash
# A copy of a stock Ghidra release with this directory's processor work added:
#
#   - processors/DSP56300: the DSP56300 processor module (language files
#     compiled with the release's own SLEIGH, the loop-end analyzer compiled
#     against the release's jars into lib/DSP56300.jar);
#   - patches/coldfire-emac.patch: ColdFire ISA_C/EMAC decoding and the
#     68000:BE:32:Coldfire_EMAC_frac variant, applied to Ghidra/Processors/68000;
#   - the decompiler binary, built with the release's gradle wrapper when the
#     release ships none for this machine (12.1.4 has linux_x86_64 and
#     win_x86_64 only).
#
#   tools/ghidra/install.sh <stock install> [dest]    # make ghidra-install GHIDRA=<stock install>
#
# The stock install is never modified. dest defaults to
# out/ghidra/<stock dir name>-octabam; an existing dest this script made is
# replaced, anything else there is refused. Written against the 12.1.4
# release; another version is attempted only if the patch applies.
# DEBUG=1 streams every step's output; otherwise it goes to <dest>.install.log.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
TESTED=12.1.4
MARK=.octabam-install

die() { echo "ghidra-install: $*" >&2; exit 1; }
say() { echo "[ghidra-install] $*"; }

[ $# -ge 1 ] && [ -n "$1" ] || die "usage: $0 <stock Ghidra install> [dest]  (make ghidra-install GHIDRA=...)"
STOCK="$(cd "$1" 2>/dev/null && pwd)" || die "no such directory: $1"
PROPS="$STOCK/Ghidra/application.properties"
[ -f "$PROPS" ] && [ -x "$STOCK/support/analyzeHeadless" ] || die "$STOCK is not a Ghidra install (no Ghidra/application.properties)"
[ -e "$STOCK/$MARK" ] && die "$STOCK is already an octabam install; pass the stock release"
VERSION="$(sed -n 's/^application.version=//p' "$PROPS")"
DEST="${2:-$ROOT/out/ghidra/$(basename "$STOCK")-octabam}"
case "$DEST" in /*) ;; *) DEST="$PWD/$DEST" ;; esac
LOG="$DEST.install.log"

# Output of the long steps: streamed under DEBUG, else to the log.
run() {
    if [ -n "${DEBUG:-}" ]; then
        echo "+ $*" >&2
        "$@" 2>&1 | tee -a "$LOG"
        return "${PIPESTATUS[0]}"
    fi
    "$@" >>"$LOG" 2>&1 || { echo "ghidra-install: failed: $*" >&2; tail -n 25 "$LOG" >&2; echo "(the full log is $LOG)" >&2; return 1; }
}

# A JDK: Ghidra's own launcher wants the same one, so check it here once.
JAVAC="${JAVA_HOME:+$JAVA_HOME/bin/}javac"
JAR="${JAVA_HOME:+$JAVA_HOME/bin/}jar"
command -v "$JAVAC" >/dev/null || die "no javac: install a JDK $(sed -n 's/^application.java.min=//p' "$PROPS")+ or set JAVA_HOME"
JMIN="$(sed -n 's/^application.java.min=//p' "$PROPS")"
JVER="$("$JAVAC" -version 2>&1 | sed -n 's/^javac \([0-9]*\).*/\1/p')"
[ -n "$JVER" ] && [ "$JVER" -ge "${JMIN:-21}" ] || die "$JAVAC is JDK ${JVER:-?}; Ghidra $VERSION needs ${JMIN:-21}+ (set JAVA_HOME)"

# The native platform is the JVM's, as Ghidra and gradle pick it, not the
# shell's: an x86_64 bash under Rosetta reports x86_64 on an arm64 Mac.
JAVA="${JAVA_HOME:+$JAVA_HOME/bin/}java"
JPROPS="$("$JAVA" -XshowSettings:properties -version 2>&1)" || die "$JAVA -XshowSettings:properties failed"
jprop() { printf '%s\n' "$JPROPS" | sed -n "s/^ *$1 = //p"; }
JOS="$(jprop os.name)" JARCH="$(jprop os.arch)"
case "$JOS-$JARCH" in
    "Mac OS X-aarch64") PLATFORM=mac_arm_64 ;;
    "Mac OS X-x86_64") PLATFORM=mac_x86_64 ;;
    Linux-amd64 | Linux-x86_64) PLATFORM=linux_x86_64 ;;
    Linux-aarch64) PLATFORM=linux_arm_64 ;;
    *) die "no Ghidra native platform for $JAVA's os.name=${JOS:-?} os.arch=${JARCH:-?}" ;;
esac

[ "$VERSION" = "$TESTED" ] || say "warning: $STOCK is Ghidra $VERSION; this is written against $TESTED (continuing if the patch applies)"
patch --dry-run -s -p1 -d "$STOCK" <"$HERE/patches/coldfire-emac.patch" >/dev/null 2>&1 ||
    die "patches/coldfire-emac.patch does not apply to Ghidra $VERSION's 68000 module ($TESTED's applies as-is)"

if [ -e "$DEST" ]; then
    [ -e "$DEST/$MARK" ] || die "$DEST exists and is not an octabam install; remove it or pass another dest"
    say "replacing $DEST"
    rm -rf "${DEST:?}"
fi
mkdir -p "$(dirname "$DEST")"
: >"$LOG"

say "copying Ghidra $VERSION to $DEST"
cp -Rp "$STOCK" "$DEST"
echo "stock=$STOCK version=$VERSION source=$(git -C "$ROOT" rev-parse --short HEAD 2>/dev/null || echo unknown)" >"$DEST/$MARK"

say "ColdFire: patches/coldfire-emac.patch"
run patch -p1 -d "$DEST" <"$HERE/patches/coldfire-emac.patch"
run "$DEST/support/sleigh" -a "$DEST/Ghidra/Processors/68000/data/languages"

say "DSP56300: processors/DSP56300"
MOD="$DEST/Ghidra/Processors/DSP56300"
SRC="$HERE/processors/DSP56300"
# build.gradle stays out: the distribution's support/gradle includes every
# directory with one, and the module's applies build scripts only a source
# tree has, which breaks buildNatives below.
mkdir -p "$MOD/lib"
cp -Rp "$SRC/Module.manifest" "$SRC/README.md" "$SRC/data" "$MOD/"
run "$DEST/support/sleigh" -a "$MOD/data/languages"
CLASSES="$DEST.classes"
rm -rf "${CLASSES:?}"
mkdir -p "$CLASSES"
CP="$(find "$DEST/Ghidra" -path '*/lib/*.jar' | tr '\n' ':')"
run "$JAVAC" --release "${JMIN:-21}" -nowarn -cp "$CP" -d "$CLASSES" $(find "$SRC/src/main/java" -name '*.java')
run "$JAR" cf "$MOD/lib/DSP56300.jar" -C "$CLASSES" .
rm -rf "${CLASSES:?}"

for spec in "$MOD/data/languages/"*.slaspec "$DEST/Ghidra/Processors/68000/data/languages/coldfire.slaspec"; do
    [ -s "${spec%.slaspec}.sla" ] || die "no ${spec%.slaspec}.sla after compiling (see $LOG)"
done

# Ghidra looks in a module's build/os/<platform> (where buildNatives puts
# them) before its os/<platform> (where a release ships them).
DECOMP="Ghidra/Features/Decompiler/os/$PLATFORM/decompile"
BUILT="Ghidra/Features/Decompiler/build/os/$PLATFORM/decompile"
if [ -x "$DEST/$DECOMP" ]; then
    say "decompiler: the release ships $PLATFORM"
else
    say "decompiler: the release has none for $PLATFORM; building natives (a few minutes; needs a C++ toolchain and the network for gradle)"
    (cd "$DEST/support/gradle" && run ./gradlew --no-daemon buildNatives)
    [ -x "$DEST/$BUILT" ] || die "buildNatives finished without $BUILT (see $LOG)"
fi

say "done: Ghidra $VERSION + DSP56300 + ColdFire EMAC at $DEST"
say "next: make ghidra GHIDRA=$DEST"
