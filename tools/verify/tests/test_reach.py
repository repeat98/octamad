"""The path classifier, against a fake registry and a fake dependency graph:
no manifests, no firmware."""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import reach

MAKE_BASE = """\
BUILD ?= 79
define need-remix
@test -n "$(REMIX)"
endef
.PHONY: bus
bus: ## the build
\tpython3 tools/build/build_bus.py
verify-shared: ## shared
\tpython3 tools/remix/selftest.py
\tpython3 tools/verify/verify_knob_clicks.py
verify-remix: ## per remix
\tpython3 tools/verify/verify_menu.py
\tpython3 tools/verify/verify_set.py
accept: ## runner
\tpython3 tools/verify/acceptance.py
ci-dsp: ## ci
\tscripts/vendor.sh dsp56300
render: ## a tool
\tpython3 tools/harness/render_reverb.py
"""


def ctx(make_head=MAKE_BASE, make_base=MAKE_BASE):
    deps = {
        "tools/build/build_bus.py": {"tools/remix/schema.py", "tools/build/dsp_modmap.py"},
        "tools/remix/schema.py": set(),
        "tools/build/dsp_modmap.py": set(),
        "tools/remix/selftest.py": {"tools/remix/schema.py", "tools/build/stock_labels.py"},
        "tools/verify/verify_knob_clicks.py": {"tools/harness/send_probe.py"},
        "tools/verify/verify_menu.py": {"tools/remix/schema.py"},
        "tools/verify/verify_set.py": {"tools/hw/ot_project.py", "tools/emu/emu_bringup.py"},
        "tools/verify/verify_character.py": {"tools/harness/send_probe.py"},
        "tools/verify/verify_burn.py": {"tools/harness/rig_render.py"},
        "tools/harness/rig_render.py": {"tools/harness/send_probe.py"},
        "tools/harness/pressure.py": {"tools/harness/rig_render.py"},
        "tools/verify/verify_docs.py": {"tools/remix/index.py"},
        "tools/hw/bcr2000.py": {"tools/remix/schema.py"},
        "tools/harness/render_reverb.py": {"tools/harness/send_probe.py"},
    }
    return reach.Context(
        module_key={"character": "CHARACTER", "miniverb": "MINIVERB", "orphan": "ORPHAN", "send": "SEND"},
        remixes_of={"CHARACTER": ["bamsep26", "usb"], "MINIVERB": ["miniverb"], "ORPHAN": [], "SEND": ["bamsep26", "usb"]},
        gate_owners={"tools/verify/verify_character.py": ["CHARACTER"], "tools/verify/verify_burn.py": ["SEND"]},
        remixes=["bamsep26", "miniverb", "usb"],
        exists=lambda path: path != "modules/gone",
        deps=deps,
        shared_scripts=reach.recipe_scripts(make_head, "verify-shared") | {"tools/verify/verify_docs.py"},
        remix_scripts=reach.recipe_scripts(make_head, "verify-remix"),
        gate_shared={"tools/verify/verify_character.py": True, "tools/verify/verify_burn.py": False},
        make_base=make_base, make_head=make_head)


SHARED_ALL = 'make check-shared REMIXES="bamsep26 miniverb usb"'
REMIX_ALL = ["make check-remix REMIX=bamsep26", "make check-remix REMIX=miniverb", "make check-remix REMIX=usb"]
EVERY = [SHARED_ALL] + REMIX_ALL
ACCEPT_ALL = 'make accept REMIXES="bamsep26 miniverb usb" STRESS_SOURCE=${STRESS_SOURCE}'
# The floor is the cover: bamsep26 carries CHARACTER and SEND, miniverb
# MINIVERB; usb adds nothing bamsep26 has not.
SHARED = 'make check-shared REMIXES="bamsep26 miniverb"'
REMIX = ["make check-remix REMIX=bamsep26", "make check-remix REMIX=miniverb"]
COVER = [SHARED] + REMIX
ACCEPT = 'make accept REMIXES="bamsep26 miniverb" STRESS_SOURCE=${STRESS_SOURCE}'
IDENTITY = "python3 tools/verify/image_identity.py --base ${BASE}"
BUILD = ["make test-acceptance", "scripts/refhash.sh check", IDENTITY, SHARED]


