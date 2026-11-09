"""Portable distribution provenance without mutating diagnostic build records."""
import copy
import hashlib
import json

from kumitype.packager import packaged_manifest


def test_packaged_manifest_keeps_content_identity_but_not_storage(tmp_path):
    manifest = {
        'generated_at': 'now', 'duration_seconds': 12, 'process_peak_rss_kib': 999,
        'config': {
            '_project_root': str(tmp_path),
            'paths': {'source': str(tmp_path / 'source'), 'cache': str(tmp_path / 'cache')},
            'sources': {'lock': str(tmp_path / 'pins.toml'), 'cascadia': {'version': '1'}},
            'font_overrides': {'biz': {'subset_files': [str(tmp_path / 'extra.ttf')],
                                       'subset_licenses': [str(tmp_path / 'OFL.txt')],
                                       'jp_scale': 0.9}},
        },
        'config_sha256': 'local-config-hash',
        'sources': [{'path': str(tmp_path / 'donor.ttf'), 'sha256': 'font-hash'}],
        'additional_licenses': [{'path': str(tmp_path / 'OFL.txt'), 'sha256': 'license-hash'}],
        'builder': {'implementation_sha256': 'implementation-hash'},
    }
    original = copy.deepcopy(manifest)
    projected = packaged_manifest(manifest)
    assert manifest == original
    assert str(tmp_path) not in json.dumps(projected)
    assert projected['sources'] == [{'sha256': 'font-hash'}]
    assert projected['additional_licenses'] == [{'sha256': 'license-hash'}]
    assert projected['config']['font_overrides']['biz'] == {'jp_scale': 0.9}
    assert projected['builder'] == manifest['builder']
    assert projected['config_sha256'] == hashlib.sha256(json.dumps(
        projected['config'], sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()
    assert packaged_manifest(projected) == projected
    manifest['config']['font_overrides']['biz']['jp_scale'] = 0.8
    assert packaged_manifest(manifest)['config_sha256'] != projected['config_sha256']


def test_source_manifest_projection_removes_nested_absolute_font_paths(tmp_path):
    record = {'id': 'donor', 'version': '1', 'url': 'https://example.org/donor',
              'sha256': 'archive-hash', 'fonts': [{'path': str(tmp_path / 'font.ttf'),
                                                'sha256': 'font-hash', 'weight': 400}]}
    projected = packaged_manifest(record)
    assert projected == {**record, 'fonts': [{'sha256': 'font-hash', 'weight': 400}]}
