#!/usr/bin/env python3
"""Which gates a change reaches: the diff against main, classified by what
depends on each changed file.

    python3 tools/verify/reach.py [--base origin/main] [--run] [--paths ...]
    make reach [BASE=origin/main] [RUN=1] [KEEP=1] [JOBS=n]

CONTRIBUTING's "every remix the change can reach" was worked out by hand:
a module's remixes from the selections, a build change's refhash, a
verifier's callers. This reads the changed paths (committed and not,
against the merge-base with `--base`) and prints the commands, one line
each, with the paths that put them there; `--run` runs them in order and
stops at the first failure (`--keep-going`: every one, then a table).
There is no default remix. The FLOOR -- what a change to the build, the
port, a shared tool or an unclassified path reaches -- is the COVER: the
fewest remixes that between them carry every module (greedy from the
registry, 9 of 27 on 28 Sep 2026), so every module's gates and every kind
of per-remix gate run at least once. `--all` makes it every remix. A
change to the BUILD adds `image_identity.py`: every remix built from the
base and from this tree, and `--run` then checks the ones whose image
moved (dry mode says so). Together with refhash (the flag matrix of one
layout) that replaces "every remix" for a build change; before 28 Sep
2026 every such change ran all 25-27 remixes' checks.

HOW A PATH IS PLACED (28 Sep 2026; before, by directory):

  modules/<name>/           the remixes carrying the module: make check (both
                            halves) and make accept for each
  remixes/<name>/remix.py   that remix (remixes/test/<name>/remix.py too)
  tools/, scripts/          by DEPENDENCY: the Python imports (`from remix
                            import`, `import send_probe`) and the
                            `tools/x/y.py` path strings in every tools/ file
                            are a graph; a changed file reaches the gates
                            that transitively depend on it --
                              the build (build_bus.py, cycle_count.py, dsp/)
                                -> refhash, identity (then the changed remixes'
                                   checks), the runner tests, check-shared once
                                   for the cover
                              a gate of the SHARED half (the verify-shared
                              recipe: selftest, slots, replaces, docs,
                              label_fmt, the knob census; a manifest gate
                              with remix_arg=False)
                                -> make check-shared once (for the cover) / its owners
                              a gate of the PER-REMIX half (the verify-remix
                              recipe: dirtystate, initregs, dram_boot, labels,
                              modenames, hidden, menu, set, usb)
                                -> make check-remix for the cover
                              a manifest gate with remix_arg=True
                                -> make check for its owners' remixes
                              the acceptance machinery (acceptance.py,
                              module_gates.py, stress_project.py, pressure.py)
                                -> the runner tests, the cover, accept for the cover
                              a file no gate depends on (bcr2000.py, a render
                              tool a `make render*` target runs)
                                -> nothing, and the note says so
                            tools/emu/ (the port) is the cover's per-remix
                            half plus ci-emu and emu-cf; tools/harness/dsp_host,
                            tools/patches, setup.sh, vendor.sh are ci-dsp
                            plus the cover (identity cannot see a toolchain
                            change: both trees build with the same binary)
  Makefile                  by TARGET: the targets whose recipe or
                            prerequisites changed against the base --
                            the check graph (bus, cycles, verify*, check*)
                            reaches identity, the cover and make ci; the
                            runner's targets (accept, reach, check-remixes,
                            test-acceptance) the runner tests; the ci
                            targets make ci; any other target nothing; a
                            changed variable or define, identity + the cover
  docs/, *.md               verify_docs
  .github/                  make ci
  anything else             the cover, named unclassified

It refuses a tree that is not rebased onto the base (the base must be an
ancestor of HEAD): gates run before a rebase are not a result (PR #396).
CI runs the dry form on every pull request so the expected local gates are
in the job log; it has no firmware, so it runs none of them.

Two or more remixes to check are printed as one `make check-shared
REMIXES="..."` (once) and a `make check-remix REMIX=<r>` each; one remix
alone stays `make check`. `make accept` runs both halves itself (the shared
half once for every remix it is given), so with STRESS_SOURCE set a remix
that reaches accept has no separate check line and the accept remixes are
one `make accept REMIXES="..."`; without it the check lines stay and the
accept line is listed as blocked. `--run --jobs N` runs the check-remix
lines through `check_shards.py`, N worktrees at a time.
"""
import argparse
import ast
import json
import os
import pathlib
import re
import subprocess
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401

