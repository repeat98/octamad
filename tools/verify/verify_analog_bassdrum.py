#!/usr/bin/env python3
"""Check generated descriptor helpers; DSP audio is tested by bd808/bd909."""
import pathlib
import subprocess
ROOT=pathlib.Path(__file__).resolve().parents[2]
def main():
    subprocess.run(['python3',str(ROOT/'modules/analog-bassdrum/generate.py'),'--check'],check=True)
    print('PASS generated ColdFire descriptor helpers; synthesis gates run on the DSP')
if __name__=='__main__':main()
