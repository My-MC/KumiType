"""Command-line entry point."""
import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from .source_registry import import_source, install_sources, update_lock

from .config import Target, load, targets
from .builder import build_all, build_one
from .report import doctor, write_validation_report
from .validator import audit_matrix, validate_all
from .packager import package_all


def main() -> int:
    parser = argparse.ArgumentParser(prog='kumitype')
    parser.add_argument('--config', default='config/build.yaml')
    sub = parser.add_subparsers(dest='command', required=True)
    listing = sub.add_parser('list', help='Show configured build targets')
    listing.add_argument('--json', action='store_true')
    fetching = sub.add_parser('fetch', help='Fetch pinned and hash-verified sources')
    fetching.add_argument('--lock', type=Path, default=Path('config/sources.lock.toml'))
    fetching.add_argument('--source-dir', type=Path, default=Path('source'))
    fetching.add_argument('--cache-dir', type=Path, default=Path('cache'))
    building = sub.add_parser('build', help='Build a static font offline')
    building.add_argument('--base', required=True)
    building.add_argument('--jp', required=True)
    building.add_argument('--weight', type=int, default=400)
    building.add_argument('--style', default='normal')
    building.add_argument('--all-weights', action='store_true')
    building.add_argument('--all-styles', action='store_true')
    all_build = sub.add_parser('build-all', help='Build all configured targets offline')
    all_build.add_argument('--jobs', default=None)
    for command in (building, all_build):
        command.add_argument('--source-dir', type=Path, default=Path('source'))
        command.add_argument('--output-dir', type=Path, default=Path('build'))
    sub.add_parser('doctor', help='Inspect build environment')
    validation = sub.add_parser('validate', help='Validate generated fonts')
    validation.add_argument('--all', action='store_true', required=True)
    validation.add_argument('--harfbuzz', default='hb-shape', help='HarfBuzz executable path')
    validation.add_argument('--require-harfbuzz', action='store_true',
                            help='Fail if shaping cannot be checked')
    packaging = sub.add_parser('package', help='Package generated families with licenses')
    packaging.add_argument('--all', action='store_true', required=True)
    updating = sub.add_parser('update-source', help='Explicitly update one pinned source record')
    updating.add_argument('--lock', type=Path, default=Path('config/sources.lock.toml'))
    for option in ('id', 'version', 'url', 'sha256', 'format'):
        updating.add_argument('--' + option, required=True)
    updating.add_argument('--filename')
    importing = sub.add_parser('import-source', help='Import a locked source artifact offline')
    importing.add_argument('--lock', type=Path, default=Path('config/sources.lock.toml'))
    importing.add_argument('--id', required=True)
    importing.add_argument('--file', type=Path, required=True)
    auditing = sub.add_parser('audit', help='Check configured matrix completeness')
    for command in (validation, packaging, auditing):
        command.add_argument('--build-dir', type=Path, default=Path('build'))
    packaging.add_argument('--source-dir', type=Path, default=Path('source'))
    packaging.add_argument('--output-dir', type=Path, default=Path('dist'))
    args = parser.parse_args()
    try:
        if args.command == 'audit':
            result = audit_matrix(load(args.config), args.build_dir)
            print(json.dumps(result, indent=2))
            return 0 if result['complete'] else 1
        if args.command == 'import-source':
            result = import_source(args.lock, args.id, args.file)
            print(f"Imported {result['id']} {result['version']}: {len(result['fonts'])} fonts")
            return 0
        if args.command == 'update-source':
            update_lock(args.lock, args.id, args.version, args.url, args.sha256,
                        args.format, args.filename)
            print(f'Updated source lock: {args.id} {args.version}')
            return 0
        if args.command == 'package':
            for archive in package_all(root=args.build_dir, source=args.source_dir, output=args.output_dir):
                print(archive)
            return 0
        if args.command == 'validate':
            results = validate_all(root=args.build_dir, harfbuzz=args.harfbuzz)
            if args.require_harfbuzz:
                for result in results:
                    if result.get('shaping', {}).get('status') != 'passed':
                        result['errors'].append('Required HarfBuzz validation did not pass')
                        result['valid'] = False
            write_validation_report(results, args.build_dir)
            print(json.dumps(results, indent=2))
            return 0 if results and all(r['valid'] for r in results) else 1
        if args.command == 'doctor':
            config = load(args.config)
            print(json.dumps(doctor(lock=Path(config.get('sources', {}).get(
                'lock', 'config/sources.lock.toml'))), indent=2))
            return 0
        if args.command == 'fetch':
            results = install_sources(args.lock, args.source_dir, args.cache_dir)
            for result in results:
                print(f"{result['id']} {result['version']}: {len(result['fonts'])} fonts")
            return 0
        config = load(args.config)
        if args.command == 'build-all':
            build_all(config, args.jobs, args.source_dir, args.output_dir)
            return 0
        matrix = targets(config)
        if args.command == 'build':
            weights = config['weights'] if args.all_weights else [args.weight]
            styles = config['styles'] if args.all_styles else [args.style]
            for weight in weights:
                for style in styles:
                    target = Target(args.base, args.jp, weight, style)
                    if target not in matrix:
                        raise ValueError(f'Target not configured: {target}')
                    print(build_one(config, target, args.source_dir, args.output_dir))
            return 0
        if args.json:
            print(json.dumps([asdict(item) for item in matrix], indent=2))
        else:
            for key in ('variants', 'japanese_fonts', 'weights', 'styles'):
                print(f'{key}: {", ".join(map(str, config[key]))}')
            print(f'{len(matrix)} static TTF targets')
        return 0
    except (OSError, ValueError) as exc:
        print(f'kumitype: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