ROOT = pathlib.Path(__file__).resolve().parents[2]

# One command per gate; the order is the order they run in.
ORDER = ("verify_docs", "selftest", "test-acceptance", "ci-dsp", "ci-emu", "emu-cf", "refhash", "identity", "check-shared", "check", "check-remix", "accept", "ci")

# The build: a change here is every remix, both halves, and refhash proves
# the artifacts identical. dsp/ holds the sources build_bus assembles.
BUILD_ROOTS = ("tools/build/build_bus.py", "tools/build/cycle_count.py")
# The acceptance runner and what it drives: the runner tests, then accept
# for every remix (which runs both halves of every check itself).
ACCEPTANCE = ("tools/verify/acceptance.py", "tools/verify/module_gates.py",
              "tools/harness/stress_project.py", "tools/harness/pressure.py")
CLASSIFIER = ("tools/verify/reach.py",)
# Makefile targets by what a change to them reaches.
MAKE_CHECK = {"bus", "cycles", "verify", "verify-shared", "verify-remix", "check", "check-shared", "check-remix",
              "need-remix", "os", "recon"}
MAKE_RUNNER = {"accept", "test-acceptance", "reach", "check-remixes"}
MAKE_CI = {"ci", "ci-dsp", "ci-emu", "emu-cf", "check-asm"}


def cmd_check(remix):
    return ("check", f"make check REMIX={remix}")


def cmd_check_remix(remix):
    return ("check-remix", f"make check-remix REMIX={remix}")


def cmd_check_shared(remixes):
    return ("check-shared", f'make check-shared REMIXES="{" ".join(sorted(remixes))}"')


def cmd_accept(remix):
    return ("accept", f"make accept REMIX={remix} STRESS_SOURCE=${{STRESS_SOURCE}}")


def accept_remix(command):
    return command.split("REMIX=")[1].split()[0]


def shared_remixes(command):
    return command.split('REMIXES="')[1].split('"')[0].split()


CMD = {
    "verify_docs": ("verify_docs", "python3 tools/verify/verify_docs.py"),
    "selftest": ("selftest", "python3 tools/remix/selftest.py"),
    "test-acceptance": ("test-acceptance", "make test-acceptance"),
    "ci-dsp": ("ci-dsp", "make ci-dsp"),
    "ci-emu": ("ci-emu", "make ci-emu"),
    "emu-cf": ("emu-cf", "make emu-cf"),
    "refhash": ("refhash", "scripts/refhash.sh check"),
    # Names the remixes whose IMAGE the change moved; --run then checks
    # those (dry mode says so). scripts/refhash.sh pins the build FLAGS of
    # one layout, this pins the 27 remixes: together they replace "every
    # remix" for a build change.
    "identity": ("identity", "python3 tools/verify/image_identity.py --base ${BASE}"),
    "ci": ("ci", "make ci"),
}

# ---- the dependency graph over tools/ ------------------------------------

IMPORT = re.compile(r"^\s*(?:from\s+([A-Za-z_][\w.]*)\s+import\s+([\w, ]+)|import\s+([A-Za-z_][\w.]*))", re.M)
PATHREF = re.compile(r"\b((?:tools|scripts|dsp)/[A-Za-z0-9_./-]+\.[A-Za-z0-9]+)\b")
# A path string is a dependency when the code RUNS or READS it: an argument
# of one of these calls (an argv list inside subprocess.run counts), or a
# `ROOT / "tools/x/y.py"`. A path in a comment, a docstring, a message or a
# build-report hint is prose (build_bus.py names render_reverb.py and
# verify_delay.py in hints, and every remix "depended" on both).
RUNS_OR_READS = {"run", "Popen", "check_output", "check_call", "call", "open", "Path", "PurePath",
                 "read_text", "read_bytes", "exists", "is_file", "glob", "rglob", "joinpath", "execv", "execvp"}


