#!/usr/bin/env python3
"""Strict, local acceptance evidence. Never flashes a unit or publishes artifacts.

    python3 tools/verify/acceptance.py --remix <name> [<name> ...] (--project DIR | --stress-source DIR)
    make accept REMIX=<name> STRESS_SOURCE=<dir>
    make accept REMIXES="a b c" STRESS_SOURCE=<dir>

Gates, in order: preflight and fixture per remix; `make check-shared` ONCE
for every remix that passed them (the remix-independent half: the ledger
selftest, the knob census, the isolated module gates); then per remix
`make check-remix` with its project, the static cycle report, the
pressure price and the pressure render on its own restored image. One
remix's report is at --out; several are at --out/<remix>/report.json with
the shared half's log beside them and summary.json over all.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
import pathlib
import platform
import re
import shutil
import signal
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import toolpath  # noqa: E402,F401
from remix import registry  # noqa: E402

SCHEMA_VERSION = 2
# A skip means missing evidence, even if the child returns zero. [N/A] is
# reserved for an explicit inapplicable branch in a verifier.
SKIP = re.compile(r"^\s*(?:\[SKIP\]|SKIP:)", re.M)
FAIL = re.compile(r"^\s*\[FAIL\]", re.M)
NA = re.compile(r"^\s*\[N/A\].*$", re.M)
LIMITATIONS = [
    "Emulator evidence is not hardware validation.",
    "DSP static costs omit contention; instruction meters are not CPU percentages.",
    "No calibrated ColdFire deadline, storage I/O budget, or hardware soak is certified.",
    "Pressure samples layouts; it does not prove every ordering or cross-core timing.",
    "Generated project playback covers A01; A02-A04 transitions are not automated here.",
]


def sha256(path):
    with open(path, "rb") as f:
        digest = hashlib.sha256()
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inventory(path):
    """Hashes only: never put firmware, project bytes, or audio in the report."""
    return {p.relative_to(path).as_posix(): sha256(p)
            for p in sorted(path.rglob("*")) if p.is_file()}


def sample_inventory(project):
    """Project sample paths may point outside the project, e.g. ../AUDIO."""
    from ot_project import read_project
    _, slots = read_project(project)
    result = {}
    for slot in slots:
        rel = slot["path"]
        if not rel:
            continue
        path = (project / rel).resolve()
        metadata = path.with_suffix(".ot")
        result[rel] = dict(sha256=sha256(path) if path.is_file() else None,
                           metadata_sha256=sha256(metadata) if metadata.is_file() else None)
    return result


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def provenance():
    binaries = [
        ROOT / "vendor/dsp56300/build/source/dsp_host/dsp_asm",
        ROOT / "vendor/dsp56300/build/source/dsp_host/dsp_host",
        ROOT / "out/emu/ot_emu",
    ]
    for name in ("make", "m68k-elf-as", "m68k-elf-ld", "m68k-elf-gcc"):
        if shutil.which(name):
            binaries.append(pathlib.Path(shutil.which(name)))
    return {
        "commit": git("rev-parse", "HEAD"),
        "working_tree": git("status", "--porcelain", "--untracked-files=all"),
        "source_sha256": {name: sha256(ROOT / name) for name in
                          subprocess.check_output(["git", "ls-files", "-z", "--cached",
                                                   "--others", "--exclude-standard"],
                                                  cwd=ROOT).decode().split("\0")
                          if name and (ROOT / name).is_file()},
        "diff_sha256": hashlib.sha256(subprocess.check_output(
            ["git", "diff", "HEAD", "--binary"], cwd=ROOT)).hexdigest(),
        "submodules": git("submodule", "status", "--recursive").splitlines(),
        "python": sys.version,
        "platform": platform.platform(),
        "tools": {str(p): sha256(p) for p in binaries if p.is_file()},
        "firmware_sha256": (sha256(ROOT / "out/raw/section_3_MAIN_OS.bin")
                            if (ROOT / "out/raw/section_3_MAIN_OS.bin").is_file() else None),
    }


def run_gate(name, command, out, env, timeout, cwd=None):
    """A failed command, timeout, or successful-but-skipped gate cannot pass."""
    cwd = cwd or ROOT
    log = out / (name + ".log")
    start = time.monotonic()
    result = dict(name=name, command=command, status="failed", exit_code=None,
                  log=log.name, duration_seconds=0, skips=[], not_applicable=[])
    print(f"acceptance: {name}", flush=True)
    stdout = out / (name + ".stdout")
    with log.open("w", encoding="utf-8") as f, stdout.open("w", encoding="utf-8") as output:
        try:
            proc = subprocess.Popen(command, cwd=cwd, env=env, stdout=output,
                                    stderr=f,
                                    start_new_session=(os.name == "posix"))
            try:
                result["exit_code"] = proc.wait(timeout=timeout)
            except (subprocess.TimeoutExpired, KeyboardInterrupt) as exc:
                if os.name == "posix":
                    os.killpg(proc.pid, signal.SIGKILL)
                else:
                    proc.kill()
                proc.wait()
                if isinstance(exc, KeyboardInterrupt):
                    raise
                result["reason"] = f"timed out after {timeout} seconds"
        except OSError as exc:
            result["reason"] = str(exc)
    text = stdout.read_text(encoding="utf-8", errors="replace") + "\n" + log.read_text(encoding="utf-8", errors="replace")
    log.write_text(text, encoding="utf-8")
    result["stdout"] = stdout.name
    result["skips"] = [line.strip() for line in text.splitlines() if SKIP.match(line)]
    result["not_applicable"] = [line.strip() for line in NA.findall(text)]
    if result["exit_code"] == 0 and not FAIL.search(text):
        result["status"] = "blocked" if result["skips"] else "passed"
    result["duration_seconds"] = round(time.monotonic() - start, 3)
    print(f"acceptance: {name}: {result['status']} ({log})", flush=True)
    return result


def budget_result(data):
    """A lower-bound estimate over the wall is a rejection; below is no guarantee."""
    if (not isinstance(data.get("worst_core"), int)
            or not isinstance(data.get("usable"), int) or data["usable"] <= 0):
        raise ValueError("cycle report has no valid worst_core/usable measurement")
    return "failed" if data["worst_core"] > data["usable"] else "passed"


def _effect(m):
    """A DSP module the fixture can put on a track and the pricer can meter:
    one with a chooser row. A DspSection reached by a hook alone (menu None,
    USB AUDIO IN's RX inject) is placed by the build but is no effect."""
    return m.dsp is not None and getattr(m, "menu", 1) is not None


def pressure_profile(modules):
    """Ready when every DSP module of the selection declares its dearest
    settings (schema.Module.dear); blocked, by name, when one does not. A
    module is never rendered at default knobs and called covered."""
    blockers = [f"{m.key}: {m.pressure_blocker}" for m in modules
                if getattr(m, "pressure_blocker", "")]
    if blockers:
        return "blocked", "; ".join(sorted(blockers))
    dsp = [m for m in modules if _effect(m)]
    if not dsp:
        return "not_applicable", "remix has no DSP modules"
    missing = sorted(m.key for m in dsp
                     if getattr(m, "params", ()) and not getattr(m, "dear", None))
    if missing:
        return "blocked", ("no dearest settings (schema.Module.dear) for "
                           + ", ".join(missing))
    return "ready", "every DSP module declares its dearest settings: " + ", ".join(sorted(m.key for m in dsp))


def pressure_evidence_error(rows, price):
    """Missing meters or layouts are missing evidence, even after exit zero."""
    counts = {}
    for row in rows:
        core = row.get("core")
        if core not in (0, 1) or row.get("rc") != 0 or row.get("flags"):
            return "failed or invalid pressure layout"
        meter = row.get("meter", {}).get(str(core))
        if not meter or len(meter) != 2 or any(v <= 0 for v in meter):
            return "pressure layout has no positive instruction meter"
        counts[core] = counts.get(core, 0) + 1
    for core in (0, 1):
        label = f"core {core} (T{'5-8' if core == 0 else '1-4'})"
        layouts = price["cores"][label]["layouts"]
        expected = min(6, layouts) + min(4, max(0, layouts - 6))
        if expected == 0 or counts.get(core, 0) != expected:
            return f"core {core}: incomplete pressure sample"
    return None


def aggregate(gates):
    if any(g["status"] == "failed" for g in gates):
        return "failed"
    if any(g["status"] in ("blocked", "not_run") for g in gates):
        return "blocked"
    return "passed"


def write_report(out, report):
    report["status"] = aggregate(report["gates"]) if "finished_at" in report else "running"
    tmp = out / "report.json.tmp"
    tmp.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    tmp.replace(out / "report.json")


GATES = ("preflight", "fixture", "check_shared", "check_remix", "cycles", "pressure_price", "pressure_render")


class Run:
    """One remix's report: its gates, its output directory, its environment."""

    def __init__(self, remix, out, env, timeout, tree=None):
        self.remix, self.out, self.timeout = remix, out, timeout
        self.tree = tree or ROOT   # the worktree the per-remix stages run in (a shard with --jobs)
        self.env = dict(env, REMIX=remix)
        self.out.mkdir(parents=True, exist_ok=True)
        self.report = dict(schema_version=SCHEMA_VERSION, remix=remix,
                           started_at=dt.datetime.now(dt.timezone.utc).isoformat(),
                           status="blocked", validation_level="local-emulator",
                           hardware_validated=False, limitations=LIMITATIONS,
                           gates=[dict(name=n, status="not_run") for n in GATES],
                           provenance={}, modules=[], fixtures={}, measurements={})
        self.project = None
        self.profile = self.reason = None
        self.stopped = False
        write_report(self.out, self.report)

    def record(self, result):
        self.report["gates"][GATES.index(result["name"])] = result
        write_report(self.out, self.report)
        ok = result["status"] in ("passed", "not_applicable")
        if not ok:
            self.stopped = True
        return ok

    def run(self, name, command):
        # cwd only when sharded: the tests fake run_gate with the five-argument signature
        extra = {} if self.tree == ROOT else {"cwd": self.tree}
        return self.record(run_gate(name, command, self.out, self.env, self.timeout, **extra))

    def fail(self, exc):
        self.report["gates"].append(dict(name="runner", status="failed", reason=str(exc)))
        self.stopped = True

    def finish(self):
        self.report["finished_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
        write_report(self.out, self.report)
        print(f"acceptance: {self.remix}: {self.report['status']}: {self.out / 'report.json'}", flush=True)
        return self.report["status"]


RUNNER_ERRORS = (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError, SystemExit)


def preflight(r, args, provenance_data):
    r.report["provenance"] = dict(provenance_data)
    remix = registry.remix(r.remix)
    modules = registry.selected(remix)
    r.report["modules"] = [
        dict(key=m.key, name=m.name, kind=m.kind.value,
             manifest_sha256=(sha256(ROOT / "modules" / m.name / "manifest.py")
                              if (ROOT / "modules" / m.name / "manifest.py").is_file() else None))
        for m in modules]
    r.profile, r.reason = pressure_profile(modules)
    project = args.project
    if project is None and args.stress_source is None and os.environ.get("OT_PROJECT"):
        project = pathlib.Path(os.environ["OT_PROJECT"])
    problems = []
    if project is None and args.stress_source is None:
        problems.append("provide --project / OT_PROJECT or --stress-source")
    # A blocked pressure profile (a DSP module without `dear`) blocks the
    # pressure stages, not the check stages: the report still carries the
    # remix's check evidence, and says by name why it is blocked.
    required = [ROOT / "out/raw/section_3_MAIN_OS.bin",
                ROOT / "out/emu/ot_emu", ROOT / ".venv/bin/python3"]
    if any(_effect(m) for m in modules):
        required += [ROOT / "vendor/dsp56300/build/source/dsp_host/dsp_host",
                     ROOT / "vendor/dsp56300/build/source/dsp_host/dsp_asm"]
    problems += [f"missing prerequisite: {p}" for p in required if not p.is_file()]
    r.project = project
    r.record(dict(name="preflight", status="blocked" if problems else "passed",
                  reasons=problems, pressure_profile=r.reason))


def fixture(r, args):
    if args.stress_source and r.profile != "ready":
        # The stress fixture is the pressure fixture: every DSP module at its
        # dearest settings. With nothing of ours to place the generator
        # refuses; with a module that declares no `dear` it would place the
        # module at settings nobody vouched for (CF METER on every FX2 slot
        # silenced seven tracks, 28 Sep 2026). Either way the source project
        # itself is the fixture, as an operator project would be.
        r.project = args.stress_source
        args = argparse.Namespace(stress_source=None)
        note = f"source project as-is: {r.reason}"
    else:
        note = "operator-supplied project"
    if args.stress_source:
        source = args.stress_source.expanduser().resolve()
        project = r.out / "STRESS"
        if not r.run("fixture", [sys.executable, "tools/harness/stress_project.py",
                                 "--remix", r.remix, "--source", str(source), "--out", str(project)]):
            return
        r.report["fixtures"]["source"] = {
            p.name: sha256(p) for p in sorted(source.iterdir())
            if p.is_file() and p.suffix in (".work", ".strd")}
    else:
        project = r.project.expanduser().resolve()
        if not (project / "project.work").is_file() or not (project / "bank01.work").is_file():
            r.record(dict(name="fixture", status="blocked", reason="project.work and bank01.work are required"))
            return
        r.record(dict(name="fixture", status="passed", reason=note))
    r.project = project
    r.report["fixtures"]["project"] = inventory(project)
    r.report["fixtures"]["referenced_samples"] = sample_inventory(project)
    r.env["OT_PROJECT"] = str(project)
    r.report["parameters"] = dict(build=r.env["BUILD"], bank=r.env.get("OT_BANK"),
                                  pressure=dict(top=6, sample=4, seed=1, seconds=2, frames=16))
    r.report["measurements"]["units"] = dict(
        dsp_static="static cycles/sample/core; contention omitted",
        pressure_meter="emulated instructions/block and instructions/sample/core")
    write_report(r.out, r.report)


def check_shared(runs, out, env, timeout):
    """The remix-independent half of make check, once for every live remix;
    its one result is every report's check_shared gate, the log shared."""
    names = " ".join(r.remix for r in runs)
    shared_env = dict(env, REMIXES=names, REMIX=runs[0].remix)
    result = run_gate("check_shared", ["make", "-j1", "check-shared", f"REMIXES={names}",
                                       f"BUILD={env['BUILD']}"], out, shared_env, timeout)
    for r in runs:
        mine = dict(result)
        for key in ("log", "stdout"):
            mine[key] = os.path.relpath(out / result[key], r.out)
        r.record(mine)


def remix_stages(r):
    """check-remix with the project, the static cycle report, the pressure
    price and the pressure render, each on this remix's own image."""
    if not r.run("check_remix", ["make", "-j1", "check-remix", f"REMIX={r.remix}",
                                 f"BUILD={r.env['BUILD']}", f"OT_PROJECT={r.project}"]):
        return
    # Preserve the exact restored image for every pressure invocation.
    image = r.out / "image.bin"
    shutil.copy2(r.tree / "out/mainos_bus.bin", image)
    r.report["provenance"]["image_sha256"] = sha256(image)
    if not r.run("cycles", [sys.executable, "tools/build/cycle_count.py", "--json"]):
        return
    data = json.loads((r.out / "cycles.stdout").read_text())
    r.report["measurements"]["dsp_static"] = data
    cycle_gate = r.report["gates"][GATES.index("cycles")]
    cycle_gate["status"] = budget_result(data)
    if not r.record(cycle_gate):
        return
    if r.profile in ("not_applicable", "blocked"):
        for name in ("pressure_price", "pressure_render"):
            r.record(dict(name=name, status=r.profile, reason=r.reason))
        return
    pressure_out = r.out / "pressure"
    if not r.run("pressure_price", [sys.executable, "tools/harness/pressure.py",
                                    "price", "--remix", r.remix, "--out", str(pressure_out)]):
        return
    price = json.loads((pressure_out / f"{r.remix}_price.json").read_text())
    r.report["measurements"]["pressure_price"] = price
    if any(core["over"] for core in price["cores"].values()):
        gate = r.report["gates"][GATES.index("pressure_price")]
        gate.update(status="failed", reason="selectable layouts exceed the static DSP wall")
        r.record(gate)
        return
    # Deterministic, non-silent input on ALL eight tracks, no external audio.
    from stress_project import make_sample
    stems = r.out / "stems"
    stems.mkdir()
    for track in range(1, 9):
        make_sample(stems / f"T{track}.wav")
    r.report["fixtures"]["stems"] = inventory(stems)
    rendered_ok = r.run("pressure_render", [sys.executable, "tools/harness/pressure.py",
                                            "render", "--remix", r.remix, "--image", str(image),
                                            "--out", str(pressure_out), "--stems", str(stems),
                                            "--top", "6", "--sample", "4", "--seed", "1",
                                            "--seconds", "2"])
    result_file = pressure_out / f"{r.remix}_render.json"
    rendered = json.loads(result_file.read_text()) if result_file.is_file() else []
    r.report["measurements"]["pressure_render"] = rendered
    if not rendered_ok:
        return
    evidence_error = pressure_evidence_error(rendered, price)
    if evidence_error:
        gate = r.report["gates"][GATES.index("pressure_render")]
        gate.update(status="failed", reason=evidence_error)
        r.record(gate)


def run_sharded(live, jobs):
    """The per-remix stages of `jobs` remixes at a time, each remix in a
    shard worktree (check_shards.make_shard: HEAD + this tree's diff, its
    own port build), handed out from one queue so the dearest remix does
    not set the wall. The shared half ran once in this tree already."""
    import queue as queue_mod
    import threading
    import check_shards
    shards = [ROOT / "out/shards" / str(i) for i in range(jobs)]
    (ROOT / "out/shards").mkdir(parents=True, exist_ok=True)
    print(f"acceptance: {len(live)} remixes over {jobs} shards under out/shards/", flush=True)
    for s in shards:
        check_shards.make_shard(s, ROOT / "out/shards" / f"{s.name}.setup.log")
    todo = queue_mod.Queue()
    for r in live:
        todo.put(r)

    def worker(shard):
        while True:
            try:
                r = todo.get_nowait()
            except queue_mod.Empty:
                return
            r.tree = shard
            try:
                remix_stages(r)
            except RUNNER_ERRORS as exc:
                r.fail(exc)
    threads = [threading.Thread(target=worker, args=(s,)) for s in shards]
    for t in threads:
        t.start()
    for t in threads:
        t.join()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--remix", nargs="+",
                    default=(os.environ.get("REMIXES") or os.environ.get("REMIX") or "").split() or None,
                    help="one remix, or several: the remix-independent half of make check runs once")
    fixture_group = ap.add_mutually_exclusive_group()
    fixture_group.add_argument("--project", type=pathlib.Path)
    fixture_group.add_argument("--stress-source", type=pathlib.Path,
                               help="generate each remix's stress fixture from a local project")
    ap.add_argument("--out", type=pathlib.Path,
                    default=ROOT / "out/acceptance" / dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"))
    ap.add_argument("--timeout", type=int, default=3600, help="seconds per command")
    ap.add_argument("--jobs", type=int, default=1,
                    help="the per-remix stages of N remixes at a time, each in its own worktree under out/shards/ "
                         "(tools/verify/check_shards.py); the shared half still runs once, here")
    args = ap.parse_args(argv)
    if args.jobs <= 0:
        ap.error("--jobs must be positive")
    if args.timeout <= 0:
        ap.error("--timeout must be positive")
    out = args.out.resolve()
    if out.exists():
        ap.error("--out already exists; choose a fresh directory to avoid stale evidence")
    if not args.remix:
        ap.error("--remix is required (or REMIX / REMIXES in the environment)")
    remixes = list(dict.fromkeys(args.remix))
    out.mkdir(parents=True)

    env = dict(os.environ)
    # Serialize recursive Make even when this runner is invoked by make -j.
    for var in ("MAKEFLAGS", "MFLAGS", "MAKEOVERRIDES"):
        env.pop(var, None)
    env.setdefault("BUILD", "0")

    # One remix: the report at --out, as before. Several: --out/<remix>/
    # each, the shared half's log beside them, summary.json over all.
    runs = [Run(name, out if len(remixes) == 1 else out / name, env, args.timeout) for name in remixes]
    try:
        provenance_data = provenance()
    except RUNNER_ERRORS as exc:
        provenance_data = {}
        for r in runs:
            r.fail(exc)
    for r in runs:
        if r.stopped:
            continue
        try:
            preflight(r, args, provenance_data)
            if not r.stopped:
                fixture(r, args)
        except RUNNER_ERRORS as exc:
            r.fail(exc)
    live = [r for r in runs if not r.stopped]
    if live:
        try:
            check_shared(live, out, env, args.timeout)
        except RUNNER_ERRORS as exc:
            for r in live:
                r.fail(exc)
    live = [r for r in live if not r.stopped]
    if args.jobs > 1 and len(live) > 1:
        run_sharded(live, min(args.jobs, len(live)))
    else:
        for r in live:
            try:
                remix_stages(r)
            except RUNNER_ERRORS as exc:
                r.fail(exc)
    statuses = {r.remix: r.finish() for r in runs}
    if len(runs) > 1:
        (out / "summary.json").write_text(json.dumps(statuses, indent=2) + "\n", encoding="utf-8")
        print(f"acceptance: {sum(s == 'passed' for s in statuses.values())} of {len(runs)} passed: {out / 'summary.json'}",
              flush=True)
    return 0 if all(s == "passed" for s in statuses.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
