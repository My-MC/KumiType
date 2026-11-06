"""Configuration loading and deterministic target expansion."""
from dataclasses import dataclass
from itertools import product
from pathlib import Path
import math
import re

import yaml

VARIANTS = ('code', 'code-pl', 'code-nf', 'mono', 'mono-pl', 'mono-nf')
JAPANESE_FONTS = ('plex', 'biz', 'noto', 'line-seed', 'mplus1', 'mplus2', 'zen-kaku')
WEIGHTS = (200, 300, 350, 400, 600, 700)
STYLES = ('normal', 'italic')


@dataclass(frozen=True)
class Target:
    base: str
    japanese: str
    weight: int
    style: str


def load(path: str | Path) -> dict:
    try:
        with Path(path).open(encoding='utf-8') as stream:
            data = yaml.safe_load(stream)
    except yaml.YAMLError as exc:
        raise ValueError(f'Invalid YAML in {path}: {exc}') from exc
    if not isinstance(data, dict):
        raise ValueError('Build configuration must be a mapping')
    unicode_path = Path(path).parent / 'unicode.yaml'
    if unicode_path.exists():
        try:
            with unicode_path.open(encoding='utf-8') as stream:
                unicode_data = yaml.safe_load(stream)
        except yaml.YAMLError as exc:
            raise ValueError(f'Invalid Unicode policy YAML: {exc}') from exc
        if not isinstance(unicode_data, dict) or not isinstance(unicode_data.get('unicode_overrides'), dict):
            raise ValueError('unicode.yaml: expected unicode_overrides mapping')
        local = data.get('unicode_overrides', {})
        if not isinstance(local, dict):
            raise ValueError('unicode_overrides: expected a mapping')
        data['unicode_overrides'] = {**unicode_data['unicode_overrides'], **local}
    registry_path = Path(path).parent / 'fonts.yaml'
    registry = {}
    if registry_path.exists():
        with registry_path.open(encoding='utf-8') as stream:
            registry_data = yaml.safe_load(stream)
        if not isinstance(registry_data, dict) or not isinstance(registry_data.get('fonts'), dict):
            raise ValueError('fonts.yaml: expected fonts mapping')
        registry = registry_data['fonts']
        outputs = set()
        for identifier, entry in registry.items():
            if not isinstance(identifier, str) or not re.fullmatch(r'[a-z0-9-]+', identifier):
                raise ValueError(f'Invalid font registry ID: {identifier}')
            if not isinstance(entry, dict) or not isinstance(entry.get('output'), str):
                raise ValueError(f'Invalid registry entry: {identifier}')
            if not re.fullmatch(r'[A-Za-z][A-Za-z0-9]*', entry['output']) or entry['output'] in outputs:
                raise ValueError(f'Invalid or duplicate font output name: {identifier}')
            if entry['output'].casefold() in ('plex', 'source', 'cascadia', 'cascadiacode'):
                raise ValueError(f'Reserved source font name in registry: {identifier}')
            outputs.add(entry['output'])
        data['_font_registry'] = registry
    allowed_fonts = tuple(registry) if registry else JAPANESE_FONTS
    for key, allowed in [('variants', VARIANTS), ('japanese_fonts', allowed_fonts),
                         ('weights', WEIGHTS), ('styles', STYLES)]:
        values = data.get(key)
        if not isinstance(values, list) or not values:
            raise ValueError(f'{key}: expected a nonempty list')
        if any(not isinstance(v, (str, int)) or isinstance(v, bool) for v in values):
            raise ValueError(f'{key}: expected scalar values')
        if len(set(values)) != len(values) or any(v not in allowed for v in values):
            raise ValueError(f'{key}: unsupported or duplicate values: {values}')
    for key in ('project', 'sources', 'rendering', 'build', 'font_overrides', 'unicode_overrides'):
        if key in data and not isinstance(data[key], dict):
            raise ValueError(f'{key}: expected a mapping')
    project = data.get('project', {})
    name = project.get('name', '')
    if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9 ]*', name):
        raise ValueError('project.name: expected a Latin name without path separators')
    if 'cascadia' in name.lower():
        raise ValueError('project.name: reserved source family name is prohibited')
    if registry:
        project['font_names'] = {identifier: entry['output'] for identifier, entry in registry.items()}
    if not isinstance(project.get('version'), str):
        raise ValueError('project.version: expected a quoted version string')
    if data.get('build', {}).get('output_format', 'ttf') != 'ttf':
        raise ValueError('build.output_format: only static ttf output is supported')
    rendering_groups = [data.get('rendering', {})]
    for identifier, override in data.get('font_overrides', {}).items():
        if identifier not in allowed_fonts or not isinstance(override, dict):
            raise ValueError(f'Invalid font override: {identifier}')
        rendering_groups.append(override)
    for rendering in rendering_groups:
        for key in ('jp_scale', 'baseline_offset', 'halfwidth_kana_scale'):
            if key in rendering:
                value = rendering[key]
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                    raise ValueError(f'{key}: expected a finite number')
                if key in ('jp_scale', 'halfwidth_kana_scale') and value <= 0:
                    raise ValueError(f'{key} must be positive')
    for cp, preference in data.get('unicode_overrides', {}).items():
        try:
            codepoint = int(str(cp), 16)
        except ValueError as exc:
            raise ValueError(f'Invalid hexadecimal codepoint: {cp}') from exc
        if not 0 <= codepoint <= 0x10FFFF or 0xD800 <= codepoint <= 0xDFFF:
            raise ValueError(f'Invalid Unicode scalar: {cp}')
        if preference not in ('cascadia', 'japanese'):
            raise ValueError(f'Invalid Unicode preference: {preference}')
    return data


def targets(config: dict) -> list[Target]:
    return [Target(*values) for values in product(
        config['variants'], config['japanese_fonts'], config['weights'], config['styles'])]