def path_refs(text):
    """The repo paths a Python source runs or reads (see RUNS_OR_READS)."""
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return set()
    parents = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node
    out = set()
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
            continue
        refs = PATHREF.findall(node.value)
        if not refs:
            continue
        p = parents.get(node)
        while p is not None and not isinstance(p, ast.stmt):
            if isinstance(p, ast.BinOp) and isinstance(p.op, ast.Div):
                out.update(refs); break
            if isinstance(p, ast.Call):
                f = p.func
                name = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")
                if name in RUNS_OR_READS:
                    out.update(refs); break
            p = parents.get(p)
    return out


def resolve_import(module, names, exists):
    """The repo files an import statement names, by toolpath's rules: the
    `remix` package under tools/, every group directory by bare name."""
    out = set()
    parts = module.split(".")
    base = "tools/" + "/".join(parts)
    if exists(base + ".py"):
        out.add(base + ".py")
    if exists(base + "/__init__.py"):
        out.add(base + "/__init__.py")
    for n in names:                     # `from hw import ot_bank`: tools/hw has no __init__
        if exists(f"{base}/{n}.py"):
            out.add(f"{base}/{n}.py")
    if len(parts) == 1:
        for g in ("build", "harness", "emu", "hw", "verify"):
            if exists(f"tools/{g}/{module}.py"):
                out.add(f"tools/{g}/{module}.py")
    return out


def scan_deps(root=ROOT):
    """{file: set(files it imports or names by path)} over tools/**/*.py and
    scripts/*.sh; a submodule's files are not ours."""
    files = [p for p in root.glob("tools/**/*.py") if "upstream" not in p.parts]
    files += list(root.glob("scripts/*.sh"))
    rel = lambda p: p.relative_to(root).as_posix()
    known = {rel(p) for p in files}
    exists = lambda path: path in known or (root / path).is_file()
    deps = {}
    for p in files:
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        d = set()
        if p.suffix == ".py":
            for m in IMPORT.finditer(text):
                if m.group(1):
                    d |= resolve_import(m.group(1), [n.strip().split(" as ")[0] for n in m.group(2).split(",")], exists)
                else:
                    d |= resolve_import(m.group(3), [], exists)
        refs = path_refs(text) if p.suffix == ".py" else {
            r for line in text.splitlines() if not line.lstrip().startswith("#") for r in PATHREF.findall(line)}
        for ref in refs:
            if exists(ref):
                d.add(ref)
        d.discard(rel(p))
        deps[rel(p)] = d
    return deps


def makefile_targets(text):
    """{target: its prerequisites + recipe text}, {variable: its line},
    {define: its body} from a Makefile's text; comments, blanks and .PHONY
    lines are not a change."""
    targets, variables, defines = {}, {}, {}
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        m = re.match(r"^define\s+(\S+)", line)
        if m:
            body = []
            i += 1
            while i < len(lines) and not lines[i].startswith("endef"):
                body.append(lines[i]); i += 1
            defines[m.group(1)] = "\n".join(body)
            i += 1
            continue
        m = re.match(r"^([A-Za-z_][\w-]*)\s*[?:+]?=(.*)$", line)
        if m:
            variables[m.group(1)] = line.strip()
            i += 1
            continue
        m = re.match(r"^([A-Za-z0-9_.-]+):(?!=)(.*)$", line)
        if m and not line.startswith((".PHONY", "\t")):
            recipe = [m.group(2).split("##")[0].strip()]
            i += 1
            while i < len(lines) and lines[i].startswith("\t"):
                recipe.append(lines[i].strip()); i += 1
            targets[m.group(1)] = "\n".join(recipe)
            continue
        i += 1
    return targets, variables, defines


def makefile_changes(base_text, head_text):
    """(changed targets, changed variables or defines) between two Makefiles."""
    bt, bv, bd = makefile_targets(base_text or "")
    ht, hv, hd = makefile_targets(head_text or "")
    targets = sorted(k for k in set(bt) | set(ht) if bt.get(k) != ht.get(k))
    other = sorted(k for k in set(bv) | set(hv) if bv.get(k) != hv.get(k))
    other += sorted(k for k in set(bd) | set(hd) if bd.get(k) != hd.get(k))
    return targets, other


