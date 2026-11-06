from kumitype.provenance import implementation_digest


def test_implementation_digest_tracks_code_and_ignores_generated_files(tmp_path):
    (tmp_path / 'one.py').write_text('value = 1\n')
    first = implementation_digest(tmp_path)
    (tmp_path / 'font.ttf').write_bytes(b'generated')
    assert implementation_digest(tmp_path) == first
    (tmp_path / 'one.py').write_text('value = 2\n')
    assert implementation_digest(tmp_path) != first
