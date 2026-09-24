"""Machinedrum native-machine skeleton.

WP-B1 declares the ownership envelope for the first MD image; since the
24 September decision it is core 1's (payload B, tracks 1-4). The DSP source
and ColdFire registration are intentionally not claimed yet: WP-B2 will
connect the user's build-time extraction to this manifest without copying
any firmware into the repository.
"""

from pathlib import Path
import runpy

from remix.schema import Kind, Module


_LAYOUT = runpy.run_path(str(Path(__file__).with_name("layout.py")))
LAYOUT = _LAYOUT["LAYOUT"]


def _allocation(name):
    return next(region for region in LAYOUT["allocations"]
                if region["name"] == name)


def _span(name):
    region = _allocation(name)
    return {
        "name": name,
        "space": region["space"],
        "start": region["start"],
        "end": region["start"] + region["words"],
        "words": region["words"],
    }


# B1's resource declaration is deliberately plain data.  It is derived from
# layout.py so a later extractor cannot quietly acquire a second address book.
# The generic remixer ledger does not yet arbitrate the shared physical window;
# B2 is where these claims become build placement and collision checks.
RESOURCE_CLAIMS = {
    "payload": "B",
    "donor": {
        "name": "payload-B stock effects and the P above them",
        "space": "P",
        "start": _allocation("hot_code")["start"],
        "end": (_allocation("driver_code")["start"]
                + _allocation("driver_code")["words"]),
        "words": (_allocation("hot_code")["words"]
                  + _allocation("driver_code")["words"]),
    },
    "shared": tuple(_span(name) for name in ("window_code", "window_tables", "sine")),
}


def _check_claims():
    spans = [RESOURCE_CLAIMS["donor"], *RESOURCE_CLAIMS["shared"]]
    for left, right in zip(sorted(spans, key=lambda item: item["start"]),
                           sorted(spans, key=lambda item: item["start"])[1:]):
        if left["space"] == right["space"] and left["end"] > right["start"]:
            raise ValueError(
                f"Machinedrum resource claims overlap: {left['name']} and "
                f"{right['name']}")


_check_claims()


MODULE = Module(
    name="machinedrum",
    key="MACHINEDRUM",
    kind=Kind.CF_PATCH,
    doc=("Native Machinedrum core-1 machine skeleton: payload-B donor and "
         "shared-window ownership from the proposed layout."),
)
