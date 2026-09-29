"""Pre-boot buffers must not silently overlap a growing linked runtime."""
import pathlib
import sys
import unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[2]))
from remix.platform_build import preboot_layout
class PrebootLayoutTests(unittest.TestCase):
    def setUp(self):
        self.layout=dict(base=0x40a00000,runtime_end=0x40a10000,
                         stage=0x40a10000,stage_end=0x40a18000,ceiling=0x41400000)
        self.entries=[dict(name='A',dst=0x48b00000,rawlen=0x10000,
                           stage=0x48b80000,blob=bytes(0x8000))]
    def test_cached_extents(self):
        self.assertEqual(preboot_layout(self.layout,self.entries)[0]['start'],0x40b00000)
    def test_runtime_growth(self):
        for field in ('runtime_end','stage_end'):
            with self.subTest(field=field), self.assertRaisesRegex(ValueError,'overlaps'):
                preboot_layout(dict(self.layout,**{field:0x40b00001}),self.entries)
    def test_preboot_overlap(self):
        with self.assertRaisesRegex(ValueError,'overlaps'):
            preboot_layout(self.layout,self.entries*2)
    def test_arena_end(self):
        with self.assertRaisesRegex(ValueError,'outside'):
            preboot_layout(dict(self.layout,ceiling=0x40b81000),self.entries)
    def test_empty_preserves_old_layout(self):
        self.assertEqual(preboot_layout({},[]),[])
