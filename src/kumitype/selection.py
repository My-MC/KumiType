"""Shared matrix selectors; execution settings and provenance stay unchanged."""
from dataclasses import asdict, dataclass
import re

from .config import Target, targets
from .metadata import JP_NAMES, expected_identity

OPTIONS = {'base': 'variants', 'jp': 'japanese_fonts', 'weight': 'weights',
           'style': 'styles', 'family': None}


def add_options(parser):
    for name in OPTIONS:
        parser.add_argument('--' + name, action='append', metavar='VALUE',
                            help='Repeat or use commas; omitted dimensions select all configured values')


def split_values(values):
    return list(dict.fromkeys(item.strip() for value in (values or []) for item in value.split(',')))


@dataclass
class Selection:
    selectors: dict
    targets: list[Target]
    families: list[dict]

    @property
    def specified(self):
        return any(self.selectors.values())

    def summary(self):
        return {'selectors': self.selectors, 'target_count': len(self.targets),
                'family_count': len(self.families), 'families': self.families}


def select(config, args):
    selectors = {name: split_values(getattr(args, name, None)) for name in OPTIONS}
    matrix = targets(config)
    family_names = {(t.base, t.japanese): expected_identity(t, config['project'])['family']
                    for t in matrix}
    available = {name: list(map(str, config[key])) for name, key in OPTIONS.items() if key}
    available['family'] = [f'{base}/{jp} ({name})' for (base, jp), name in family_names.items()]

    def error(message):
        choices = '\n'.join(f'  --{name}: {", ".join(values)}' for name, values in available.items())
        raise ValueError(f'{message}\nSelectable values:\n{choices}')

    for name in available.keys() - {'family'}:
        unknown = set(selectors[name]) - set(available[name])
        if unknown:
            error(f'Unknown --{name}: {", ".join(sorted(unknown))}')
    def normalize(value):
        return re.sub(r'[\s-]+', '', value.casefold())
    aliases = {}
    for pair, name in family_names.items():
        aliases[normalize('/'.join(pair))] = pair
        aliases[normalize(name)] = pair
    pairs = set()
    for value in selectors['family']:
        matched = aliases.get(normalize(value))
        if matched is None:
            error(f'Unknown --family: {value}')
        else:
            pairs.add(matched)
    selected = [t for t in matrix
                if (not selectors['base'] or t.base in selectors['base'])
                and (not selectors['jp'] or t.japanese in selectors['jp'])
                and (not selectors['weight'] or str(t.weight) in selectors['weight'])
                and (not selectors['style'] or t.style in selectors['style'])
                and (not pairs or (t.base, t.japanese) in pairs)]
    if not selected:
        error('Selectors match zero targets')
    families = []
    for pair, name in family_names.items():
        count = sum((t.base, t.japanese) == pair for t in selected)
        if count:
            families.append({'id': '/'.join(pair), 'name': name, 'target_count': count})
    return Selection(selectors, selected, families)


def target_path(root, config, target):
    """Canonical output location shared by scoped artifact consumers."""
    variant = target.base.replace('-pl', 'PL').replace('-nf', 'NF')
    variant = variant[0].upper() + variant[1:]
    name = expected_identity(target, config['project'])['postscript_name']
    return root / config['project'].get('font_names', JP_NAMES)[target.japanese] / variant / (name + '.ttf')


def listing(selection):
    return {**selection.summary(), 'targets': [asdict(t) for t in selection.targets]}
