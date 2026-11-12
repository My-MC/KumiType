"""Release metadata and artifact guardrails, without network access."""
import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[2] / 'scripts/release-support.py'


def support():
    assert SCRIPT.exists(), 'Release support script is not implemented'
    spec = importlib.util.spec_from_file_location('release_support', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_matrix_uses_validated_registry_ids():
    from kumitype.config import load
    config = load(SCRIPT.parents[1] / 'config/build.yaml')
    assert support().release_matrix(config) == {'jp': list(config['_font_registry'])}
    config['japanese_fonts'] = ['plex']
    with pytest.raises(ValueError, match='registry'):
        support().release_matrix(config)


def test_assemble_exact_inventory_and_checksums(tmp_path):
    import hashlib
    import json
    import zipfile
    from kumitype.config import load
    from kumitype.selection import target_path

    config = load(SCRIPT.parents[1] / 'config/build.yaml')
    config.update(variants=['mono'], japanese_fonts=['biz'], weights=[400], styles=['normal'])
    from kumitype.config import targets
    path = target_path(tmp_path / 'build', config, targets(config)[0])
    shard = tmp_path / 'artifacts' / 'font-build-biz'
    manifest = shard / 'build' / path.relative_to(tmp_path / 'build').with_suffix('.json')
    manifest.parent.mkdir(parents=True)
    payload = b'synthetic inventory test; not a font'
    digest = hashlib.sha256(payload).hexdigest()
    manifest.write_text(json.dumps({'sha256': digest}))
    dist = shard / 'dist'
    dist.mkdir()
    archive = dist / 'KumiTypeBIZ-Mono.zip'
    with zipfile.ZipFile(archive, 'w') as z:
        z.writestr(path.name, payload)
    result = support().assemble(config, tmp_path / 'artifacts', tmp_path / 'output')
    assert result == {'archives': 1, 'fonts': 1}
    restored = tmp_path / 'output' / 'build' / path.relative_to(tmp_path / 'build')
    assert restored.read_bytes() == payload
    assert (tmp_path / 'output/dist/SHA256SUMS').read_text() == (
        hashlib.sha256(archive.read_bytes()).hexdigest() + '  ' + archive.name + '\n')
    with zipfile.ZipFile(archive, 'a') as z:
        z.writestr('extra.ttf', b'extra')
    with pytest.raises(ValueError, match='inventory'):
        support().assemble(config, tmp_path / 'artifacts', tmp_path / 'bad-output')


def test_cli_preflight_dry_run_outputs_matrix_notes_and_version(tmp_path):
    import json
    import shutil
    import subprocess
    import sys
    import yaml

    shutil.copytree(SCRIPT.parents[1] / 'config', tmp_path / 'config')
    config_path = tmp_path / 'config/build.yaml'
    config = yaml.safe_load(config_path.read_text())
    config['project']['version'] = '1.2.3'
    config_path.write_text(yaml.safe_dump(config))
    (tmp_path / 'pyproject.toml').write_text('[project]\nversion = "1.2.3"\n')
    changelog = tmp_path / 'CHANGELOG.md'
    changelog.write_text('## [Unreleased]\n\n### 追加\n\n- Fixture.\n')
    command = [sys.executable, str(SCRIPT), 'preflight', '--output', str(tmp_path / 'notes')]
    result = subprocess.run([*command, '--dry-run'], cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data['version'] == '1.2.3'
    assert len(data['matrix']['jp']) == 7
    assert '追加' in (tmp_path / 'notes/release-notes.md').read_text()
    strict = subprocess.run([*command, '--tag', 'v1.2.3'], cwd=tmp_path, capture_output=True, text=True)
    assert strict.returncode != 0
    assert 'CHANGELOG' in strict.stderr
    changelog.write_text('## [Unreleased]\n\n## [1.2.3] - 2026-11-12\n\n- Released.\n')
    for tag in ['v1.2.3', 'v1.2.3-rc.1']:
        released = subprocess.run([*command, '--tag', tag], cwd=tmp_path, capture_output=True, text=True)
        assert released.returncode == 0, released.stderr
        assert (tmp_path / 'notes/release-notes.md').read_text() == '- Released.\n'


CHANGELOG = '''# Changelog

## [Unreleased]

### Added

- New work.

## [0.1.0] - 2026-11-12

### Added

- First release.

## [0.0.1] - 2026-01-01

- Old.

[0.1.0]: https://example.com
'''


def test_extract_only_selected_release_section():
    assert support().changelog_notes(CHANGELOG, '0.1.0') == '### Added\n\n- First release.\n'


def test_unreleased_fallback_requires_explicit_dry_run():
    text = CHANGELOG.split('## [0.1.0]')[0]
    with pytest.raises(ValueError, match='CHANGELOG'):
        support().changelog_notes(text, '0.1.0')
    assert support().changelog_notes(text, '0.1.0', dry_run=True) == '### Added\n\n- New work.\n'


def test_missing_version_does_not_use_another_release():
    with pytest.raises(ValueError, match='CHANGELOG'):
        support().changelog_notes(CHANGELOG, '0.2.0')


@pytest.mark.parametrize('text', ['## [0.1.0] - 2026-02-30\n\n- Invalid date.',
                                '## [0.1.0] - 2026-11-12\n\n',
                                '## [0.1.0] - 2026-11-12\n- A\n## [0.1.0] - 2026-11-12\n- B'])
def test_invalid_or_ambiguous_release_section(text):
    with pytest.raises(ValueError, match='CHANGELOG'):
        support().changelog_notes(text, '0.1.0')


@pytest.mark.parametrize('tag', ['v0.1.0', 'v0.1.0-rc.1', 'v0.1.0-beta.2'])
def test_version_matches_stable_and_prerelease(tag):
    assert support().check_version(tag, '0.1.0', '0.1.0') == '0.1.0'


@pytest.mark.parametrize('tag,build,package', [
    ('v0.2.0', '0.1.0', '0.1.0'),
    ('v0.1.0', '0.1.0', '0.2.0'),
    ('0.1.0', '0.1.0', '0.1.0'),
    ('v01.1.0', '01.1.0', '01.1.0'),
    ('v0.1.0-', '0.1.0', '0.1.0'),
    ('v0.1.0-rc..1', '0.1.0', '0.1.0'),
    ('v0.1.0-01', '0.1.0', '0.1.0'),
    ('v0.1.0\n', '0.1.0', '0.1.0'),
])
def test_version_rejects_mismatch_and_malformed_tag(tag, build, package):
    with pytest.raises(ValueError, match='version|tag'):
        support().check_version(tag, build, package)