def commands(paths, accept_runs_check=False, c=None):
    return [cmd for _, cmd, _ in reach.plan(reach.classify(paths, c or ctx()), accept_runs_check)]


def note(path, c=None):
    return reach.classify([path], c or ctx())[0][2]


class ModuleAndRemixTests(unittest.TestCase):
    def test_module_reaches_every_remix_that_carries_it(self):
        self.assertEqual(commands(["modules/character/engine.asm"]),
                         ['make check-shared REMIXES="bamsep26 usb"',
                          "make check-remix REMIX=bamsep26", "make check-remix REMIX=usb",
                          'make accept REMIXES="bamsep26 usb" STRESS_SOURCE=${STRESS_SOURCE}'])

    def test_accept_runs_the_checks_of_the_remixes_it_accepts(self):
        self.assertEqual(commands(["modules/character/engine.asm"], accept_runs_check=True),
                         ['make accept REMIXES="bamsep26 usb" STRESS_SOURCE=${STRESS_SOURCE}'])
        cmds = commands(["modules/miniverb/a.asm", "tools/verify/verify_character.py"], accept_runs_check=True)
        self.assertEqual(cmds, ['make check-shared REMIXES="bamsep26 usb"',
                                "make accept REMIX=miniverb STRESS_SOURCE=${STRESS_SOURCE}"])

    def test_submodule_pin_is_the_module(self):
        self.assertEqual(commands(["modules/miniverb/upstream"]),
                         ["make check REMIX=miniverb", "make accept REMIX=miniverb STRESS_SOURCE=${STRESS_SOURCE}"])

    def test_module_no_remix_carries_is_the_selftests_refusal(self):
        self.assertIn("no remix carries", note("modules/orphan/manifest.py"))
        self.assertEqual(commands(["modules/orphan/manifest.py"]), ["python3 tools/remix/selftest.py"])

    def test_removed_module_directory_runs_nothing_and_says_so(self):
        self.assertIn("removed module directory", note("modules/gone/manifest.py"))
        self.assertEqual(commands(["modules/gone/manifest.py"]), [])

    def test_unknown_but_present_module_directory_is_the_floor(self):
        self.assertEqual(commands(["modules/mystery/manifest.py"]), COVER)

    def test_template_runs_nothing(self):
        self.assertEqual(commands(["modules/_template/manifest.py"]), [])

    def test_remix_selection_and_readme(self):
        self.assertEqual(commands(["remixes/miniverb/remix.py"]),
                         ["make check REMIX=miniverb", "make accept REMIX=miniverb STRESS_SOURCE=${STRESS_SOURCE}"])
        self.assertEqual(commands(["remixes/miniverb/README.md"]), ["python3 tools/verify/verify_docs.py"])

    def test_one_remix_stays_make_check(self):
        self.assertEqual(commands(["remixes/miniverb/remix.py"])[0], "make check REMIX=miniverb")

    def test_test_remix_selection_and_readme(self):
        self.assertEqual(commands(["remixes/test/miniverb/remix.py"]),
                         ["make check REMIX=miniverb", "make accept REMIX=miniverb STRESS_SOURCE=${STRESS_SOURCE}"])
        self.assertEqual(commands(["remixes/test/miniverb/README.md"]), ["python3 tools/verify/verify_docs.py"])