def recipe_scripts(make_text, target):
    m = re.search(r"^%s:[^\n]*\n((?:\t[^\n]*\n)+)" % re.escape(target), make_text, re.M)
    return set(re.findall(r"tools/\S+\.py", m.group(1))) if m else set()


class Context:
    """What the classifier needs from the registry and the tree, so tests
    can fake it."""

    def __init__(self, module_key, remixes_of, gate_owners, remixes, exists=None, deps=None,
                 shared_scripts=(), remix_scripts=(), gate_shared=None, make_base=None, make_head=None,
                 all_remixes=False):
        self.module_key = module_key        # module directory -> key
        self.remixes_of = remixes_of        # key -> sorted remix names carrying it
        self.gate_owners = gate_owners      # verifier path -> keys whose manifests name it
        self.remixes = remixes              # every remix
        # The floor, since nothing is the default remix: every remix with
        # --all, else the cover -- the fewest remixes that between them carry
        # every module, so every module's gates and every kind of per-remix
        # gate run at least once (28 Sep 2026; 9 of 27 that day).
        self.floor = list(remixes) if all_remixes else self.cover()
        self.exists = exists or (lambda path: (ROOT / path).exists())
        self.deps = deps or {}              # file -> files it depends on
        self.shared_scripts = set(shared_scripts) - set(ACCEPTANCE)   # the verify-shared recipe's
        self.remix_scripts = set(remix_scripts) - set(ACCEPTANCE)     # the verify-remix recipe's
        self.gate_shared = gate_shared or {}   # manifest gate script -> True when remix_arg=False
        self.make_base, self.make_head = make_base, make_head
        self._dependents = None

    def cover(self):
        """Greedy set cover of the modules by the remixes: the remix adding
        the most uncovered modules first (ties by name), until every module
        some remix carries is covered."""
        modules_of = {}
        for key, names in self.remixes_of.items():
            for n in names:
                modules_of.setdefault(n, set()).add(key)
        left = set().union(*modules_of.values()) if modules_of else set()
        picked = []
        while left:
            name = min(modules_of, key=lambda n: (-len(modules_of[n] & left), n))
            if not modules_of[name] & left:
                break
            picked.append(name)
            left -= modules_of[name]
        return sorted(picked)

    def floor_note(self):
        return ("every remix" if len(self.floor) == len(self.remixes)
                else f"the cover ({len(self.floor)} of {len(self.remixes)} remixes)")

    def every(self):
        """The floor, both halves (plan() folds these into one check-shared
        and a check-remix each)."""
        return [cmd_check(r) for r in self.floor]

    def every_remix(self):
        return [cmd_check_remix(r) for r in self.floor]

    def build_change(self):
        """A change to the build: refhash (the flag matrix), identity (the
        remixes whose image moved, checked by --run), the shared half once
        for the floor."""
        return [CMD["refhash"], CMD["identity"], CMD["test-acceptance"], cmd_check_shared(self.floor)]

    def dependents(self, path):
        """Every file that depends on `path`, transitively."""
        if self._dependents is None:
            rev = {}
            for f, ds in self.deps.items():
                for d in ds:
                    rev.setdefault(d, set()).add(f)
            self._dependents = rev
        seen, todo = set(), [path]
        while todo:
            p = todo.pop()
            for f in self._dependents.get(p, ()):
                if f not in seen:
                    seen.add(f); todo.append(f)
        return seen

    @classmethod
    def from_registry(cls, base=None, all_remixes=False):
        from remix import registry
        mods = registry.modules()
        module_key = {m.name: m.key for m in mods.values()}
        remixes_of = {k: [] for k in mods}
        for name in registry.remix_names():
            for k in registry.remix(name).modules:
                remixes_of.setdefault(k, []).append(name)
        gate_owners, gate_shared = {}, {}
        for m in mods.values():
            for g in getattr(m, "gates", ()):
                gate_owners.setdefault(g.script, []).append(m.key)
                gate_shared[g.script] = gate_shared.get(g.script, True) and not g.remix_arg
        make_head = (ROOT / "Makefile").read_text()
        make_base = None
        if base:
            r = subprocess.run(["git", "show", f"{base}:Makefile"], cwd=ROOT, capture_output=True, text=True)
            make_base = r.stdout if r.returncode == 0 else None
        return cls(module_key, {k: sorted(v) for k, v in remixes_of.items()}, gate_owners,
                   registry.remix_names(), deps=scan_deps(),
                   shared_scripts=recipe_scripts(make_head, "verify-shared"),
                   remix_scripts=recipe_scripts(make_head, "verify-remix"),
                   gate_shared=gate_shared, make_base=make_base, make_head=make_head,
                   all_remixes=all_remixes)


