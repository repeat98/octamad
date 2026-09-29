"""Compile and test the actual firmware controller on the host."""
from pathlib import Path
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[3]
def main():
    subprocess.run(['python3','modules/dsp-loader-transfer/generate.py','--check'],
                   cwd=ROOT,check=True)
    with tempfile.TemporaryDirectory(prefix='dsp-transfer-') as directory:
        binary=Path(directory)/'controller'
        subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-DDL_NATIVE_TEST',
                        '-Imodules/dsp-loader-transfer',
                        'modules/dsp-loader-transfer/transfer.c',
                        'tools/experimental/dsp_part_loader/test_transfer.c',
                        '-o',str(binary)],cwd=ROOT,check=True)
        subprocess.run([str(binary)],check=True)
        subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-DDL_NATIVE_TEST',
                        '-Imodules/dsp-loader-transfer',
                        'modules/dsp-loader-transfer/selection.c',
                        'tools/experimental/dsp_part_loader/test_selection.c',
                        '-o',str(binary)],cwd=ROOT,check=True)
        subprocess.run([str(binary)],check=True)
        subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror',
                        '-Imodules/dsp-loader-transfer',
                        'modules/dsp-loader-transfer/allocator.c',
                        'tools/experimental/dsp_part_loader/test_allocator.c',
                        '-o',str(binary)],cwd=ROOT,check=True)
        subprocess.run([str(binary)],check=True)
        subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-DDL_NATIVE_TEST',
                        '-Imodules/dsp-loader-transfer',
                        'modules/dsp-loader-transfer/allocator.c',
                        'modules/dsp-loader-transfer/manager.c',
                        'tools/experimental/dsp_part_loader/test_manager.c',
                        '-o',str(binary)],cwd=ROOT,check=True)
        subprocess.run([str(binary)],check=True)
    print('PASS: native transfer, selection guards, allocator and residency backend; acknowledgements, capacity, sharing, cancellation and retirement')
if __name__=='__main__': main()
