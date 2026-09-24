#!/usr/bin/env python3
"""Drive the ColdFire port's panel from a script (the Machinedrum editor gates).

    from md_panel import run_scripted
    run_scripted(cmd, script, log)

`cmd` is an ot_emu command line without --live; `script` is a list of
(wall seconds to wait before, line) where line is what `ot_emu --live`
reads (docs/remixer/EMU.md, "Driving it: the panel from a FIFO"):
`key <code> down|up`, `enc <n> <delta>`, `pot <v>`, `midi <hex>...`,
`quit`. The waits are wall time: the port runs about 15 frames a second
with both DSP cores, so a wait is a coarse "after the UI has settled",
never a timing. The FIFO is created in a private temp directory.

The port reads the FIFO only after the project has loaded (the RTOS is
up), and a writer blocks until the reader opens it, so the first wait
should cover the load (about 40 s wall for the 20 s --load-ms).
"""
import os
import subprocess
import tempfile
import threading
import time


def run_scripted(cmd, script, log_path, cwd=None, timeout=1800):
    with tempfile.TemporaryDirectory() as td:
        fifo = os.path.join(td, "panel.fifo")
        os.mkfifo(fifo)
        full = list(cmd) + ["--live", fifo]
        with open(log_path, "w") as log:
            log.write(" ".join(str(c) for c in full) + "\n")
            log.flush()
            proc = subprocess.Popen(full, cwd=cwd, stdout=log, stderr=subprocess.STDOUT)
            sent = []

            def feed():
                try:
                    with open(fifo, "w") as f:      # blocks until the port opens it
                        for wait, line in script:
                            time.sleep(wait)
                            if proc.poll() is not None:
                                return
                            f.write(line + "\n")
                            f.flush()
                            sent.append((time.time(), line))
                except (BrokenPipeError, OSError):
                    pass
            t = threading.Thread(target=feed, daemon=True)
            t.start()
            try:
                rc = proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                proc.kill()
                rc = proc.wait()
            t.join(timeout=5)
            return rc, sent


def key(code, hold=0.6, gap=0.6):
    """A press and release of one key: two script lines."""
    return [(gap, f"key {code:#x} down"), (hold, f"key {code:#x} up")]