def route_tool(path, ctx):
    """A tools/ or scripts/ file: the gates that depend on it."""
    if path.startswith("dsp/") or path in BUILD_ROOTS:
        return ctx.build_change(), f"the build: refhash the flag matrix, identity the remixes whose image moved (their checks follow), the shared half once for {ctx.floor_note()}"
    if path in CLASSIFIER or path.startswith("tools/verify/tests/"):
        return [CMD["test-acceptance"]], "the classifier and its tests: their own tests are the gate"
    if path in ACCEPTANCE:
        return [CMD["test-acceptance"]] + ctx.every() + [cmd_accept(r) for r in ctx.floor], f"the acceptance machinery: {ctx.floor_note()}"
    if path.startswith("tools/emu/ot_emu/"):
        return [CMD["ci-emu"], CMD["emu-cf"]] + ctx.every_remix(), f"the ColdFire port: the per-remix half of {ctx.floor_note()} (the set gates need OT_PROJECT)"
    if path.startswith(("tools/harness/dsp_host/", "tools/patches/")) or path in ("scripts/setup.sh", "scripts/vendor.sh"):
        return [CMD["ci-dsp"]] + ctx.every(), f"the DSP toolchain: rebuild it first (scripts/setup.sh; a dsp_host change in an isolated tree, AGENTS.md); {ctx.floor_note()}"
    if path == "scripts/refhash.sh":
        return [CMD["refhash"]], ""
    users = ctx.dependents(path) | {path}
    gates, notes = [], []
    if users & set(BUILD_ROOTS):
        return ctx.build_change(), f"the build depends on it: refhash, identity (the remixes whose image moved are checked), the shared half once for {ctx.floor_note()}"
    if users & set(ACCEPTANCE):
        gates += [CMD["test-acceptance"]] + ctx.every() + [cmd_accept(r) for r in ctx.floor]
        notes.append(f"the acceptance machinery depends on it: {ctx.floor_note()}")
    if users & set(CLASSIFIER):
        gates.append(CMD["test-acceptance"])
    if users & ctx.shared_scripts:
        # once; REMIXES only picks the module union for the isolated gates,
        # and the floor's union is every module
        gates.append(cmd_check_shared(ctx.floor))
        notes.append("a gate of the shared half: " + ", ".join(sorted(pathlib.PurePosixPath(u).stem for u in users & ctx.shared_scripts)))
    if users & ctx.remix_scripts:
        gates += ctx.every_remix()
        notes.append(f"a gate of the per-remix half, run for {ctx.floor_note()}: " + ", ".join(sorted(pathlib.PurePosixPath(u).stem for u in users & ctx.remix_scripts)))
    for script in sorted(users & set(ctx.gate_owners)):
        owners = ctx.gate_owners[script]
        remixes = sorted({r for k in owners for r in ctx.remixes_of.get(k, [])})
        if not remixes:
            continue
        if ctx.gate_shared.get(script):
            gates.append(cmd_check_shared(remixes))
        else:
            gates += [cmd_check(r) for r in remixes]
        notes.append(f"{pathlib.PurePosixPath(script).stem}, a gate of " + ", ".join(owners))
    if path.startswith("tools/verify/") and not gates and path.startswith("tools/verify/verify_"):
        notes.append("a verifier no recipe or manifest runs (its own make target)")
    if not gates and not notes:
        notes.append("no gate depends on it")
    return gates, "; ".join(notes)


