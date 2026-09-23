#!/usr/bin/env python3
"""Run with: python3 -m unittest tools.harness.test_stock_workloads"""

import tempfile
from pathlib import Path
import unittest

from tools.harness import stock_workloads as sw


class StockWorkloadsTest(unittest.TestCase):
    def test_preserved_pilot_identity(self):
        self.assertEqual(sw.digest(sw.PILOT), sw.PILOT_SHA256)

    def test_bank_configuration_and_source_immutability(self):
        before = sw.source_hashes(sw.SOURCE)
        with tempfile.TemporaryDirectory() as tmp:
            for active in (0, 1, 4, 8):
                project = Path(tmp) / f"case-{active}"
                sw.repitch.build_project(sw.SOURCE, project, 0, 0, 120.0, 64, 127, "flex")
                sw.configure_bank(project, active)
                sw.verify_project(project, active)
                bank = (project / "bank01.work").read_bytes()
                self.assertEqual(sum(bank[0x10:-2]) & 0xFFFF, int.from_bytes(bank[-2:], "big"))
            self.assertEqual(sw.source_hashes(sw.SOURCE), before)

    def test_verifier_rejects_effect_and_trig_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "case"
            sw.repitch.build_project(sw.SOURCE, project, 0, 0, 120.0, 64, 127, "flex")
            sw.configure_bank(project, 1)
            sw.verify_project(project, 1)

            def effect(data):
                data[sw.otp.PART_BASE + sw.otp.FX2_OFF] = 8

            sw.otp._bank_write(project, 1, effect, guard=False)
            with self.assertRaises(AssertionError):
                sw.verify_project(project, 1)

            sw.configure_bank(project, 1)
            def wrong_trig(data):
                data[sw.otp.trac_off(0, 0) + 7] = 0

            sw.otp._bank_write(project, 1, wrong_trig, guard=False)
            with self.assertRaises(AssertionError):
                sw.verify_project(project, 1)


if __name__ == "__main__":
    unittest.main()
