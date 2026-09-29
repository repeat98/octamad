"""Run continuous audio comparison while a real capacity guard refuses a pattern."""
import sys
from pathlib import Path
if not __package__:
    sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
    __package__='tools.experimental.dsp_part_loader'
from .verify_live_audio import main
if __name__=='__main__': main(pattern=True,refuse=True)
