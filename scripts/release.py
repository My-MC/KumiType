#!/usr/bin/env python3
"""Run the offline release pipeline, retaining per-stage logs and wall times."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

from kumitype.artifacts import write_text
from kumitype.config import load, resolve_path
from kumitype.selection import add_options, select

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=ROOT / 'config/build.yaml')
    parser.add_argument('--jobs', default='auto')
    parser.add_argument('--build-dir', type=Path)
    parser.add_argument('--dist-dir', type=Path)
    parser.add_argument('--harfbuzz', default='hb-shape')
    add_options(parser)
    args = parser.parse_args()
    config = load(args.config)
    selection = select(config, args)
    if selection.selectors['weight'] or selection.selectors['style']:
        parser.error('Release requires complete families; --weight/--style are not supported')
    build = resolve_path(config, args.build_dir or config['paths']['build'])
    dist = resolve_path(config, args.dist_dir or config['paths']['dist'])
    selectors = []
    for key in ('base', 'jp', 'family'):
        for value in getattr(args, key, None) or []:
            selectors.extend(['--' + key, value])
    cli = [sys.executable, '-m', 'kumitype.cli', '--config', str(args.config.resolve())]
    stages = [
        ('build', cli + ['build', *selectors, '--jobs', args.jobs, '--output-dir', str(build)]),
        ('audit', cli + ['audit', *selectors, '--build-dir', str(build)]),
        ('validate', cli + ['validate', *selectors, '--build-dir', str(build), '--jobs', args.jobs,
                            '--harfbuzz', args.harfbuzz, '--require-harfbuzz']),
        ('package', cli + ['package', *selectors, '--build-dir', str(build), '--jobs', args.jobs,
                           '--output-dir', str(dist)]),
        ('check-packages', [sys.executable, str(ROOT / 'scripts/check-packages.py'),
                            '--build-dir', str(build), '--dist-dir', str(dist)]),
    ]
    build.mkdir(parents=True, exist_ok=True)
    report = {'jobs': args.jobs, 'selection': selection.summary(), 'stages': []}
    started = time.monotonic()
    for name, command in stages:
        stage_start = time.monotonic()
        print(f'{name}: starting', file=sys.stderr, flush=True)
        with (build / f'pipeline-{name}.stdout.log').open('w') as stdout, \
                (build / f'pipeline-{name}.stderr.log').open('w') as stderr:
            result = subprocess.run(command, cwd=ROOT, stdout=stdout, stderr=stderr)
        seconds = time.monotonic() - stage_start
        report['stages'].append({'name': name, 'command': command, 'seconds': seconds,
                                 'returncode': result.returncode})
        report['total_seconds'] = time.monotonic() - started
        write_text(build / 'pipeline-timings.json', json.dumps(report, indent=2) + '\n')
        print(f'{name}: {seconds:.2f}s, exit {result.returncode}', file=sys.stderr, flush=True)
        if result.returncode:
            return result.returncode
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