class DependencyTests(unittest.TestCase):
    def test_the_build_and_what_it_imports_reach_refhash_identity_and_the_shared_half(self):
        for p in ("tools/build/build_bus.py", "tools/remix/schema.py", "tools/build/dsp_modmap.py", "dsp/probe.asm"):
            self.assertEqual(commands([p]), BUILD, p)
        self.assertIn("the build", note("tools/remix/schema.py"))
        self.assertIn("identity", note("tools/remix/schema.py"))

    def test_a_shared_gate_reaches_the_shared_half_only(self):
        for p in ("tools/verify/verify_knob_clicks.py", "tools/remix/selftest.py", "tools/build/stock_labels.py"):
            self.assertEqual(commands([p]), [SHARED], p)
        self.assertIn("shared half", note("tools/build/stock_labels.py"))

    def test_a_per_remix_gate_reaches_the_covers_per_remix_halves_only(self):
        for p in ("tools/verify/verify_menu.py", "tools/verify/verify_set.py", "tools/hw/ot_project.py", "tools/emu/emu_bringup.py"):
            self.assertEqual(commands([p]), REMIX, p)
        self.assertIn("the cover (2 of 3 remixes)", note("tools/verify/verify_menu.py"))

    def test_a_manifest_gate_reaches_its_owners(self):
        # remix_arg=False: the shared half for the owners' remixes
        self.assertEqual(commands(["tools/verify/verify_character.py"]), ['make check-shared REMIXES="bamsep26 usb"'])
        # remix_arg=True: the owners' full checks
        self.assertEqual(commands(["tools/verify/verify_burn.py"]),
                         ['make check-shared REMIXES="bamsep26 usb"', "make check-remix REMIX=bamsep26", "make check-remix REMIX=usb"])
        self.assertIn("a gate of SEND", note("tools/verify/verify_burn.py"))

    def test_a_harness_file_reaches_what_runs_it(self):
        # send_probe: the knob census (shared), Character's gate (shared), the burn (SEND's remixes), the acceptance machinery via pressure
        cmds = commands(["tools/harness/send_probe.py"])
        self.assertIn("make test-acceptance", cmds)
        self.assertIn(ACCEPT, cmds)
        # rig_render also runs under verify_burn (SEND's gate, bamsep26 + usb): usb's check is not
        # among the cover's accepts, so it stays
        self.assertEqual(commands(["tools/harness/rig_render.py"], accept_runs_check=True),
                         ["make test-acceptance", "make check REMIX=usb", ACCEPT])

    def test_a_file_no_gate_depends_on_reaches_nothing(self):
        for p in ("tools/hw/bcr2000.py", "tools/harness/render_reverb.py", "tools/hw/new_tool.py"):
            self.assertEqual(commands([p]), [], p)
            self.assertEqual(note(p), "no gate depends on it", p)

    def test_the_docs_renderer_reaches_verify_docs_as_a_shared_gate(self):
        self.assertEqual(commands(["tools/remix/index.py"]), [SHARED])

    def test_a_verifier_nothing_runs_is_named(self):
        self.assertEqual(commands(["tools/verify/verify_roll.py"]), [])
        self.assertIn("own make target", note("tools/verify/verify_roll.py"))

    def test_acceptance_machinery_and_classifier(self):
        for p in ("tools/verify/acceptance.py", "tools/harness/pressure.py"):
            self.assertEqual(commands([p]), ["make test-acceptance"] + COVER + [ACCEPT], p)
        self.assertEqual(commands(["tools/verify/reach.py"]), ["make test-acceptance"])
        self.assertEqual(commands(["tools/verify/tests/test_reach.py"]), ["make test-acceptance"])

    def test_toolchain_and_port(self):
        self.assertEqual(commands(["tools/patches/dsp56300.patch"]), ["make ci-dsp"] + COVER)
        self.assertEqual(commands(["tools/emu/ot_emu/machine.h"]), ["make ci-emu", "make emu-cf"] + REMIX)
        self.assertEqual(commands(["scripts/refhash.sh"]), ["scripts/refhash.sh check"])


