import pytest

from kumitype.artifacts import save_font, write_text


class Font:
    def save(self, path):
        path.write_bytes(b'new')


def test_failed_validation_preserves_existing_output(tmp_path):
    path = tmp_path / 'font.ttf'
    path.write_bytes(b'good')
    with pytest.raises(ValueError):
        save_font(Font(), path, lambda _: {'valid': False, 'errors': ['bad']})
    assert path.read_bytes() == b'good'
    assert list(tmp_path.iterdir()) == [path]


def test_successful_artifact_replacement(tmp_path):
    path = tmp_path / 'font.ttf'
    save_font(Font(), path, lambda _: {'valid': True, 'errors': []})
    assert path.read_bytes() == b'new'
    manifest = path.with_suffix('.json')
    write_text(manifest, '{}')
    assert manifest.read_text() == '{}'
    assert len(list(tmp_path.iterdir())) == 2


def test_archive_publication_failure_keeps_previous_file(tmp_path):
    from kumitype.artifacts import atomic_output

    path = tmp_path / 'family.zip'
    path.write_bytes(b'previous archive')
    with pytest.raises(RuntimeError):
        with atomic_output(path) as temporary:
            temporary.write_bytes(b'incomplete archive')
            raise RuntimeError('compression failed')
    assert path.read_bytes() == b'previous archive'
    assert list(tmp_path.iterdir()) == [path]
    with atomic_output(path) as temporary:
        temporary.write_bytes(b'complete archive')
    assert path.read_bytes() == b'complete archive'
