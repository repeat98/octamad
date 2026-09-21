"""One construction of the dsp_host command used by Euclid verifiers."""


def command(host, mem, init, proc, src, dst, params, blocks, *, audio=None,
            guard=False, schedules=()):
    args = [str(host), '-mem', str(mem), '-init', f'{init:x}', '-proc', f'{proc:x}']
    if audio is not None:
        args += ['-audio', str(audio)]
    args += ['-frames', '16', '-blocks', str(blocks), '-alloc', '0', '-r7', '1',
             '-in', str(src), '-out', str(dst),
             '-params', ','.join(map(str, params))]
    if guard:
        args.append('-guard')
    for row in schedules:
        block, changed = row[0], row[1:]
        args += ['-sched', ','.join(
            f'{block}:0:{slot}={value}' for slot, value in enumerate(changed))]
    return args