class MakefileTests(unittest.TestCase):
    def test_unchanged_makefile_reaches_nothing(self):
        self.assertEqual(commands(["Makefile"]), [])
        self.assertIn("no target", note("Makefile"))

    def test_a_new_target_outside_the_check_graph_reaches_nothing(self):
        head = MAKE_BASE + "ghidra: ## import\n\tpython3 tools/ghidra/ot_ghidra.py\n"
        self.assertEqual(commands(["Makefile"], c=ctx(make_head=head)), [])
        self.assertIn("ghidra", note("Makefile", ctx(make_head=head)))

    def test_a_check_target_reaches_identity_the_cover_and_ci(self):
        head = MAKE_BASE.replace("\tpython3 tools/verify/verify_menu.py\n", "\tpython3 tools/verify/verify_menu.py\n\tpython3 tools/verify/verify_usb.py\n")
        self.assertEqual(commands(["Makefile"], c=ctx(make_head=head)), [IDENTITY] + COVER + ["make ci"])

    def test_a_variable_or_define_reaches_identity_and_the_cover(self):
        self.assertEqual(commands(["Makefile"], c=ctx(make_head=MAKE_BASE.replace("BUILD ?= 79", "BUILD ?= 80"))), [IDENTITY] + COVER + ["make ci"])
        self.assertEqual(commands(["Makefile"], c=ctx(make_head=MAKE_BASE.replace('@test -n "$(REMIX)"', "@true"))), [IDENTITY] + COVER + ["make ci"])

    def test_runner_and_ci_targets(self):
        head = MAKE_BASE.replace("\tpython3 tools/verify/acceptance.py\n", "\tpython3 tools/verify/acceptance.py --x\n")
        self.assertEqual(commands(["Makefile"], c=ctx(make_head=head)), ["make test-acceptance"])
        head = MAKE_BASE.replace("\tscripts/vendor.sh dsp56300\n", "\tscripts/vendor.sh dsp56300 mc68k\n")
        self.assertEqual(commands(["Makefile"], c=ctx(make_head=head)), ["make ci"])

    def test_comments_and_phony_are_not_changes(self):
        head = MAKE_BASE.replace("## the build", "## THE build").replace(".PHONY: bus\n", ".PHONY: bus cycles\n# a note\n")
        self.assertEqual(commands(["Makefile"], c=ctx(make_head=head)), [])

    def test_without_a_base_the_makefile_is_the_cover(self):
        self.assertEqual(commands(["Makefile"], c=ctx(make_base=None)), COVER + ["make ci"])


class PlanTests(unittest.TestCase):
    def test_docs_and_ci(self):
        self.assertEqual(commands(["docs/remixer/MODULES.md", "README.md"]), ["python3 tools/verify/verify_docs.py"])
        self.assertEqual(commands([".github/workflows/ci.yml"]), ["make ci"])

    def test_unclassified_reaches_the_cover_and_says_so(self):
        self.assertIn("unclassified: the cover (2 of 3 remixes)", note("mystery.bin"))
        self.assertEqual(commands(["mystery.bin"]), COVER)

    def test_all_makes_the_floor_every_remix(self):
        c = ctx(); c.floor = list(c.remixes)
        self.assertEqual(commands(["mystery.bin"], c=c), EVERY)
        self.assertEqual(note("mystery.bin", c), "unclassified: every remix")

    def test_the_cover_is_the_fewest_remixes_carrying_every_module(self):
        self.assertEqual(ctx().cover(), ["bamsep26", "miniverb"])
        c = ctx()
        c.remixes_of = {"A": ["x", "y"], "B": ["x"], "C": ["z"]}
        self.assertEqual(c.cover(), ["x", "z"])      # y is a subset of x
        c.remixes_of = {"A": ["x", "y"], "B": ["y"], "C": ["z"], "D": ["x"]}
        self.assertEqual(c.cover(), ["x", "y", "z"])  # B only in y, D only in x
        c.remixes_of = {"A": ["x"], "B": []}
        self.assertEqual(c.cover(), ["x"])           # a module no remix carries is not coverable

    def test_order_is_fixed_and_each_command_once(self):
        cmds = commands(["docs/x.md", "modules/character/a.asm", "tools/build/dsp_modmap.py", "modules/character/b.asm", "tools/verify/verify_menu.py"])
        self.assertEqual(cmds[0], "python3 tools/verify/verify_docs.py")
        self.assertEqual(len(cmds), len(set(cmds)))
        shared = [c for c in cmds if c.startswith("make check-shared")]
        self.assertEqual(shared, [SHARED_ALL])        # the cover's and CHARACTER's shared lines, merged
        self.assertLess(cmds.index("scripts/refhash.sh check"), cmds.index(IDENTITY))
        self.assertLess(cmds.index(IDENTITY), cmds.index(SHARED_ALL))
        self.assertLess(cmds.index(SHARED_ALL), cmds.index("make check-remix REMIX=bamsep26"))
        self.assertEqual(cmds.count("make check-remix REMIX=bamsep26"), 1)

    def test_halves_merge_into_one_shared_line(self):
        # a shared gate + a per-remix gate + one module's full check: one check-shared, one check-remix each
        cmds = commands(["tools/verify/verify_knob_clicks.py", "tools/verify/verify_menu.py", "modules/miniverb/a.asm"])
        self.assertEqual(cmds, COVER + ["make accept REMIX=miniverb STRESS_SOURCE=${STRESS_SOURCE}"])

    def test_sharded_collapses_the_check_remix_lines(self):
        items = reach.plan(reach.classify(["tools/verify/verify_menu.py"], ctx()))
        cmds = [c for _, c, _ in reach.sharded(items, 4)]
        self.assertEqual(cmds, ["python3 tools/verify/check_shards.py --jobs 4 bamsep26 miniverb"])
        one = reach.plan(reach.classify(["remixes/miniverb/remix.py"], ctx()))
        self.assertEqual(reach.sharded(one, 4), one)

    def test_remixes_reached(self):
        rows = reach.classify(["modules/character/a.asm", "remixes/miniverb/remix.py"], ctx())
        self.assertEqual(reach.remixes_reached(rows), ["bamsep26", "miniverb", "usb"])
        rows = reach.classify(["tools/verify/verify_knob_clicks.py"], ctx())
        self.assertEqual(reach.remixes_reached(rows), ["bamsep26", "miniverb"])