def route_makefile(ctx):
    if ctx.make_base is None:
        return ctx.every() + [CMD["ci"]], f"the Makefile (no base to diff against): {ctx.floor_note()}"
    targets, other = makefile_changes(ctx.make_base, ctx.make_head)
    gates, notes = [], []
    # A variable or a check target can change what the build writes (a
    # flag default) or how a gate runs: identity names the moved images,
    # the floor runs the gates.
    if other:
        gates += [CMD["identity"]] + ctx.every() + [CMD["ci"]]
        notes.append("variables or defines changed: " + ", ".join(other) + f": identity + {ctx.floor_note()}")
    check = [t for t in targets if t in MAKE_CHECK]
    if check:
        gates += [CMD["identity"]] + ctx.every() + [CMD["ci"]]
        notes.append("the check graph: " + ", ".join(check) + f": identity + {ctx.floor_note()}")
    runner = [t for t in targets if t in MAKE_RUNNER]
    if runner:
        gates.append(CMD["test-acceptance"])
        notes.append("the runner's targets: " + ", ".join(runner))
    ci = [t for t in targets if t in MAKE_CI]
    if ci:
        gates.append(CMD["ci"])
        notes.append("ci targets: " + ", ".join(ci))
    rest = [t for t in targets if t not in MAKE_CHECK | MAKE_RUNNER | MAKE_CI]
    if rest:
        notes.append("targets outside the check graph: " + ", ".join(rest) + ": no gate")
    if not targets and not other:
        notes.append("no target, variable or define changed")
    return gates, "; ".join(notes)


def classify(paths, ctx):
    """[(path, [(kind, command), ...], note)] for each changed path."""
    out = []
    for path in paths:
        parts = pathlib.PurePosixPath(path).parts
        gates, note = [], ""
        top = parts[0] if parts else ""
        if top == "modules" and len(parts) >= 2:
            d = parts[1]
            if d.startswith("_"):
                note = "template: skipped by the registry"
            elif d in ctx.module_key:
                key = ctx.module_key[d]
                remixes = ctx.remixes_of.get(key, [])
                if remixes:
                    gates = [cmd_check(r) for r in remixes] + [cmd_accept(r) for r in remixes]
                    note = f"{key} -> " + ", ".join(remixes)
                else:
                    note = f"{key}: no remix carries it (the selftest refuses this)"
                    gates = [CMD["selftest"]]
            elif not ctx.exists(f"modules/{d}"):
                # A removed (or renamed) module: the registry no longer knows
                # it, and the remixes that carried it changed their remix.py
                # in the same diff (the selftest refuses an unknown module),
                # which routes their checks. Nothing more to run for the
                # directory itself.
                note = "removed module directory: its remixes' selections are in the diff"
            else:
                note = "unknown module directory"
                gates = ctx.every()
        elif top == "remixes" and len(parts) >= 2:
            # remixes/<name>/..., remixes/test/<name>/..., or a flat remixes/<name>.py
            name = parts[2] if parts[1] == "test" and len(parts) >= 3 else parts[1]
            name = name[:-3] if name.endswith(".py") else name
            if parts[-1] == "README.md":
                gates = [CMD["verify_docs"]]
            else:
                gates = [cmd_check(name), cmd_accept(name)]
        elif top in ("tools", "scripts", "dsp"):
            gates, note = route_tool(path, ctx)
        elif path == "Makefile":
            gates, note = route_makefile(ctx)
        elif path.startswith(".github/"):
            gates = [CMD["ci"]]
        elif path.endswith(".md") or path.startswith("docs/"):
            gates = [CMD["verify_docs"]]
        elif path in ("pyproject.toml", "uv.lock", "LICENSE", ".gitignore", ".gitmodules"):
            gates = ctx.every()
        else:
            gates = ctx.every()
            note = f"unclassified: {ctx.floor_note()}"
        out.append((path, gates, note))
    return out


