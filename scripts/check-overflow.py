#!/usr/bin/env python3
"""Summarize outline overflow by Unicode width and category for tuning."""
import argparse
import json
import unicodedata
from collections import Counter
from pathlib import Path

from kumitype.artifacts import write_text

parser = argparse.ArgumentParser()
parser.add_argument('--build-dir', type=Path, default=Path('build'))
args = parser.parse_args()
results = []
for path in sorted(args.build_dir.rglob('*.json')):
    if not path.with_suffix('.ttf').exists():
        continue
    manifest = json.loads(path.read_text(encoding='utf-8'))
    codepoints = manifest['merge']['overflow_codepoints']
    results.append({'path': str(path.with_suffix('.ttf')),
                    'width_classes': dict(Counter(unicodedata.east_asian_width(chr(cp)) for cp in codepoints)),
                    'characters': [{'codepoint': f'U+{cp:04X}',
                                    'name': unicodedata.name(chr(cp), 'UNNAMED'),
                                    'width': unicodedata.east_asian_width(chr(cp)),
                                    'category': unicodedata.category(chr(cp))} for cp in codepoints]})
write_text(args.build_dir / 'overflow-report.json', json.dumps(results, indent=2))
print(f'Analyzed {len(results)} outputs; see overflow-report.json')
