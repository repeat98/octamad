"""STOCK ANALYSIS FAST -- preserve the stock analysis math; amortize its loop control."""
from remix.schema import Detour, Kind, Linked, Module

MODULE = Module(
    name="stock-analysis-fast",
    key="STOCK ANALYSIS FAST",
    kind=Kind.CF_PATCH,
    doc="Experimental stock sample-analysis loop unroll; hardware saving unmeasured.",
    linked=(Linked("analysis-fast", "modules/stock-analysis-fast/analysis.s", cpu="5475",
                   reference=(0x400D6B80, "8cfff0df430449efcf006c0b75c590bed38f83cc70954de16ee2cb36c95edc0d")),),
    detours=(Detour(
        0x40098494, bytes.fromhex("2141fff4a2030900"),
        "analysis-fast", "analysis_fast",
        "stock analysis recurrence: eight original iterations per loop",
        pad_to=8,
    ),),
)
