#!/usr/bin/env python3
"""The per-remix half of `make check` for several remixes, N worktrees at a time.

    python3 tools/verify/check_shards.py [--jobs N] [--keep] [--shards DIR] <remix> ...
    make check-remixes REMIXES="a b c" [JOBS=4]
    make reach RUN=1 JOBS=4            # the check-remix lines through this
    python3 tools/verify/check_shards.py --by-gate [--jobs N] <remix>
    make check-remix-gates REMIX=<name> [JOBS=4]

Every `make check-remix` builds over out/mainos_bus.bin and its verifiers
read out/, so one tree runs one remix at a time; PR #486's 25-remix table
was three worktrees driven by hand. This makes N detached worktrees of HEAD
plus the tree's uncommitted changes under out/shards/<i>, each with the
shared vendor/ and .venv/ links, the stock slice, its submodules and its
OWN port build (out/emu is never shared between trees: AGENTS.md), then
hands the remixes out from one queue as shards come free, so the dear ones
(bottleservice, rig-kits) do not decide the wall time. Logs land in
out/check_shards/<remix>.log; one table at the end; exit 1 when a remix
failed. The shards are KEPT between runs (since 28 Sep 2026): a run finds
out/shards/<i> in place and refreshes it -- `git checkout --detach` to this
tree's HEAD plus its uncommitted diff, `git submodule update`, the shard's
out/ wiped except emu/ and raw/, and the port rebuilt on its existing
CMake cache (nothing recompiles unless tools/emu changed) -- which turns
~220 s of setup (four worktrees, four `cmake --fresh` builds) into a few
seconds. `--fresh` rebuilds them from nothing; `--rm` removes them after.

THE LONG POLE IS SPLIT (29 Sep 2026). A remix whose half would set the
wall time runs as its gate jobs (as `--by-gate` below) in the same queue as
the other remixes' whole halves, longest first, so it no longer takes one
shard for the whole run while the others idle. Which remixes: `--split
auto` (the default) splits a remix whose last recorded time
(out/check_shards/times.json, written after every run) exceeds both 300 s
and the run's total over the shard count; with no record, the remixes that
carry OCTAKIT (every project load under it is ~32 s emulated; bottleservice
and mods were the floor of every run on 28-29 Sep 2026). `--split none`
runs every remix whole; `--split a,b` names them.

`--by-gate` shards ONE remix's per-remix half by gate instead: every gate
of `make verify-remix` (plus `make cycles`) is its own job, each shard
restores the remix's image with `make bus` before its job, and the wall
is the longest gate rather than the whole list. The gates never read one
another's results; they only ever shared out/. The image-stage module
gates boot the card verify_set stages (TEMPO BUS): their job stages it
itself (`verify_set.py --stage-only`) and runs on its own shard. The job list mirrors
the `verify-remix` recipe and refuses to run when the two name different
scripts.
"""
import argparse
import json
import os
import pathlib
import queue
import re
import shutil
import subprocess
import sys
import threading
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
SKIP = re.compile(r"^\s*(?:\[SKIP\]|SKIP:)")


def git(*args, cwd=ROOT, check=True):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=check)


def shard_ok(path):
    """A registered worktree of this repository at `path`."""
    if not (path / ".git").is_file():
        return False
    r = git("worktree", "list", "--porcelain", check=False)
    return f"worktree {path.resolve()}" in r.stdout.splitlines()


