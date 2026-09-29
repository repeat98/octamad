"""Conservative, non-compacting planner; preparation never mutates live state.

Pool ranges and cycle allowances MUST exclude the resident system. This model
has no hardware defaults. Private pools only: shared P/X/Y aliases require a
single backing-store allocator and are refused in this first insert-only ABI.
"""
from dataclasses import dataclass
from .package import Package, SPACES


class Refused(ValueError):
    def __init__(self, code, detail):
        self.code = code
        super().__init__(detail)

    @property
    def modal(self):
        return {'memory': 'DSP memory full', 'cycles': 'DSP processing limit',
                'transition': 'DSP transition needs more memory',
                'transition_cycles': 'DSP transition processing limit',
                'unsupported': 'DSP module unavailable'}.get(self.code, 'DSP load failed')


@dataclass(frozen=True)
class Pool:
    space: str
    base: int
    words: int

    def __post_init__(self):
        if (self.space not in SPACES or type(self.base) is not int or type(self.words) is not int
                or self.base < 0 or self.words <= 0 or self.base + self.words > 0x1000000):
            raise ValueError('invalid private pool')
        if self.base < 0x40000 and self.base + self.words > 0x30000:
            raise ValueError('shared aliases are not private pools')


@dataclass(frozen=True)
class Budget:
    pools: tuple[Pool, ...]
    cycles_per_block: int

    def __post_init__(self):
        if not isinstance(self.pools, tuple) or type(self.cycles_per_block) is not int or self.cycles_per_block <= 0:
            raise ValueError('invalid budget')
        if {p.space for p in self.pools} != set(SPACES) or len(self.pools) != 3:
            raise ValueError('one private pool per space required')


@dataclass(frozen=True)
class Instance:
    track: int
    slot: str
    package: str                 # content hash, never an ambiguous name
    continuity: str = 'default'  # change this to request new state

    def __post_init__(self):
        if type(self.track) is not int or not 1 <= self.track <= 8 or self.slot not in ('fx1', 'fx2'):
            raise ValueError('invalid track/slot')

    @property
    def core(self):
        return 1 if self.track <= 4 else 0


@dataclass(frozen=True)
class Allocation:
    core: int
    space: str
    base: int
    words: int
    owner: tuple


@dataclass(frozen=True)
class Plan:
    generation: int
    instances: tuple[Instance, ...]
    allocations: tuple[Allocation, ...]  # target after transition retires
    staged: tuple[Allocation, ...]      # new uploads/state, never overwrites live
    required_cores: frozenset[int]
    steady_cycles: tuple[int, int]
    transition_cycles: tuple[int, int]


def _first_fit(pool, used, words, alignment):
    cursor = pool.base
    for a in sorted(used, key=lambda a: a.base):
        cursor = (cursor + alignment - 1) & -alignment
        if cursor + words <= a.base:
            return cursor
        cursor = max(cursor, a.base + a.words)
    cursor = (cursor + alignment - 1) & -alignment
    return cursor if cursor + words <= pool.base + pool.words else None


class Planner:
    def __init__(self, packages: tuple[Package, ...], budgets: tuple[Budget, Budget]):
        self.packages = {p.identity: p for p in packages}
        if len(self.packages) != len(packages) or len(budgets) != 2:
            raise ValueError('duplicate packages or missing core budget')
        self.budgets = budgets
        self.generation = 0
        self.instances = ()
        self.allocations = ()
        self._pending = None
        self._ready = set()
        self._retiring = False

    def _cycles(self, instances):
        counts = [0, 0]
        for i in instances:
            p = self.packages.get(i.package)
            if p is None or i.slot not in p.slots or p.cycles_per_block is None:
                raise Refused('unsupported', f'T{i.track} {i.slot}: missing package, slot support or cycle evidence')
            counts[i.core] += p.cycles_per_block
        return tuple(counts)

    def _place(self, instances, preserve):
        used = list(self.allocations if preserve else ())
        target, staged = [], []
        needed = []
        for i in instances:
            p = self.packages[i.package]
            for s in p.sections:
                if s.words:
                    needed.append((i.core, s.space, ('code', p.identity, s.space), len(s.words), s.alignment))
            if p.state_words:
                needed.append((i.core, 'X', ('state', i), p.state_words, 1))
        seen = set()
        for core, space, owner, words, alignment in needed:
            key = (core, owner)
            if key in seen:
                continue
            seen.add(key)
            existing = next((a for a in used if a.core == core and a.owner == owner), None)
            if existing is not None:
                target.append(existing)
                continue
            pool = next(p for p in self.budgets[core].pools if p.space == space)
            base = _first_fit(pool, [a for a in used if a.core == core and a.space == space], words, alignment)
            if base is None:
                raise Refused('memory', f'core {core} {space}: cannot place {words} words for {owner[0]}')
            a = Allocation(core, space, base, words, owner)
            used.append(a)
            staged.append(a)
            target.append(a)
        return tuple(target), tuple(staged)

    def prepare(self, instances: tuple[Instance, ...]):
        if self._pending is not None or self._retiring:
            raise Refused('busy', 'finish or cancel the previous transition first')
        if not isinstance(instances, tuple) or len({(i.track, i.slot) for i in instances}) != len(instances):
            raise ValueError('Part must contain unique immutable track/slot selections')
        steady = self._cycles(instances)
        for core in (0, 1):
            if steady[core] > self.budgets[core].cycles_per_block:
                raise Refused('cycles', f'core {core}: Part exceeds processing allowance')
        # First classify target fit independently from overlap/fragmentation.
        self._place(instances, False)
        transition = self._cycles(tuple(dict.fromkeys(self.instances + instances)))
        for core in (0, 1):
            if transition[core] > self.budgets[core].cycles_per_block:
                raise Refused('transition_cycles', f'core {core}: outgoing and incoming instances exceed allowance')
        try:
            target, staged = self._place(instances, True)
        except Refused as exc:
            raise Refused('transition', str(exc)) from exc
        # Dispatch changes need acknowledgement even when no bytes are uploaded.
        changed = frozenset(c for c in (0, 1) if
                            tuple(i for i in self.instances if i.core == c) !=
                            tuple(i for i in instances if i.core == c))
        plan = Plan(self.generation, instances, target, staged, changed, steady, transition)
        self._pending = plan
        self._ready.clear()
        return plan

    def _check(self, plan):
        if plan is not self._pending or plan.generation != self.generation:
            raise Refused('stale', 'stale or foreign plan')

    def acknowledge(self, plan, core):
        """Transport adapter calls this ONLY after verified upload and dispatch staging."""
        self._check(plan)
        if core not in plan.required_cores:
            raise ValueError('core is not a participant')
        self._ready.add(core)

    def cancel(self, plan):
        self._check(plan)
        self._pending = None
        self._ready.clear()

    def commit(self, plan):
        """Model a coordinated boundary; this function does not clock DSP hardware.

        Keep outgoing allocations reserved until finish_transition: calling commit
        is not evidence that tails/crossfades have finished using their memory.
        """
        self._check(plan)
        if self._ready != set(plan.required_cores):
            raise Refused('not_ready', 'all participating cores must be ready')
        self.allocations = tuple(dict.fromkeys(self.allocations + plan.allocations))
        self.instances = plan.instances
        self._target = plan.allocations
        self._retiring = True
        self._pending = None
        self._ready.clear()
        self.generation += 1

    def finish_transition(self):
        """Audio adapter must confirm outgoing voices/tails are no longer executing."""
        if not self._retiring:
            raise Refused('stale', 'no transition to retire')
        self.allocations = self._target
        self._retiring = False
