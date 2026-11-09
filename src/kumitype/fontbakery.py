"""Run universal (including OpenType) checks without hiding unapproved failures."""
import hashlib
import json
import re
import subprocess
import sys
from importlib.metadata import version
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


def load_policy(path: Path) -> dict:
    data = json.loads(path.read_text())
    if data.get('schema_version') != 1 or not isinstance(data.get('exceptions'), list):
        raise ValueError('Invalid FontBakery allowlist schema')
    policy = {}
    for entry in data['exceptions']:
        check, code, reason = (entry.get(k) for k in ('check_id', 'code', 'reason'))
        if (not isinstance(check, str) or not re.fullmatch(r'[A-Za-z0-9_/.-]+', check)
                or not isinstance(code, str) or not re.fullmatch(r'[A-Za-z0-9_.-]+', code)
                or not isinstance(reason, str) or not re.search(r'[ぁ-んァ-ヶ一-龯]', reason)
                or (check, code) in policy):
            raise ValueError('Allowlist requires unique exact check/code and Japanese reason')
        policy[check, code] = reason
    return policy


def classify(report: dict, policy: dict) -> dict:
    try:
        checks = [c for s in report['sections'] for c in s['checks']]
        counts = Counter(c['result'] for c in checks)
        declared = {s: n for s, n in report['result'].items() if n}
        if not checks or dict(counts) != declared or not counts.keys() <= {
                'PASS', 'SKIP', 'INFO', 'WARN', 'FAIL', 'ERROR', 'FATAL', 'DEBUG'}:
            raise ValueError('Empty, incomplete or inconsistent FontBakery report')
    except (KeyError, TypeError) as exc:
        raise ValueError('Malformed FontBakery report') from exc
    failures, allowed, warnings = [], [], []
    for section in report['sections']:
        for check in section['checks']:
            identifier = check['key'][1].removeprefix('<FontBakeryCheck:').removesuffix('>')
            statuses = {log['status'] for log in check['logs']}
            if (not statuses <= {'PASS', 'SKIP', 'INFO', 'WARN', 'FAIL', 'ERROR', 'FATAL', 'DEBUG'}
                    or (check['result'] in ('FAIL', 'ERROR', 'FATAL') and check['result'] not in statuses)):
                raise ValueError('Unexplained failure or unknown log status')
            for log in check['logs']:
                status = log['status']
                message = log['message']
                item = {'check_id': identifier, 'code': message['code'],
                        'status': status, 'font': check.get('filename'),
                        'message': message['message']}
                if status == 'FAIL' and (identifier, message['code']) in policy:
                    item['reason'] = policy[identifier, message['code']]
                    allowed.append(item)
                elif status in ('FAIL', 'ERROR', 'FATAL'):
                    failures.append(item)
                elif status == 'WARN':
                    warnings.append(item)
    return {'valid': not failures, 'failures': failures, 'allowed': allowed, 'warnings': warnings}


def run_checks(paths: list[Path], output: Path, allowlist: Path) -> dict:
    (output / 'summary.json').unlink(missing_ok=True)
    paths = sorted(set(p.resolve() for p in paths))
    if not paths:
        raise ValueError('No fonts to inspect')
    policy = load_policy(allowlist)
    output.mkdir(parents=True, exist_ok=True)
    fonts = [{'path': str(p), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in paths]
    result: dict = {'schema_version': 1, 'fontbakery_version': version('fontbakery'),
                   'profile': 'universal (includes opentype)', 'network': 'skipped',
                   'font_count': len(paths), 'fonts': fonts,
                   'allowlist_sha256': hashlib.sha256(allowlist.read_bytes()).hexdigest(),
                   'valid': True, 'groups': []}
    # Family checks must not combine unrelated Japanese families / Code and Mono.
    def inspect_group(index_directory):
        index, directory = index_directory
        group = [str(p) for p in paths if p.parent == directory]
        raw = output.resolve() / f'universal-{index:03d}.json'
        raw.unlink(missing_ok=True)  # A crashed invocation must not reuse old evidence.
        args = [sys.executable, '-m', 'fontbakery', 'check-universal', '--skip-network',
                '-q', '--json', str(raw), *group]
        process = subprocess.run(args, capture_output=True, text=True, timeout=3600)
        raw.with_suffix('.log').write_text(process.stdout + process.stderr)
        if process.returncode not in (0, 1) or not raw.is_file():
            raise ValueError(f'FontBakery invocation failed ({process.returncode}): {raw}')
        classified = classify(json.loads(raw.read_text()), policy)
        if process.returncode == 1 and not (classified['failures'] or classified['allowed']):
            raise ValueError(f'Unexplained FontBakery nonzero exit: {raw}')
        return {'directory': str(directory), 'report': str(raw),
                'returncode': process.returncode, **classified}

    # Bound memory use to two independent FontBakery processes. map preserves order.
    with ThreadPoolExecutor(max_workers=2) as pool:
        result['groups'] = list(pool.map(inspect_group, enumerate(sorted({p.parent for p in paths}))))
    result['valid'] = all(group['valid'] for group in result['groups'])
    if fonts != [{'path': str(p), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in paths]:
        raise ValueError('Font changed during FontBakery checks')
    (output / 'summary.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def main(argv=None):
    import argparse

    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build-dir', type=Path, default=root / 'build')
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--allowlist', type=Path, default=root / 'config/fontbakery-allowlist.json')
    args = parser.parse_args(argv)
    try:
        paths = [p for p in args.build_dir.rglob('*.ttf') if not p.name.startswith('.font-')]
        result = run_checks(paths, args.output_dir or args.build_dir / 'fontbakery', args.allowlist)
    except Exception as exc:
        result = {'valid': False, 'error': f'{type(exc).__name__}: {exc}'}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return int(not result['valid'])
