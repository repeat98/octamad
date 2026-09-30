# `tools/remix/`: the remix engine and the remixer

The code that turns `modules/<name>/manifest.py` files and a
`remixes/<name>/remix.py` selection into an image, checks it, and the
`make remix` front end. The user guide for the front end is
[`docs/guide/REMIXER.md`](../../docs/guide/REMIXER.md); writing a module is
[`docs/contributing/MODULES.md`](../../docs/contributing/MODULES.md).

| file | does |
|---|---|
| `schema.py` | what a module and a remix may declare (`Module`, `Remix`, `Gate`, `Linked`, `Detour`, `CavePatch`, `Runtime`, ...) |
| `registry.py` | finds every `modules/*/manifest.py` and `remixes/**/remix.py`; no central list |
| `ledger.py` | cross-module resource collisions (FX2 id, cave, hook site, detour, poke, runtime write, core-private Y, FX2 buffer region), refused by name before a byte is written |
| `stock.py` | the stock FX2 effects as rows a remix can keep in the chooser; what a remix harvests |
| `rig.py` | a module's category, track range and chooser, derived from the manifests |
| `index.py` | `make modules`, `make docs`: the module table in `README.md` and the remix index |
| `selftest.py` | proves the ledger catches each collision class and every shipped remix is clean |
| `platform_build.py`, `loader.S` | the DRAM platform: every DRAM unit linked as one image, packed and appended after the OS behind the loader (derived from Em's Octakit loader) |
| `runtime_build.py` | a loader-appended runtime from its recipe (Octakit's `firmware.json`); memoised in `out/cache/` |
| `arena.py` | the audio page arena and the pages a remix takes from it for DRAM |
| `grains.py`, `geom.py` | BusDelay's per-build source substitutions (GRAIN count, line geometry) |
| `state.py` | the remixer's model: selection, `problems()`, `measure()`, scratch builds; no UI import |
| `audition.py` | render any effect on a source wav, knobs by manifest name; a `__main__` for headless renders |
| `app.py` | the Textual shell of `make remix`: screens, keys, workers |

The DSP-side build itself is `tools/build/build_bus.py`.

## The remixer

### Layers

| layer | file | job |
|---|---|---|
| composer | `tools/remix/state.py` | selection, `problems()`, `measure()`, scratch builds |
| rig | `tools/remix/rig.py` | category + track-range derivation, knob docs/labels/maxima |
| rendering | `tools/remix/audition.py` | the per-effect dispatch below, the journal, a `__main__` for headless renders |
| shell | `tools/remix/app.py` | Textual only: screens, keys, workers |

The panel render is cached on (page, effect id, build) and `problems()` is
computed once per pass (3.6 ms per knob step).

The panel pane boots each rebuilt image in Tier-0 (`tools/emu/README.md`).
`tools/verify/verify_remixer.py` (in `make check`) opens the app headless
with the rebuild switched off and draws every selection in all three
panes.

### The audition backend, per effect

| effect | path |
|---|---|
| busverb | `tools/harness/render_reverb.py`, its own fingerprinted engine cache |
| busdelay | the DEV hatch (`DEV=1 XBUS=1` → `out/dsp/mem_dev_A.mem`, rebuilt when stale), then `send_probe --layout DS` |
| inserts | a per-insert scratch image (the insert + SEND), dumped to `out/dsp/_audition_<name>_A.mem`; the user's `out/mainos_bus.bin` is saved and restored around the scratch build |
| stock | a dump of the stock image's payload A, `-alloc 1 -audio 0` |

An id absent from an image dispatches to the fallback; `send_probe`'s
SEND-alias guard refuses to measure it. Every render and A/B mark is
journalled to `out/_audition/log.jsonl` (track, effect, source, every
knob).
