"""Compile and test the actual firmware controller on the host."""
from pathlib import Path
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[3]
def main():
    subprocess.run(['python3','modules/dsp-dynload-transport/generate.py','--check'],
                   cwd=ROOT,check=True)
    with tempfile.TemporaryDirectory(prefix='dsp-transfer-') as directory:
        binary=Path(directory)/'controller'
        subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-DDL_NATIVE_TEST',
                        '-Imodules/dsp-dynload-transport',
                        'modules/dsp-dynload-transport/transfer.c',
                        'tools/experimental/dsp_dynload/test_transfer.c',
                        '-o',str(binary)],cwd=ROOT,check=True)
        subprocess.run([str(binary)],check=True)
        subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-DDL_NATIVE_TEST',
                        '-Imodules/dsp-dynload-transport',
                        'modules/dsp-dynload-transport/selection.c',
                        'tools/experimental/dsp_dynload/test_selection.c',
                        '-o',str(binary)],cwd=ROOT,check=True)
        subprocess.run([str(binary)],check=True)
        subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror',
                        '-Imodules/dsp-dynload-transport',
                        'modules/dsp-dynload-transport/allocator.c',
                        'tools/experimental/dsp_dynload/test_allocator.c',
                        '-o',str(binary)],cwd=ROOT,check=True)
        subprocess.run([str(binary)],check=True)
        subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-DDL_NATIVE_TEST',
                        '-Imodules/dsp-dynload-transport',
                        'modules/dsp-dynload-transport/allocator.c',
                        'modules/dsp-dynload-transport/manager.c',
                        'tools/experimental/dsp_dynload/test_manager.c',
                        '-o',str(binary)],cwd=ROOT,check=True)
        subprocess.run([str(binary)],check=True)
        for name in ('preflight','publication'):
            subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-DDL_NATIVE_TEST',
                            '-Imodules/dsp-dynload-transport',
                            f'modules/dsp-dynload-transport/{name}.c',
                            f'tools/experimental/dsp_dynload/test_{name}.c',
                            '-o',str(binary)],cwd=ROOT,check=True)
            subprocess.run([str(binary)],check=True)
    print('PASS: native transfer, selection guards, allocator and residency backend; acknowledgements, capacity, sharing, cancellation and retirement')
if __name__=='__main__': main()
