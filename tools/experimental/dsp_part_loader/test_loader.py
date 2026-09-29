"""No firmware required: package validation and adversarial transition tests."""
from dataclasses import replace
import random
import unittest
from .package import Package, Relocation, Section
from .planner import Budget, Instance, Planner, Pool, Refused


def package(name='a', words=16, cycles=10, state=8):
    return Package(name, (Section('P', (0,) * words),), (), 0, 1,
                   state, cycles, 'synthetic test bound', '0' * 64)


def budget(p=128, x=256, cycles=200):
    return Budget((Pool('P', 0x1000, p), Pool('X', 0x4000, x), Pool('Y', 0x1000, 128)), cycles)


def activate(planner, instances):
    plan = planner.prepare(instances)
    for core in plan.required_cores:
        planner.acknowledge(plan, core)
    planner.commit(plan)
    planner.finish_transition()
    return plan


class PackageTests(unittest.TestCase):
    def test_roundtrip_and_cross_space_relocations(self):
        p = replace(package(), sections=(Section('P', (0, 1)), Section('X', (7, 8))),
                    relocations=(Relocation('P', 0, 'P', 0), Relocation('P', 1, 'X', 1)))
        self.assertEqual(Package.from_json(p.to_json()), p)
        self.assertEqual(p.relocate({'P': 4096, 'X': 8192})['P'], (4096, 8193))
        self.assertNotEqual(p.identity, replace(p, name='other').identity)

    def test_reject_malformed_packages(self):
        p = package()
        for changes in ({'version': 2}, {'abi': 'bus'}, {'init': 99}, {'state_words': 133},
                        {'cycles_per_block': -1}, {'cycles_per_block': float('nan')},
                        {'cycles_per_block': True}, {'init': 1.5}, {'source_hash': 'invalid'},
                        {'relocations': (Relocation('P', 0, 'Y', 0),)},
                        {'relocations': (Relocation('P', 0, 'P', 16),)},
                        {'relocations': (Relocation('P', 0, 'P', 1),)},
                        {'relocations': (Relocation('P', 0, 'P', 0),) * 2}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(p, **changes)
        with self.assertRaises(ValueError):
            Section('P', (1 << 24,))
        with self.assertRaises(ValueError):
            Section('P', (0,), 3)
        with self.assertRaises(ValueError):
            p.relocate({'P': 0xffffff})
        with self.assertRaises(ValueError):
            replace(p, sections=(Section('P', (0, 0), 8),)).relocate({'P': 1})


class PlannerTests(unittest.TestCase):
    def setUp(self):
        self.a, self.b = package(), package('b')
        self.p = Planner((self.a, self.b), (budget(), budget()))

    def test_eight_tracks_share_code_per_core_not_state(self):
        instances = tuple(Instance(t, 'fx1', self.a.identity) for t in range(1, 9))
        plan = activate(self.p, instances)
        self.assertEqual(plan.steady_cycles, (40, 40))
        self.assertEqual(len([a for a in plan.allocations if a.space == 'P']), 2)
        states = [a for a in plan.allocations if a.owner[0] == 'state']
        self.assertEqual(len(states), 8)
        self.assertEqual(Instance(1, 'fx1', self.a.identity).core, 1)
        self.assertEqual(Instance(5, 'fx1', self.a.identity).core, 0)
        no_change = self.p.prepare(instances)
        self.assertEqual(no_change.staged, ())
        self.assertEqual(no_change.transition_cycles, (40, 40))

    def test_transaction_readiness_cancel_and_stale(self):
        old = (self.p.instances, self.p.allocations, self.p.generation)
        plan = self.p.prepare((Instance(1, 'fx1', self.a.identity), Instance(5, 'fx1', self.a.identity)))
        self.assertEqual(old, (self.p.instances, self.p.allocations, self.p.generation))
        self.p.acknowledge(plan, 0)
        with self.assertRaises(Refused) as cm:
            self.p.commit(plan)
        self.assertEqual(cm.exception.code, 'not_ready')
        self.assertEqual(old, (self.p.instances, self.p.allocations, self.p.generation))
        self.p.cancel(plan)
        with self.assertRaises(Refused):
            self.p.acknowledge(plan, 1)
        new = self.p.prepare(plan.instances)
        with self.assertRaises(Refused):
            self.p.commit(plan)
        for c in new.required_cores:
            self.p.acknowledge(new, c)
        self.p.commit(new)
        with self.assertRaises(Refused):
            self.p.prepare(())
        self.p.finish_transition()

    def test_outgoing_allocations_retire_only_after_fade(self):
        activate(self.p, (Instance(1, 'fx1', self.a.identity),))
        old = self.p.allocations
        plan = self.p.prepare((Instance(1, 'fx1', self.b.identity),))
        for new in plan.staged:
            for a in old:
                if (new.core, new.space) == (a.core, a.space):
                    self.assertTrue(new.base + new.words <= a.base or a.base + a.words <= new.base)
        self.p.acknowledge(plan, 1)
        self.p.commit(plan)
        self.assertTrue(set(old) <= set(self.p.allocations))
        self.p.finish_transition()
        self.assertFalse(set(old) & set(self.p.allocations))

    def test_memory_vs_transition_failure_leave_old_part(self):
        p = Planner((self.a, self.b), (budget(p=16), budget(p=16)))
        activate(p, (Instance(1, 'fx1', self.a.identity),))
        old = (p.instances, p.allocations, p.generation)
        for target, code in [((Instance(1, 'fx1', self.b.identity),), 'transition'),
                             ((Instance(1, 'fx1', self.a.identity), Instance(2, 'fx1', self.b.identity)), 'memory')]:
            with self.assertRaises(Refused) as cm:
                p.prepare(target)
            self.assertEqual(cm.exception.code, code)
            self.assertEqual(old, (p.instances, p.allocations, p.generation))

    def test_cycles_are_per_instance_and_include_overlap(self):
        p = Planner((self.a, self.b), (budget(cycles=15), budget(cycles=15)))
        activate(p, (Instance(1, 'fx1', self.a.identity),))
        with self.assertRaises(Refused) as cm:
            p.prepare((Instance(1, 'fx1', self.b.identity),))
        self.assertEqual(cm.exception.code, 'transition_cycles')
        with self.assertRaises(Refused) as cm:
            p.prepare((Instance(1, 'fx1', self.a.identity), Instance(2, 'fx1', self.a.identity)))
        self.assertEqual(cm.exception.code, 'cycles')

    def test_unknown_unmeasured_wrong_slot_and_duplicate(self):
        unknown = replace(self.a, cycles_per_block=None, slots=('fx1',))
        p = Planner((unknown,), (budget(), budget()))
        for i in (Instance(1, 'fx1', 'missing'), Instance(1, 'fx1', unknown.identity),
                  Instance(1, 'fx2', unknown.identity)):
            with self.assertRaises(Refused) as cm:
                p.prepare((i,))
            self.assertEqual(cm.exception.code, 'unsupported')
        i = Instance(1, 'fx1', self.a.identity)
        with self.assertRaises(ValueError):
            self.p.prepare((i, i))
        with self.assertRaises(ValueError):
            Pool('P', 0x30000, 32)

    def test_reset_requires_new_state_but_keeps_code(self):
        activate(self.p, (Instance(1, 'fx1', self.a.identity),))
        plan = self.p.prepare((Instance(1, 'fx1', self.a.identity, 'reset'),))
        self.assertEqual([a.owner[0] for a in plan.staged], ['state'])
        self.assertEqual(plan.transition_cycles[1], 20)

    def test_state_memory_and_alignment_are_real_costs(self):
        aligned = replace(self.a, sections=(Section('P', (0,) * 16, 16),))
        tiny = Budget((Pool('P', 0x1001, 30), Pool('X', 0x4000, 128),
                       Pool('Y', 0x1000, 128)), 200)
        p = Planner((aligned,), (tiny, tiny))
        with self.assertRaises(Refused) as cm:
            p.prepare((Instance(5, 'fx1', aligned.identity),))
        self.assertEqual(cm.exception.code, 'memory')
        p = Planner((self.a,), (budget(x=16), budget(x=16)))
        activate(p, (Instance(1, 'fx1', self.a.identity),))
        with self.assertRaises(Refused) as cm:
            p.prepare((Instance(1, 'fx1', self.a.identity, 'reset'),
                       Instance(2, 'fx1', self.a.identity)))
        self.assertEqual(cm.exception.code, 'transition')

    def test_full_sixteen_slots_then_empty_part(self):
        target = tuple(Instance(t, slot, self.a.identity) for t in range(1, 9)
                       for slot in ('fx1', 'fx2'))
        plan = activate(self.p, target)
        self.assertEqual(plan.steady_cycles, (80, 80))
        self.assertEqual(len([a for a in plan.allocations if a.space == 'P']), 2)
        empty = self.p.prepare(())
        self.assertEqual(empty.required_cores, frozenset((0, 1)))
        self.assertEqual(empty.steady_cycles, (0, 0))
        self.assertEqual(empty.transition_cycles, (80, 80))
        for c in empty.required_cores:
            self.p.acknowledge(empty, c)
        self.p.commit(empty)
        self.assertTrue(self.p.allocations)
        self.p.finish_transition()
        self.assertEqual(self.p.allocations, ())

    def test_seeded_random_transitions_never_overlap(self):
        rng = random.Random(808909)
        for _ in range(200):
            target = tuple(Instance(t, 'fx1', rng.choice((self.a, self.b)).identity)
                           for t in range(1, 9) if rng.randrange(3))
            plan = self.p.prepare(target)
            union = tuple(dict.fromkeys(self.p.allocations + plan.staged))
            for idx, a in enumerate(union):
                for b in union[idx + 1:]:
                    if (a.core, a.space) == (b.core, b.space):
                        self.assertTrue(a.base + a.words <= b.base or b.base + b.words <= a.base)
            for c in plan.required_cores:
                self.p.acknowledge(plan, c)
            self.p.commit(plan)
            self.p.finish_transition()


if __name__ == '__main__':
    unittest.main()