def plan(rows, accept_runs_check=True):
    """The commands in run order, each once, with the paths that put it
    there. Two or more remixes to check become ONE `make check-shared`
    (the remix-independent gates, once) and a `make check-remix` each; a
    single full check alone stays `make check`. Two or more remixes to
    accept become ONE `make accept REMIXES="..."` (the runner runs the
    shared half once), and with `accept_runs_check` (STRESS_SOURCE is set,
    so the accept line will run) a remix that is accepted is not checked
    separately: accept runs both halves of its check itself."""
    by_cmd = {}
    for path, gates, _ in rows:
        for kind, command in gates:
            by_cmd.setdefault((kind, command), []).append(path)
    accepts = {k: v for k, v in by_cmd.items() if k[0] == "accept"}
    accepted = []
    if accepts:
        accepted = sorted(accept_remix(c) for _, c in accepts)
        paths = sorted({p for v in accepts.values() for p in v})
        for k in accepts:
            del by_cmd[k]
        if len(accepted) > 1:
            by_cmd[("accept", f'make accept REMIXES="{" ".join(accepted)}" STRESS_SOURCE=${{STRESS_SOURCE}}')] = paths
        else:
            by_cmd[cmd_accept(accepted[0])] = paths
        if accept_runs_check:
            for k in [k for k in by_cmd if k[0] in ("check", "check-remix") and accept_remix(k[1]) in accepted]:
                del by_cmd[k]
    checks = {k: v for k, v in by_cmd.items() if k[0] == "check"}
    halves = [k for k in by_cmd if k[0] in ("check-shared", "check-remix")]
    if len(checks) > 1 or (checks and halves):
        # full checks beside other halves: every full check is its two halves
        for (k, c), v in checks.items():
            del by_cmd[(k, c)]
            r = accept_remix(c)
            by_cmd.setdefault(cmd_check_shared([r]), []).extend(v)
            by_cmd.setdefault(cmd_check_remix(r), []).extend(v)
    shared = {k: v for k, v in by_cmd.items() if k[0] == "check-shared"}
    if len(shared) > 1:
        names = sorted({r for _, c in shared for r in shared_remixes(c)})
        paths = sorted({p for v in shared.values() for p in v})
        for k in shared:
            del by_cmd[k]
        by_cmd[cmd_check_shared(names)] = paths
    keyed = sorted(by_cmd.items(), key=lambda kv: (ORDER.index(kv[0][0]), kv[0][1]))
    return [(kind, command, sorted(set(paths))) for (kind, command), paths in keyed]


def remixes_reached(rows):
    out = set()
    for _, gates, _ in rows:
        for kind, command in gates:
            if kind in ("check", "check-remix"):
                out.add(accept_remix(command))
            elif kind == "check-shared":
                out |= set(shared_remixes(command))
    return sorted(out)


def sharded(items, jobs):
    """The check-remix lines as one `check_shards.py --jobs N` line, in
    the first one's place: each remix's half in its own worktree, N at a
    time (the halves all write out/mainos_bus.bin, so one tree runs one)."""
    remixes = [c.split("REMIX=")[1] for k, c, _ in items if k == "check-remix"]
    if len(remixes) < 2:
        return items
    out, done = [], False
    for kind, command, paths in items:
        if kind != "check-remix":
            out.append((kind, command, paths))
        elif not done:
            all_paths = sorted({p for k, _, ps in items if k == "check-remix" for p in ps})
            out.append(("check-remix", f"python3 tools/verify/check_shards.py --jobs {jobs} " + " ".join(remixes), all_paths))
            done = True
    return out


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)


