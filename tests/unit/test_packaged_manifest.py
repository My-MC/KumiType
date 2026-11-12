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


def test_execution_tuning_is_not_distribution_identity():
    original = {'config': {'project': {'version': '0.1.0'},
                            'build': {'output_format': 'ttf', 'jobs': 'auto', 'fail_on_error': True}},
                'config_sha256': 'diagnostic-only'}
    tuned = copy.deepcopy(original)
    tuned['config']['build'].update(jobs=2, worker_memory_mb=640, max_jobs=4, fail_on_error=False)
    assert packaged_manifest(tuned) == packaged_manifest(original)
    assert original['config']['build']['jobs'] == 'auto'
    projected = packaged_manifest(tuned)
    assert projected['config']['build'] == {'output_format': 'ttf'}
    assert packaged_manifest(projected) == projected
    tuned['config']['build']['output_format'] = 'other-content-format'
    assert packaged_manifest(tuned)['config_sha256'] != projected['config_sha256']


def test_runtime_only_build_block_matches_omitted_block():
    manifest = {'config': {}, 'config_sha256': 'diagnostic'}
    tuned = {'config': {'build': {'jobs': 'auto', 'worker_memory_mb': 768}},
             'config_sha256': 'other-diagnostic'}
    assert packaged_manifest(manifest) == packaged_manifest(tuned)


def test_source_manifest_projection_removes_nested_absolute_font_paths(tmp_path):
    record = {'id': 'donor', 'version': '1', 'url': 'https://example.org/donor',
              'sha256': 'archive-hash', 'fonts': [{'path': str(tmp_path / 'font.ttf'),
                                                'sha256': 'font-hash', 'weight': 400}]}
    projected = packaged_manifest(record)
    assert projected == {**record, 'fonts': [{'sha256': 'font-hash', 'weight': 400}]}
