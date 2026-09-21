"""Opt-in, bounded MIDI diagnostics; no card writes."""
from remix.schema import Detour, Kind, Linked, Module
MODULE = Module(
    name='crash-trace', key='CRASH TRACE', kind=Kind.CF_PATCH,
    doc='Sparse MIDI checkpoints and a bounded exception report before the panel printer.',
    linked=(Linked('crashtrace', 'modules/crash-trace/trace.s', dram=False),),
    detours=(
        Detour(0x4000d568, bytes.fromhex('203c75180000'), 'crashtrace', 'trace_frame',
               'Checkpoint after Euclid and before stock output scaling'),
        Detour(0x4003af94, bytes.fromhex('4fefffd448d7040c'), 'crashtrace', 'trace_fault',
               'Report the exception frame before touching the panel UART', pad_to=8),
    ),
)
