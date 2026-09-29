"""check_shards --by-gate: the job list mirrors `make verify-remix`."""
import pathlib
import sys
import unittest

HERE = pathlib.Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[1]))
sys.path.insert(0, str(HERE.parents[2]))
import check_shards  # noqa: E402
from reach import recipe_scripts  # noqa: E402

ROOT = HERE.parents[3]


class ByGate(unittest.TestCase):
    def jobs(self, remix="bottleservice"):
        return check_shards.remix_jobs(remix, ROOT / "out/shards/0")

    def test_every_recipe_script_has_a_job(self):
        jobs = self.jobs()
        check_shards.check_recipe(jobs)          # raises SystemExit on drift
        recipe = recipe_scripts((ROOT / "Makefile").read_text(), "verify-remix")
        named = set().union(*(scripts for _n, _c, _e, scripts in jobs))
        self.assertTrue(recipe <= named, recipe - named)

    def test_drift_is_refused(self):
        jobs = [j for j in self.jobs() if j[0] != "usb"]
        with self.assertRaises(SystemExit) as cm:
            check_shards.check_recipe(jobs)
        self.assertIn("verify_usb.py", str(cm.exception))

    def test_image_stage_stages_its_own_card(self):
        """TEMPO BUS boots the card verify_set stages: its job stages it
        (--stage-only) and runs apart from verify_set's own run."""
        (_n, cmds, _e, _s), = [j for j in self.jobs() if j[0] == "set"]
        self.assertEqual([c[1] for c in cmds], ["tools/verify/verify_set.py"])
        (_n, cmds, _e, _s), = [j for j in self.jobs() if j[0] == "image"]
        self.assertEqual([c[1] for c in cmds], ["tools/verify/verify_set.py", "tools/verify/module_gates.py"])
        self.assertIn("--stage-only", cmds[0])
        self.assertEqual(cmds[1][cmds[1].index("--stage") + 1], "image")

    def test_module_gates_are_one_job_each(self):
        names = [j[0] for j in self.jobs()]
        self.assertIn("gate:verify_scenesp2", names)
        self.assertIn("gate:verify_burn", names)
        self.assertEqual(len(names), len(set(names)))

    def test_every_job_carries_the_remix(self):
        for _n, _c, env, _s in self.jobs():
            self.assertEqual(env["REMIX"], "bottleservice")

    def test_without_a_venv_the_skip_jobs_still_stand_for_their_scripts(self):
        real = check_shards.ROOT
        try:
            check_shards.ROOT = pathlib.Path("/nonexistent-tree")   # no .venv there
            jobs = [j for j in check_shards.remix_jobs("bottleservice", ROOT / "out/shards/0") if j[0] == "labels"]
        finally:
            check_shards.ROOT = real
        self.assertEqual(jobs[0][1][0][0], "echo")
        self.assertEqual(jobs[0][3], {"tools/verify/verify_labels.py"})


if __name__ == "__main__":
    unittest.main()


class Split(unittest.TestCase):
    """Which remixes run as gate jobs (check_shards.choose_split)."""

    def test_none_and_named(self):
        self.assertEqual(check_shards.choose_split(["a", "b"], "none", {}, 3), set())
        self.assertEqual(check_shards.choose_split(["a", "b"], "b,zz", {}, 3), {"b"})

    def test_recorded_times_pick_the_long_pole(self):
        times = {"bottleservice": 780.0, "usb": 140.0, "miniverb": 80.0, "euclid": 130.0}
        self.assertEqual(check_shards.choose_split(list(times), "auto", times, 3), {"bottleservice"})
        # nothing over 300 s: nothing split
        small = {k: 100.0 for k in times}
        self.assertEqual(check_shards.choose_split(list(small), "auto", small, 3), set())

    def test_without_a_record_the_octakit_remixes(self):
        got = check_shards.choose_split(["bottleservice", "usb", "restock"], "auto", {}, 3)
        self.assertEqual(got, {"bottleservice"})
