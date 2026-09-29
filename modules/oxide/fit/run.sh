#!/bin/sh
# run a python script in the venv, dropping the UA plugin's logger banner
cd "$(dirname "$0")" && ./v/bin/python "$@" 2>&1 | grep -v -E "^\s+(General|Errors|Sockets|ServerSockets|ClientSockets|Mixer|Engine|Plugin|Async|MIDISync|UAPW|HBGF|Timers)@?|^\s+Timers:|^$"
