"""Small accounting tests; no firmware or third-party dependencies required."""
from pathlib import Path
import tempfile
import unittest

from profile_stock import distribution, read_counts, windows, detailed


class ProfileTests(unittest.TestCase):
    def test_nearest_rank_percentiles(self):
        self.assertEqual(distribution(range(1,101)),
                         dict(n=100,mean=50.5,p95=95,p99=99,maximum=100))
        with self.assertRaises(ValueError): distribution([])

    def test_windows_are_nonoverlapping(self):
        self.assertEqual(windows({0x100:2,0x1ff:3,0x200:4}),[(0x100,5),(0x200,4)])

    def test_bad_pc_tables(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"pcs"
            for text in ("1 2\n1 3\n", "1 -1\n", "100000000 1\n", "oops\n"):
                path.write_text(text)
                with self.assertRaises(ValueError): read_counts(path)

    def test_frame_accounting_rejects_incomplete_or_mismatched(self):
        with tempfile.TemporaryDirectory() as directory:
            prefix=Path(directory)/"profile"
            path=Path(str(prefix)+".frames.tsv")
            path.write_text("frame cpu dsp0 dsp1 skipped0 skipped1 complete\n"
                            "0 1 0 0 0 0 0\n1 10 0 0 0 0 1\n2 2 0 0 0 0 0\n")
            with self.assertRaisesRegex(ValueError,"CPU frame/PC"):
                detailed(prefix,{0:12},b"",2)
            with self.assertRaisesRegex(ValueError,"does not cover"):
                detailed(prefix,{0:13},b"",3)


if __name__ == "__main__": unittest.main()