class GraphTests(unittest.TestCase):
    def test_path_refs_count_runs_and_reads_not_prose(self):
        src = '''
"""tools/harness/prose.py is named in this docstring."""
import subprocess, sys
# tools/harness/comment.py
subprocess.run([sys.executable, "tools/harness/run_me.py", "--x"])
p = ROOT / "tools/hw/read_me.py"
print("see tools/harness/message.py")
sys.exit(f"run tools/harness/exit_msg.py first")
open("scripts/opened.sh")
'''
        self.assertEqual(reach.path_refs(src), {"tools/harness/run_me.py", "tools/hw/read_me.py", "scripts/opened.sh"})

    def test_resolve_import_by_toolpath_rules(self):
        known = {"tools/remix/__init__.py", "tools/remix/schema.py", "tools/harness/send_probe.py", "tools/hw/ot_bank.py"}
        ex = known.__contains__
        self.assertEqual(reach.resolve_import("remix", ["schema"], ex), {"tools/remix/__init__.py", "tools/remix/schema.py"})
        self.assertEqual(reach.resolve_import("remix.schema", ["Module"], ex), {"tools/remix/schema.py"})
        self.assertEqual(reach.resolve_import("send_probe", [], ex), {"tools/harness/send_probe.py"})
        self.assertEqual(reach.resolve_import("hw", ["ot_bank"], ex), {"tools/hw/ot_bank.py"})
        self.assertEqual(reach.resolve_import("json", [], ex), set())

    def test_makefile_targets_and_changes(self):
        t, v, d = reach.makefile_targets(MAKE_BASE)
        self.assertIn("verify-shared", t)
        self.assertEqual(v["BUILD"], "BUILD ?= 79")
        self.assertIn("need-remix", d)
        self.assertEqual(reach.makefile_changes(MAKE_BASE, MAKE_BASE), ([], []))
        self.assertEqual(reach.makefile_changes(MAKE_BASE, MAKE_BASE + "x: y\n\tz\n"), (["x"], []))
        self.assertEqual(reach.recipe_scripts(MAKE_BASE, "verify-remix"), {"tools/verify/verify_menu.py", "tools/verify/verify_set.py"})


if __name__ == "__main__":
    unittest.main()
