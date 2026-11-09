import hashlib
import json
import zipfile

import pytest

from kumitype import source_registry as registry


def fixture_source(tmp_path):
    artifact = tmp_path / 'font.zip'
    with zipfile.ZipFile(artifact, 'w') as bundle:
        bundle.writestr('font.ttf', b'ttf')
        bundle.writestr('font.otf', b'otf')
        bundle.writestr('OFL.txt', b'license')
    record = {'id': 'test', 'version': '1', 'format': 'zip',
              'url': 'https://example.org/font.zip',
              'sha256': hashlib.sha256(artifact.read_bytes()).hexdigest()}
    lock = tmp_path / 'lock.toml'
    lock.write_text('[[sources]]\n' + '\n'.join(f'{k}={json.dumps(v)}' for k, v in record.items()))
    return artifact, lock, tmp_path / 'source', tmp_path / 'cache'


def test_matching_installation_skips_extraction_and_inspection(tmp_path, monkeypatch):
    artifact, lock, source, cache = fixture_source(tmp_path)
    inspected = []
    def inspect(path):
        inspected.append(path.suffix)
        return {'path': str(path), 'codepoints': [32, 33, 34, 100]}
    monkeypatch.setattr(registry, 'inspect_font', inspect)
    registry.import_source(lock, 'test', artifact, source, cache)
    assert inspected == ['.ttf']
    manifest = source / 'test/1/source-manifest.json'
    before = manifest.read_bytes()
    def forbidden(*args):
        raise AssertionError('unchanged sources must not be reprocessed')
    monkeypatch.setattr(registry, 'inspect_font', forbidden)
    monkeypatch.setattr(registry, 'extract_zip', forbidden)
    registry.install_sources(lock, source, cache)
    assert manifest.read_bytes() == before


def test_explicit_otf_source_preserves_build_input(tmp_path, monkeypatch):
    artifact, lock, source, cache = fixture_source(tmp_path)
    lock.write_text(lock.read_text() + '\nfont_format="otf"\n')
    inspected = []
    def inspect(path):
        inspected.append(path.suffix)
        return {'path': str(path), 'codepoints': []}
    monkeypatch.setattr(registry, 'inspect_font', inspect)
    registry.import_source(lock, 'test', artifact, source, cache)
    assert inspected == ['.otf']


def test_codepoint_ranges_roundtrip_and_legacy_compatibility(tmp_path, monkeypatch):
    artifact, lock, source, cache = fixture_source(tmp_path)
    monkeypatch.setattr(registry, 'inspect_font', lambda path: {
        'path': str(path), 'codepoints': [32, 33, 34, 100]})
    registry.import_source(lock, 'test', artifact, source, cache)
    manifest = source / 'test/1/source-manifest.json'
    stored = json.loads(manifest.read_text())
    assert stored['fonts'][0]['codepoint_ranges'] == [[32, 34], [100, 100]]
    assert 'codepoints' not in stored['fonts'][0]
    assert registry.locked_manifests(source, lock)[0]['fonts'][0]['codepoints'] == [32, 33, 34, 100]
    stored['fonts'][0].pop('codepoint_ranges')
    stored['fonts'][0]['codepoints'] = [42]
    manifest.write_text(json.dumps(stored))
    assert registry.locked_manifests(source, lock)[0]['fonts'][0]['codepoints'] == [42]


@pytest.mark.parametrize('mutation', ['font', 'license', 'missing', 'lock', 'manifest'])
def test_changed_installation_is_reprocessed(tmp_path, monkeypatch, mutation):
    artifact, lock, source, cache = fixture_source(tmp_path)
    inspected = []
    def inspect(path):
        inspected.append(str(path))
        return {'path': str(path), 'codepoints': []}
    monkeypatch.setattr(registry, 'inspect_font', inspect)
    registry.import_source(lock, 'test', artifact, source, cache)
    folder = source / 'test/1'
    if mutation == 'font':
        (folder / 'font.ttf').write_bytes(b'corrupt')
    elif mutation == 'license':
        (folder / 'OFL.txt').write_bytes(b'corrupt')
    elif mutation == 'missing':
        (folder / 'font.ttf').unlink()
    elif mutation == 'lock':
        lock.write_text(lock.read_text().replace('example.org', 'new.example.org'))
    else:
        (folder / 'source-manifest.json').write_text('invalid json')
    registry.install_sources(lock, source, cache)
    assert len(inspected) == 2
    assert (folder / 'font.ttf').read_bytes() == b'ttf'
    assert (folder / 'OFL.txt').read_bytes() == b'license'


def test_direct_otf_import_keeps_existing_api(tmp_path, monkeypatch):
    artifact = tmp_path / 'font.otf'
    artifact.write_bytes(b'otf')
    lock = tmp_path / 'lock.toml'
    lock.write_text('[[sources]]\nid="test"\nversion="1"\nformat="otf"\n'
                    'url="https://example.org/font.otf"\nsha256="' +
                    hashlib.sha256(b'otf').hexdigest() + '"\n')
    monkeypatch.setattr(registry, 'inspect_font', lambda path: {
        'path': str(path), 'codepoints': []})
    result = registry.import_source(lock, 'test', artifact, tmp_path / 'source', tmp_path / 'cache')
    assert len(result['fonts']) == 1


@pytest.mark.parametrize('content', ['[]', 'null', '1'])
def test_nonobject_manifest_is_rebuilt(tmp_path, monkeypatch, content):
    artifact, lock, source, cache = fixture_source(tmp_path)
    monkeypatch.setattr(registry, 'inspect_font', lambda path: {'path': str(path), 'codepoints': []})
    registry.import_source(lock, 'test', artifact, source, cache)
    (source / 'test/1/source-manifest.json').write_text(content)
    result = registry.install_sources(lock, source, cache)
    assert len(result[0]['fonts']) == 1


def test_removed_lock_option_invalidates_manifest(tmp_path, monkeypatch):
    artifact, lock, source, cache = fixture_source(tmp_path)
    original = lock.read_text()
    lock.write_text(original + '\nfont_format="otf"\n')
    monkeypatch.setattr(registry, 'inspect_font', lambda path: {'path': str(path), 'codepoints': []})
    registry.import_source(lock, 'test', artifact, source, cache)
    lock.write_text(original)
    result = registry.install_sources(lock, source, cache)
    assert result[0]['fonts'][0]['path'].endswith('.ttf')


@pytest.mark.parametrize('mutation', ['hash', 'empty', 'missing-path'])
def test_manifest_font_inventory_must_match_files(tmp_path, monkeypatch, mutation):
    artifact, lock, source, cache = fixture_source(tmp_path)
    calls = []
    def inspect(path):
        calls.append(path)
        return {'path': str(path), 'codepoints': []}
    monkeypatch.setattr(registry, 'inspect_font', inspect)
    registry.import_source(lock, 'test', artifact, source, cache)
    manifest = source / 'test/1/source-manifest.json'
    data = json.loads(manifest.read_text())
    if mutation == 'hash':
        data['fonts'][0]['sha256'] = '0' * 64
    elif mutation == 'empty':
        data['fonts'] = []
    else:
        del data['fonts'][0]['path']
    manifest.write_text(json.dumps(data))
    registry.install_sources(lock, source, cache)
    assert len(calls) == 2
