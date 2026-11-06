import json

import pytest

from kumitype.source_registry import load_lock, locked_manifests


def write_lock(path, version='1.0'):
    path.write_text('[[sources]]\nid="font"\nversion="' + version +
                    '"\nsha256="' + 'a' * 64 + '"\nurl="https://example.org/font.ttf"\nformat="ttf"\n')


def test_version_cannot_escape_source_directory(tmp_path):
    path = tmp_path / 'lock.toml'
    write_lock(path, '../escape')
    with pytest.raises(ValueError):
        load_lock(path)


def test_stale_versions_ignored_and_provenance_checked(tmp_path):
    lock = tmp_path / 'lock.toml'
    write_lock(lock)
    source = tmp_path / 'source'
    stale = source / 'font/0.9'
    stale.mkdir(parents=True)
    (stale / 'source-manifest.json').write_text('{}')
    assert locked_manifests(source, lock) == []
    active = source / 'font/1.0'
    active.mkdir()
    record = load_lock(lock)[0]
    (active / 'source-manifest.json').write_text(json.dumps(record))
    assert locked_manifests(source, lock) == [record]
    record['sha256'] = 'b' * 64
    (active / 'source-manifest.json').write_text(json.dumps(record))
    with pytest.raises(ValueError, match='differs from lock'):
        locked_manifests(source, lock)


def test_explicit_update_preserves_other_sources(tmp_path):
    from kumitype.source_registry import update_lock

    lock = tmp_path / 'lock.toml'
    write_lock(lock)
    update_lock(lock, 'second', '2.0', 'https://example.org/second.ttf', 'b' * 64, 'ttf')
    assert [item['id'] for item in load_lock(lock)] == ['font', 'second']
    before = lock.read_bytes()
    with pytest.raises(ValueError):
        update_lock(lock, 'second', 'latest', 'https://example.org/font', 'b' * 64, 'ttf')
    assert lock.read_bytes() == before


def test_manual_import_verifies_hash_without_network(tmp_path, monkeypatch):
    import hashlib

    from kumitype.source_registry import import_source

    artifact = tmp_path / 'LICENSE'
    artifact.write_bytes(b'test license')
    record = {'id': 'font-license', 'version': '1.0',
              'url': 'https://example.org/LICENSE', 'format': 'text', 'filename': 'LICENSE',
              'sha256': hashlib.sha256(artifact.read_bytes()).hexdigest()}
    lock = tmp_path / 'lock.toml'
    lock.write_text('[[sources]]\n' + '\n'.join(f'{k}={json.dumps(v)}' for k, v in record.items()))
    def no_network(*args, **kwargs):
        raise AssertionError('network must not be used')
    monkeypatch.setattr('urllib.request.urlopen', no_network)
    result = import_source(lock, 'font-license', artifact, tmp_path / 'source', tmp_path / 'cache')
    assert result['fonts'] == []
    assert (tmp_path / 'source/font-license/1.0/LICENSE').read_bytes() == b'test license'
    artifact.write_bytes(b'changed')
    with pytest.raises(ValueError, match='SHA-256 mismatch'):
        import_source(lock, 'font-license', artifact, tmp_path / 'source', tmp_path / 'cache')


def test_diagnostics_reports_missing_version_and_file(tmp_path):
    from kumitype.source_registry import source_status

    lock = tmp_path / 'lock.toml'
    write_lock(lock)
    source = tmp_path / 'source'
    result = source_status(lock, source)
    assert result[0]['required_version'] == '1.0'
    assert not result[0]['ready']
    folder = source / 'font/1.0'
    folder.mkdir(parents=True)
    record = load_lock(lock)[0]
    record['fonts'] = [{'path': str(folder / 'missing.ttf'), 'sha256': 'a' * 64}]
    (folder / 'source-manifest.json').write_text(json.dumps(record))
    result = source_status(lock, source)
    assert 'Missing input file' in result[0]['errors'][0]


def test_donor_selection_groups_complementary_subsets(tmp_path):
    import hashlib

    from kumitype.builder import choose_donor

    source = tmp_path / 'source'
    folder = source / 'biz/1.0'
    folder.mkdir(parents=True)
    fonts = []
    for name, codepoints in [('one', [0x3042]), ('two', [0x3042, 0x20000]), ('duplicate', [0x3042])]:
        path = folder / (name + '.ttf')
        path.write_bytes(name.encode())
        fonts.append({'path': str(path), 'codepoints': codepoints, 'family': 'Test JP',
                      'weight': 400, 'italic': False, 'axes': [],
                      'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    record = {'id': 'biz', 'version': '1.0', 'url': 'https://example.org/font.zip',
              'sha256': 'a' * 64, 'format': 'zip'}
    lock = tmp_path / 'lock.toml'
    lock.write_text('[[sources]]\n' + '\n'.join(f'{k}={json.dumps(v)}' for k, v in record.items()))
    (folder / 'source-manifest.json').write_text(json.dumps({**record, 'fonts': fonts}))
    primary, info = choose_donor(source, 'biz', 400, lock)
    selected = {str(primary), *info['subset_paths']}
    coverage = {cp for font in fonts if font['path'] in selected for cp in font['codepoints']}
    assert coverage == {0x3042, 0x20000}
    assert len(selected) == 2
