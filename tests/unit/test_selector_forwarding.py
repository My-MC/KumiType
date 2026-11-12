"""Exercise Make and workflow selector forwarding without expensive font work."""
import json
import os
from pathlib import Path
import subprocess

import yaml

ROOT = Path(__file__).resolve().parents[2]


def test_make_forwards_all_selectors_as_single_arguments(tmp_path):
    recorder = tmp_path / 'record.py'
    recorder.write_text('import json, sys\nprint(json.dumps(sys.argv[1:]))\n')
    import sys
    result = subprocess.run(['make', '--no-print-directory', '-s', 'fonts', 'validate',
                             'audit', 'package', f'PYTHON={sys.executable} {recorder}',
                             'BASE=code,mono', 'JP=biz,plex',
                             'FAMILY=KumiType BIZ Mono NF', 'WEIGHT=400,700', 'STYLE=italic'],
                            cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    calls = [json.loads(line) for line in result.stdout.splitlines()]
    assert [call[2] for call in calls] == ['build', 'validate', 'audit', 'package']
    for call in calls:
        for option, value in [('--base', 'code,mono'), ('--jp', 'biz,plex'),
                              ('--family', 'KumiType BIZ Mono NF'),
                              ('--weight', '400,700'), ('--style', 'italic')]:
            assert call[call.index(option) + 1] == value


def test_workflow_shell_preserves_selector_arguments(tmp_path):
    workflow = yaml.safe_load((ROOT / '.github/workflows/build.yaml').read_text())
    dispatch = workflow.get('on', workflow.get(True))['workflow_dispatch']
    assert set(dispatch['inputs']) == {'families', 'bases', 'japanese_fonts'}
    caller = workflow['jobs']['build']
    assert caller['uses'] == './.github/workflows/build-fonts.yaml'
    assert caller['with'] == {key: '${{ inputs.' + key + ' }}' for key in dispatch['inputs']}
    reusable = yaml.safe_load((ROOT / '.github/workflows/build-fonts.yaml').read_text())
    step = next(step for step in reusable['jobs']['build']['steps']
                if step.get('name') == 'Build, audit, validate and package selected families')
    assert '${{ inputs.' not in step['run']  # Inputs must enter through env, not shell interpolation.
    for families, bases, jp in [('', '', ''), ('KumiType BIZ Mono NF,mono/plex', 'mono-nf,mono', 'biz,plex'),
                                ('$(touch INJECTION)', '', '')]:
        environment = {**os.environ, 'FAMILIES': families, 'BASES': bases, 'JAPANESE_FONTS': jp}
        # Override uv with a shell function that prints each invocation as a JSON array.
        script = '''uv() { python -c 'import json,sys; print(json.dumps(sys.argv[1:]))' "$@"; }
''' + step['run']
        result = subprocess.run(['bash', '-e', '-c', script], env=environment, cwd=tmp_path,
                                capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        calls = [json.loads(line) for line in result.stdout.splitlines()]
        assert [call[2:4] for call in calls] == [['kumitype', 'list'], ['python', 'scripts/release.py']]
        for call in calls:
            for option, value in [('--family', families), ('--base', bases), ('--jp', jp)]:
                if value:
                    assert call[call.index(option) + 1] == value
                else:
                    assert option not in call
        assert not (tmp_path / 'INJECTION').exists()