def changed_paths(base):
    mb = git("merge-base", base, "HEAD")
    if mb.returncode:
        sys.exit(f"reach: no merge-base with {base}: {mb.stderr.strip()} (git fetch origin?)")
    merge_base = mb.stdout.strip()
    if git("merge-base", "--is-ancestor", base, "HEAD").returncode:
        sys.exit(f"reach: {base} is not an ancestor of HEAD -- rebase first; gates run "
                 f"before the rebase are not a result (CONTRIBUTING.md)")
    diff = git("diff", "--name-only", merge_base).stdout.split()
    untracked = git("ls-files", "--others", "--exclude-standard").stdout.split()
    return merge_base, sorted(set(diff) | set(untracked))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", default="origin/main")
    ap.add_argument("--paths", nargs="*", help="classify these paths instead of the diff")
    ap.add_argument("--run", action="store_true", help="run the commands, in order, stopping at the first failure")
    ap.add_argument("--keep-going", action="store_true", help="with --run: run every command, then one table")
    ap.add_argument("--jobs", type=int, default=1,
                    help="with --run: the check-remix lines through check_shards.py, N worktrees at a time")
    ap.add_argument("--all", action="store_true",
                    help="the floor is every remix instead of the cover (the remixes that between them carry every module)")
    a = ap.parse_args(argv)
    if a.paths is not None:
        merge_base, paths = None, sorted(set(a.paths))
    else:
        merge_base, paths = changed_paths(a.base)
    ctx = Context.from_registry(base=merge_base or a.base, all_remixes=a.all)
    rows = classify(paths, ctx)
    if merge_base:
        print(f"reach: {len(paths)} changed path{'s' if len(paths) != 1 else ''} against {a.base} ({merge_base[:10]})")
    for path, _, note in rows:
        print(f"  {path}" + (f"   [{note}]" if note else ""))
    if not rows:
        print("  (nothing changed)")
        return 0
    print("\nremixes reached: " + (", ".join(remixes_reached(rows)) or "none"))
    print("\ngates, in order:")
    stress = os.environ.get("STRESS_SOURCE")
    items = plan(rows, accept_runs_check=bool(stress))
    if a.jobs > 1:
        items = sharded(items, a.jobs)
    for kind, command, from_paths in items:
        why = from_paths[0] + (f" +{len(from_paths) - 1}" if len(from_paths) > 1 else "")
        print(f"  {command:56}  # {why}")
    if not items:
        print("  (none: no gate depends on what changed)")
    if any(k == "identity" for k, _, _ in items):
        print(f"  then: make check REMIX=<r> for each remix image_identity names (--run does this; the floor is {ctx.floor_note()})")
    if any(k == "accept" for k, _, _ in items) and not stress:
        print("\nSTRESS_SOURCE is unset: point it at a local project (never committed) for the accept line"
              " (it then runs the accepted remixes' checks itself).")
    if not a.run:
        return 0
    print()
    results = []
    queue = list(items)
    while queue:
        kind, command, _ = queue.pop(0)
        cmd = command.replace("${STRESS_SOURCE}", stress or "").replace("${BASE}", a.base)
        if kind == "accept" and not stress:
            print(f"reach: BLOCKED {command}: STRESS_SOURCE is unset")
            if not a.keep_going:
                return 2
            results.append((command, "BLOCKED", 0.0))
            continue
        print(f"reach: running {cmd}", flush=True)
        t0 = time.monotonic()
        r = subprocess.run(cmd, shell=True, cwd=ROOT)
        results.append((command, "ok" if r.returncode == 0 else f"FAILED ({r.returncode})", time.monotonic() - t0))
        if r.returncode:
            print(f"reach: FAILED ({r.returncode}) {cmd}")
            if not a.keep_going:
                return 1
        elif kind == "identity":
            # The remixes whose image moved: their full check (and accept,
            # with STRESS_SOURCE) join the queue in the floor's place.
            changed = json.loads((ROOT / "out/identity/changed.json").read_text())
            extra = [cmd_check(r) for r in changed] + ([cmd_accept(r) for r in changed] if stress else [])
            already = {c for _, c, _ in queue} | {c for c, _, _ in results}
            extra = [(k, c, ["image_identity"]) for k, c in extra if c not in already]
            print(f"reach: identity names {len(changed)} changed remix{'es' if len(changed) != 1 else ''}"
                  + (": " + ", ".join(changed) if changed else "") + f" -> {len(extra)} more gate{'s' if len(extra) != 1 else ''}")
            queue = sorted(queue + extra, key=lambda it: (ORDER.index(it[0]), it[1]))
    if a.keep_going:
        print("\nreach: results")
        for command, status, seconds in results:
            print(f"  {status:12} {seconds:7.0f} s  {command}")
    bad = [r for r in results if r[1] != "ok"]
    if bad:
        print(f"reach: {len(bad)} of {len(results)} gates did not pass")
        return 2 if all(r[1] == "BLOCKED" for r in bad) else 1
    print("reach: every gate passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
