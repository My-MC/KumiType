"""Compare original and generated fonts using the HarfBuzz command line."""
import json
import shutil
import subprocess
from pathlib import Path

SAMPLES = ('!=', '==', '===', '=>', '->', '<=', '>=', '&&', '||')


def compare_shaping(base: Path, generated: Path, executable='hb-shape') -> dict:
    if not shutil.which(executable):
        return {'status': 'unavailable', 'errors': [], 'samples': [],
                'reason': 'hb-shape is not installed'}
    samples: list[dict] = []
    errors = []
    for text in SAMPLES:
        shaped = []
        for path in (base, generated):
            result = subprocess.run(
                [executable, '--output-format=json', '--no-glyph-names',
                 '--features=calt=1,liga=1', '--', str(path), text],
                capture_output=True, text=True, check=False, timeout=30)
            if result.returncode:
                return {'status': 'failed', 'errors': [result.stderr.strip()], 'samples': samples}
            shaped.append(json.loads(result.stdout))
        equal = shaped[0] == shaped[1]
        samples.append({'text': text, 'equal': equal, 'base': shaped[0], 'output': shaped[1]})
        if not equal:
            errors.append(f'Shaping differs from original: {text}')
    return {'status': 'passed' if not errors else 'failed', 'errors': errors, 'samples': samples}