def make_shard(path, log, fresh=False):
    """A detached worktree of HEAD with this tree's uncommitted changes, the
    shared toolchain links, the stock slice, its submodules and its own
    port build -- created, or refreshed when one is already there."""
    keep = shard_ok(path) and not fresh
    if not keep:
        remove_shard(path)
        git("worktree", "add", "--detach", str(path), "HEAD")
    else:
        # Drop the previous run's applied diff and untracked copies, then
        # move to this tree's HEAD.
        for args in (("reset", "--hard", "--quiet"), ("clean", "-fdq"),
                     ("checkout", "--detach", "--quiet", git("rev-parse", "HEAD").stdout.strip())):
            git(*args, cwd=path)
    diff = subprocess.run(["git", "diff", "HEAD", "--binary", "--ignore-submodules=all"],
                          cwd=ROOT, capture_output=True, check=True).stdout
    if diff.strip():
        subprocess.run(["git", "apply", "--binary"], cwd=path, input=diff, check=True)
    for rel in git("ls-files", "--others", "--exclude-standard", "-z").stdout.split("\0"):
        if rel and (ROOT / rel).is_file():
            (path / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / rel, path / rel)
    for name in ("vendor", ".venv"):
        if (ROOT / name).exists() and not (path / name).exists():
            os.symlink(os.path.realpath(ROOT / name), path / name)
    out = path / "out"
    if keep:
        # No gate may read a previous run's artifact; the port build and
        # the stock slice are the two things worth keeping.
        for child in out.iterdir() if out.is_dir() else ():
            if child.name not in ("emu", "raw"):
                shutil.rmtree(child, ignore_errors=True) if child.is_dir() else child.unlink()
    (out / "raw").mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "out/raw/section_3_MAIN_OS.bin", out / "raw/section_3_MAIN_OS.bin")
    arch = os.uname().machine
    cmds = [["git", "submodule", "update", "--init"],
            # `make emu-cf` configures with --fresh (a cache from another
            # source path makes cmake refuse); a kept shard's cache names
            # its own, fixed path, so configure in place and let the build
            # recompile only what changed under tools/emu.
            ["cmake"] + ([] if keep else ["--fresh"]) + ["-B", "out/emu", "-S", "tools/emu/ot_emu",
                                                         f"-DCMAKE_OSX_ARCHITECTURES={arch}"],
            ["cmake", "--build", "out/emu", "-j8"],
            ["./out/emu/ot_emu", "--image", "out/raw/section_3_MAIN_OS.bin"]]
    with log.open("w") as f:
        f.write(f"# {'refreshed' if keep else 'created'} {path}\n")
        for cmd in cmds:
            f.write(f"$ {' '.join(cmd)}\n")
            f.flush()
            r = subprocess.run(cmd, cwd=path, stdout=f, stderr=subprocess.STDOUT, env=clean_env())
            if r.returncode:
                raise SystemExit(f"check_shards: {' '.join(cmd)} failed in {path} ({r.returncode}): {log}")


def remove_shard(path):
    if path.exists():
        git("worktree", "remove", "--force", str(path), check=False)
        shutil.rmtree(path, ignore_errors=True)
    git("worktree", "prune", check=False)


def clean_env():
    env = dict(os.environ)
    for var in ("MAKEFLAGS", "MFLAGS", "MAKEOVERRIDES"):
        env.pop(var, None)
    # every shard builds from this tree's memo (tools/remix/runtime_build.CACHE)
    env.setdefault("OCTABAM_CACHE", str(ROOT / "out/cache"))
    return env


def run_remix(shard, remix, logdir):
    log = logdir / f"{remix}.log"
    t0 = time.monotonic()
    with log.open("w") as f:
        r = subprocess.run(["make", "check-remix", f"REMIX={remix}"], cwd=shard,
                           stdout=f, stderr=subprocess.STDOUT, env=clean_env())
    text = log.read_text(errors="replace")
    skips = [l.strip() for l in text.splitlines() if SKIP.match(l)]
    return dict(remix=remix, rc=r.returncode, seconds=time.monotonic() - t0, skips=skips, log=log)


