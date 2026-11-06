from pathlib import Path

from kumitype.config import load, targets


def test_default_matrix():
    config = load(Path(__file__).parents[2] / 'config/build.yaml')
    matrix = targets(config)
    assert len(matrix) == 504
    assert len(set(matrix)) == 504
    assert len({(t.base, t.japanese) for t in matrix}) == 42


def test_invalid_rendering_and_names_rejected(tmp_path):
    import pytest
    import yaml

    config = load(Path(__file__).parents[2] / 'config/build.yaml')
    path = tmp_path / 'build.yaml'
    for invalid in [0, -1, float('nan'), float('inf'), True, 'large']:
        config['rendering']['jp_scale'] = invalid
        path.write_text(yaml.safe_dump(config))
        with pytest.raises(ValueError):
            load(path)
    config['rendering']['jp_scale'] = 1
    config['project']['name'] = '../escape'
    path.write_text(yaml.safe_dump(config))
    with pytest.raises(ValueError, match='project.name'):
        load(path)


def test_nested_matrix_value_has_clear_error(tmp_path):
    import pytest
    import yaml

    config = load(Path(__file__).parents[2] / 'config/build.yaml')
    config['variants'] = [['code']]
    path = tmp_path / 'build.yaml'
    path.write_text(yaml.safe_dump(config))
    with pytest.raises(ValueError, match='scalar'):
        load(path)


def test_registry_allows_additional_japanese_family(tmp_path):
    import yaml

    from kumitype.config import Target
    from kumitype.metadata import expected_identity

    config = load(Path(__file__).parents[2] / 'config/build.yaml')
    config['japanese_fonts'] = ['custom']
    (tmp_path / 'fonts.yaml').write_text(yaml.safe_dump({
        'fonts': {'custom': {'family': 'Custom Japanese', 'output': 'CustomJP'}}}))
    path = tmp_path / 'build.yaml'
    path.write_text(yaml.safe_dump(config))
    loaded = load(path)
    target = Target('mono', 'custom', 400, 'normal')
    assert target in targets(loaded)
    assert expected_identity(target, loaded['project'])['family'] == 'KumiType CustomJP Mono'


def test_unicode_file_policy_and_inline_precedence(tmp_path):
    import yaml

    config = load(Path(__file__).parents[2] / 'config/build.yaml')
    config['unicode_overrides'] = {'03B1': 'japanese'}
    (tmp_path / 'unicode.yaml').write_text(yaml.safe_dump({'unicode_overrides': {
        '03B1': 'cascadia', '03B2': 'cascadia'}}))
    path = tmp_path / 'build.yaml'
    path.write_text(yaml.safe_dump(config))
    policy = load(path)['unicode_overrides']
    assert policy == {'03B1': 'japanese', '03B2': 'cascadia'}


def test_registry_rejects_known_reserved_font_names(tmp_path):
    import pytest
    import yaml

    config = load(Path(__file__).parents[2] / 'config/build.yaml')
    path = tmp_path / 'build.yaml'
    path.write_text(yaml.safe_dump(config))
    for reserved in ('Plex', 'Source', 'CascadiaCode'):
        (tmp_path / 'fonts.yaml').write_text(yaml.safe_dump({
            'fonts': {'plex': {'family': 'IBM Plex Sans JP', 'output': reserved}}}))
        with pytest.raises(ValueError, match='Reserved source font name'):
            load(path)
