"""Versioned, immutable DSP packages with explicit full-word relocations.

V1 supports ordinary inserts, private P/X/Y and r7-relative instance state.
It deliberately rejects bus servers, shared aliases and fixed-address hooks.
Package hashes identify content; they are not signatures or hardware proof.
"""
from dataclasses import asdict, dataclass
import hashlib
import json

SPACES = ('P', 'X', 'Y')
WORD_MAX = (1 << 24) - 1


@dataclass(frozen=True)
class Section:
    space: str
    words: tuple[int, ...]
    alignment: int = 1

    def __post_init__(self):
        if self.space not in SPACES or not isinstance(self.words, tuple):
            raise ValueError('section needs P/X/Y and immutable words')
        if type(self.alignment) is not int or self.alignment < 1 or self.alignment & (self.alignment - 1):
            raise ValueError('alignment must be a positive power of two')
        if any(type(w) is not int or not 0 <= w <= WORD_MAX for w in self.words):
            raise ValueError('section contains a non-24-bit word')


@dataclass(frozen=True)
class Relocation:
    section: str
    offset: int
    target: str
    addend: int


@dataclass(frozen=True)
class Package:
    name: str
    sections: tuple[Section, ...]
    relocations: tuple[Relocation, ...]
    init: int
    proc: int
    state_words: int
    cycles_per_block: int | None
    cycle_evidence: str
    source_hash: str
    slots: tuple[str, ...] = ('fx1', 'fx2')
    abi: str = 'insert-r7-v1'
    version: int = 1

    def __post_init__(self):
        if type(self.version) is not int or self.version != 1 or self.abi != 'insert-r7-v1' or not isinstance(self.name, str) or not self.name:
            raise ValueError('unsupported package version/ABI or empty name')
        if not all(isinstance(v, tuple) for v in (self.sections, self.relocations, self.slots)):
            raise ValueError('package collections must be immutable')
        by_space = {s.space: s for s in self.sections}
        if len(by_space) != len(self.sections) or 'P' not in by_space:
            raise ValueError('exactly one section per space; P required')
        if not all(type(v) is int and 0 <= v < len(by_space['P'].words) for v in (self.init, self.proc)):
            raise ValueError('entry point outside P')
        if type(self.state_words) is not int or not 0 <= self.state_words <= 0x84:
            raise ValueError('state exceeds the stock r7 instance contract')
        if not self.slots or len(set(self.slots)) != len(self.slots) or set(self.slots) - {'fx1', 'fx2'}:
            raise ValueError('invalid insert slots')
        if self.cycles_per_block is not None and (type(self.cycles_per_block) is not int or self.cycles_per_block <= 0 or not isinstance(self.cycle_evidence, str) or not self.cycle_evidence):
            raise ValueError('processing budget needs a positive bound and evidence')
        if len(self.source_hash) != 64 or any(c not in '0123456789abcdef' for c in self.source_hash):
            raise ValueError('source identity must be sha256')
        seen = set()
        for r in self.relocations:
            if r.section not in by_space or r.target not in by_space:
                raise ValueError('relocation names absent section')
            if type(r.offset) is not int or not 0 <= r.offset < len(by_space[r.section].words):
                raise ValueError('relocation outside section')
            if type(r.addend) is not int or not 0 <= r.addend < len(by_space[r.target].words):
                raise ValueError('relocation outside target')
            if (r.section, r.offset) in seen:
                raise ValueError('duplicate relocation')
            seen.add((r.section, r.offset))
            if by_space[r.section].words[r.offset] != r.addend:
                raise ValueError('relocation must contain its normalized addend')

    def to_json(self):
        return json.dumps(asdict(self), sort_keys=True, separators=(',', ':'))

    @classmethod
    def from_json(cls, text):
        data = json.loads(text)
        data['sections'] = tuple(Section(s['space'], tuple(s['words']), s['alignment'])
                                 for s in data['sections'])
        data['relocations'] = tuple(Relocation(**r) for r in data['relocations'])
        data['slots'] = tuple(data['slots'])
        return cls(**data)

    @property
    def identity(self):
        return hashlib.sha256(self.to_json().encode()).hexdigest()

    def relocate(self, bases):
        if set(bases) != {s.space for s in self.sections}:
            raise ValueError('supply exactly one base for every section')
        result = {}
        for s in self.sections:
            base = bases[s.space]
            if type(base) is not int or base < 0 or base % s.alignment or base + len(s.words) > WORD_MAX + 1:
                raise ValueError('misaligned or out-of-range section')
            result[s.space] = list(s.words)
        for r in self.relocations:
            result[r.section][r.offset] = bases[r.target] + r.addend
        return {s: tuple(w) for s, w in result.items()}