def remix_jobs(remix_name, shard):
    """The per-remix half as independent jobs: (name, [argv, ...], env,
    {recipe scripts the job stands for}). Mirrors `make verify-remix` +
    `make cycles`; `check_recipe` refuses drift."""
    sys.path.insert(0, str(ROOT / "tools")); import toolpath  # noqa: E402,F401
    from remix import registry  # noqa: E402
    import module_gates  # noqa: E402
    py = sys.executable
    venv = shard / ".venv/bin/python3"       # the shard links ROOT's .venv
    has_venv = (ROOT / ".venv/bin/python3").exists()
    PY = str(venv) if has_venv else py        # the Makefile's $(PY)
    env = {"REMIX": remix_name, "BUILD": os.environ.get("BUILD", "0")}
    V = "tools/verify"
    def job(name, cmds, *scripts):
        return (name, cmds, env, set(scripts))
    jobs = [
        job("cycles", [["make", "cycles", f"REMIX={remix_name}"]]),
        job("dirtystate", [[py, f"{V}/verify_dirtystate.py", remix_name]], f"{V}/verify_dirtystate.py"),
        job("initregs", [[py, f"{V}/verify_initregs.py", remix_name]], f"{V}/verify_initregs.py"),
        job("dram_boot", [[py, f"{V}/verify_dram_boot.py"]], f"{V}/verify_dram_boot.py"),
    ]
    for name in ("labels", "modenames", "hidden"):
        # as the Makefile: SKIP without the .venv, and the job still stands for the script
        jobs.append(job(name, [[str(venv), f"{V}/verify_{name}.py", remix_name]] if has_venv
                        else [["echo", f"  [SKIP] {name}: no .venv (make emu-setup)"]], f"{V}/verify_{name}.py"))
    remix = registry.remix(remix_name)
    for key, g in module_gates.collect(registry.selected(remix), "isolated", True):
        # As `make verify-remix` runs them: module_gates.py under $(PY), so a
        # gate without `venv` inherits the driver's interpreter. The script
        # path is relative so it runs in the shard's own tree.
        cmd = module_gates.command(g, remix_name, root=ROOT)
        cmd[0] = cmd[0] if g.venv else PY
        cmd[1] = str(g.script)
        jobs.append(job(f"gate:{pathlib.Path(g.script).stem}", [cmd], f"{V}/module_gates.py"))
    jobs.append(job("menu", [[py, f"{V}/verify_menu.py"], [py, f"{V}/verify_replaces.py", "--image", remix_name]],
                    f"{V}/verify_menu.py", f"{V}/verify_replaces.py"))
    jobs.append(job("set", [[py, f"{V}/verify_set.py", remix_name]], f"{V}/verify_set.py"))
    # The image-stage module gates (TEMPO BUS boots the card verify_set
    # stages) as their own job: verify_set --stage-only stages the same
    # image and card without running, so the two run on separate shards.
    jobs.append(job("image", [[py, f"{V}/verify_set.py", remix_name, "--stage-only"],
                              [PY, f"{V}/module_gates.py", remix_name, "--stage", "image"]],
                    f"{V}/module_gates.py"))
    jobs.append(job("usb", [[py, f"{V}/verify_usb.py"]], f"{V}/verify_usb.py"))
    return jobs


def choose_split(remixes, spec, times, jobs):
    """The remixes to run as gate jobs: named, none, or (auto) those whose
    last recorded time would set the wall time; with no record, those that
    carry OCTAKIT."""
    if spec == "none":
        return set()
    if spec != "auto":
        return {r for r in spec.split(",") if r in remixes}
    known = {r: times[r] for r in remixes if r in times}
    if len(known) == len(remixes):
        floor = max(300.0, sum(known.values()) / jobs)
        return {r for r, s in known.items() if s > floor}
    sys.path.insert(0, str(ROOT / "tools")); import toolpath  # noqa: E402,F401
    from remix import registry  # noqa: E402
    return {r for r in remixes if "OCTAKIT" in registry.remix(r).modules}


