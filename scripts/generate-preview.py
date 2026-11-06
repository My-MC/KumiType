#!/usr/bin/env python3
"""Generate an offline font comparison page next to built fonts."""
import argparse
import html
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--build-dir', type=Path, default=Path('build'))
parser.add_argument('--base')
parser.add_argument('--weight', type=int)
parser.add_argument('--style', choices=['normal', 'italic'])
parser.add_argument('--output', default='preview.html')
args = parser.parse_args()
root = args.build_dir
sample = Path('tests/rendering/sample.txt').read_text(encoding='utf-8')
styles = []
sections = []
for index, manifest_path in enumerate(sorted(root.rglob('*.json'))):
    font_path = manifest_path.with_suffix('.ttf')
    if not font_path.exists():
        continue
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    target = manifest['target']
    if any(value is not None and target[key] != value for key, value in
           [('base', args.base), ('weight', args.weight), ('style', args.style)]):
        continue
    alias = f'preview{index}'
    styles.append(f'@font-face{{font-family:{alias};src:url("{font_path.relative_to(root).as_posix()}")}}')
    label = html.escape(manifest['identity']['postscript_name'])
    sections.append(f'<section><h2>{label}</h2><pre style="font-family:{alias}">{html.escape(sample)}</pre></section>')
page = ('<!doctype html><html lang="ja"><meta charset="utf-8"><title>KumiType preview</title>'
        '<style>body{margin:2rem}pre{font-size:20px;line-height:1.6;font-variant-ligatures:normal}'
        + ''.join(styles) + '</style><h1>KumiType rendering samples</h1>'
        + ''.join(sections) + '</html>')
(root / args.output).write_text(page, encoding='utf-8')
