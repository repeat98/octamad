"""The pressure pricer's enumeration, on a synthetic module table: no firmware."""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "harness"))
import pressure


def table(send):
    mods = {"INSERT": dict(cycles=10, server=False, on_fx1=False, on_fx2=True),
            "STATION": dict(cycles=100, server=False, on_fx1=True, on_fx2=False)}
    if send:
        mods["SEND"] = dict(cycles=3, server=False, on_fx1=False, on_fx2=False)
    return mods


class LayoutTests(unittest.TestCase):
    def test_remix_without_send_prices_none_at_zero(self):
        lay = pressure.enumerate_layouts(table(send=False), None)
        empty = tuple((None, None) for _ in range(4))
        self.assertNotIn(empty, lay)                   # nothing of ours: not a layout
        one = ((None, None),) * 3 + ((None, "INSERT"),)
        self.assertEqual(lay[one], 10)
        self.assertEqual(pressure.fmt(one), "-+- | -+- | -+- | -+INSERT")
        self.assertEqual(max(lay.values()), 4 * 110)

    def test_remix_with_send_puts_send_on_the_empty_slot(self):
        lay = pressure.enumerate_layouts(table(send=True), None)
        self.assertEqual(min(lay.values()), 4 * 3)
        self.assertEqual(pressure.fallback_of(table(send=True)), "SEND")
        self.assertIsNone(pressure.fallback_of(table(send=False)))


class EnvTests(unittest.TestCase):
    def test_price_modules_exports_the_remix_for_cycle_count(self):
        import os, types
        from unittest.mock import patch
        fake_cc = types.SimpleNamespace(measure=lambda stem: dict(cycles=1, inner=""))
        remix = types.SimpleNamespace(name="probe", fx1=(), modules=())
        with patch.dict(os.environ, {}, clear=True), patch.dict(sys.modules, {"cycle_count": fake_cc}), \
                patch.object(pressure.registry, "modules", return_value={}), \
                patch.object(pressure.registry, "selected", return_value=[]):
            pressure.price_modules(remix)
            self.assertEqual(os.environ.get("REMIX"), "probe")


if __name__ == "__main__":
    unittest.main()