def check_recipe(jobs):
    """Every script the Makefile's verify-remix recipe runs is in the job
    list (module_gates.py stands for the gates it runs)."""
    sys.path.insert(0, str(ROOT / "tools/verify"))
    from reach import recipe_scripts  # noqa: E402
    recipe = recipe_scripts((ROOT / "Makefile").read_text(), "verify-remix")
    named = set().union(*(scripts for _n, _c, _e, scripts in jobs))
    missing = recipe - named
    if missing:
        raise SystemExit(f"check_shards: verify-remix runs {sorted(missing)} and the by-gate job list does not; "
                         f"add the job (check_shards.remix_jobs)")


def run_job(shard, remix, job, logdir):
    name, cmds, env_add, _scripts = job
    log = logdir / f"{name.replace(':', '_')}.log"
    env = clean_env()
    env.update(env_add)
    t0 = time.monotonic()
    rc = 0
    with log.open("w") as f:
        for cmd in [["make", "bus", f"REMIX={remix}"]] + cmds:
            f.write(f"$ {' '.join(cmd)}\n")
            f.flush()
            r = subprocess.run(cmd, cwd=shard, stdout=f, stderr=subprocess.STDOUT, env=env)
            if r.returncode:
                rc = r.returncode
                break
    text = log.read_text(errors="replace")
    skips = [l.strip() for l in text.splitlines() if SKIP.match(l)]
    return dict(remix=name, rc=rc, seconds=time.monotonic() - t0, skips=skips, log=log)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("remixes", nargs="+")
    ap.add_argument("--jobs", type=int, default=4, help="worktrees at a time")
    ap.add_argument("--shards", type=pathlib.Path, default=ROOT / "out/shards")
    ap.add_argument("--keep", action="store_true", help="(the default since 28 Sep 2026; kept for callers)")
    ap.add_argument("--fresh", action="store_true", help="recreate the shards instead of refreshing the kept ones")
    ap.add_argument("--rm", action="store_true", help="remove the shards after the run")
    ap.add_argument("--by-gate", action="store_true",
                    help="one remix: its per-remix half as one job per gate over the shards")
    ap.add_argument("--split", default="auto",
                    help="auto (the default): split the remixes that would set the wall time into gate jobs; "
                         "none; or a comma-separated list")
    a = ap.parse_args(argv)
    remixes = list(dict.fromkeys(a.remixes))
    if not (ROOT / "out/raw/section_3_MAIN_OS.bin").is_file():
        sys.exit("check_shards: out/raw/section_3_MAIN_OS.bin is missing (make os && make recon)")
    if a.by_gate:
        if len(remixes) != 1:
            sys.exit("check_shards: --by-gate takes exactly one remix")
        gate_jobs = remix_jobs(remixes[0], a.shards / "0")
        check_recipe(gate_jobs)
    times_path = ROOT / "out/check_shards/times.json"
    try:
        times = json.loads(times_path.read_text())
    except (OSError, ValueError):
        times = {}
    split = set()
    if not a.by_gate and len(remixes) > 1 and a.jobs > 1:
        split = choose_split(remixes, a.split, times, a.jobs)
    if a.by_gate:
        work = [("gate", remixes[0], j) for j in gate_jobs]
    else:
        work = []
        for r in remixes:
            if r in split:
                gj = remix_jobs(r, a.shards / "0")
                check_recipe(gj)
                work += [("gate", r, j) for j in gj]
            else:
                work.append(("remix", r, None))
        # longest first (the last recorded times; unknown last, in the given order)
        est = lambda w: times.get(w[1] if w[0] == "remix" else f"{w[1]}:{w[2][0]}", -1.0)
        work.sort(key=est, reverse=True)
    jobs = max(1, min(a.jobs, len(work)))
    a.shards.mkdir(parents=True, exist_ok=True)
    logdir = ROOT / "out/check_shards" / (remixes[0] if a.by_gate else "")
    logdir.mkdir(parents=True, exist_ok=True)
    for r in split:
        (ROOT / "out/check_shards" / r).mkdir(parents=True, exist_ok=True)
    shards = [a.shards / str(i) for i in range(jobs)]

    what = (f"{len(work)} gates of {remixes[0]}" if a.by_gate else f"{len(remixes)} remixes"
            + (f" ({', '.join(sorted(split))} split into gate jobs)" if split else ""))
    print(f"check_shards: {what} over {jobs} shards under {a.shards} "
          f"({'refreshing kept shards' if all(shard_ok(s) for s in shards) and not a.fresh else 'setup: worktree + submodules + port build each'})", flush=True)
    t_setup = time.monotonic()
    errors = []

    def setup(i):
        try:
            make_shard(shards[i], a.shards / f"{i}.setup.log", fresh=a.fresh)
        except (SystemExit, subprocess.CalledProcessError, OSError) as exc:
            errors.append(str(exc))
    threads = [threading.Thread(target=setup, args=(i,)) for i in range(jobs)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    if errors:
        sys.exit("check_shards: " + "; ".join(errors))
    print(f"check_shards: shards ready in {time.monotonic() - t_setup:.0f} s", flush=True)

    todo = queue.Queue()
    for w in work:
        todo.put(w)
    results = {}
    lock = threading.Lock()

    def worker(i):
        while True:
            try:
                item = todo.get_nowait()
            except queue.Empty:
                return
            kind, rname, job = item
            if kind == "gate":
                res = run_job(shards[i], rname, job, ROOT / "out/check_shards" / rname)
                remix = job[0] if a.by_gate else f"{rname}:{job[0]}"
            else:
                remix = rname
                res = run_remix(shards[i], remix, logdir)
            res["shard"] = i
            status = "ok" if res["rc"] == 0 else f"FAILED ({res['rc']})"
            with lock:
                results[remix] = res
                print(f"check_shards: {status:12} {res['seconds']:6.0f} s  {remix:20} shard {i}"
                      + (f"  {len(res['skips'])} SKIP" if res["skips"] else ""), flush=True)
    threads = [threading.Thread(target=worker, args=(i,)) for i in range(jobs)]
    t0 = time.monotonic()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    wall = time.monotonic() - t0

    names = [w[2][0] if a.by_gate else (w[1] if w[0] == "remix" else f"{w[1]}:{w[2][0]}") for w in work]
    # the durations for the next run's split and order: every job by its
    # key ("remix" or "remix:gate"), and a split remix's total
    run = {}
    for n, r in results.items():
        key = f"{remixes[0]}:{n}" if a.by_gate else n
        run[key] = r["seconds"]
    for rname in ({remixes[0]} if a.by_gate else split):
        parts = [s for k, s in run.items() if k.startswith(rname + ":")]
        if parts:
            run[rname] = sum(parts)
    times.update({k: round(v, 1) for k, v in run.items()})
    try:
        times_path.write_text(json.dumps(dict(sorted(times.items())), indent=1) + "\n")
    except OSError:
        pass
    print(f"\ncheck_shards: results ({wall:.0f} s wall, {sum(r['seconds'] for r in results.values()):.0f} s of "
          f"{'gate' if a.by_gate else 'remix'} time)")
    for remix in names:
        r = results[remix]
        status = "ok" if r["rc"] == 0 else f"FAILED ({r['rc']})"
        print(f"  {status:12} {r['seconds']:6.0f} s  {remix:20} {r['log'].relative_to(ROOT)}")
        for s in r["skips"]:
            print(f"               {s}")
    if a.rm:
        for s in shards:
            remove_shard(s)
    bad = [r for r in results.values() if r["rc"]]
    unit = "gates" if a.by_gate else ("jobs" if split else "remixes")
    if bad:
        print(f"check_shards: {len(bad)} of {len(results)} {unit} failed")
        return 1
    print(f"check_shards: every {'gate of ' + remixes[0] if a.by_gate else 'remix'} passed"
          + ("" if a.by_gate else " its per-remix half"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
