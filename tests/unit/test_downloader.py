import hashlib
import zipfile

import pytest

from kumitype.downloader import extract_zip, fetch


def test_verified_cache_needs_no_network(tmp_path):
    content = b'cached source'
    digest = hashlib.sha256(content).hexdigest()
    (tmp_path / digest).write_bytes(content)
    assert fetch('https://invalid.example/font', digest, tmp_path).read_bytes() == content


def test_zip_traversal_rejected_before_writes(tmp_path):
    archive = tmp_path / 'bad.zip'
    with zipfile.ZipFile(archive, 'w') as bundle:
        bundle.writestr('safe.txt', 'safe')
        bundle.writestr('../escape.txt', 'unsafe')
    with pytest.raises(ValueError, match='Unsafe'):
        extract_zip(archive, tmp_path / 'out')
    assert not (tmp_path / 'out/safe.txt').exists()


def test_zip_size_limit(tmp_path):
    archive = tmp_path / 'large.zip'
    with zipfile.ZipFile(archive, 'w') as bundle:
        bundle.writestr('font.ttf', '12345')
    with pytest.raises(ValueError, match='size limit'):
        extract_zip(archive, tmp_path / 'out', max_bytes=4)


def test_failed_download_hash_does_not_poison_cache(tmp_path, monkeypatch):
    import io

    class Response(io.BytesIO):
        def geturl(self):
            return 'https://example.org/font'

    digest = hashlib.sha256(b'expected').hexdigest()
    monkeypatch.setattr('kumitype.downloader._open', lambda *a, **k: Response(b'wrong'))
    with pytest.raises(ValueError, match='SHA-256 mismatch'):
        fetch('https://example.org/font', digest, tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_corrupt_cache_is_replaced_only_after_verification(tmp_path, monkeypatch):
    import io

    class Response(io.BytesIO):
        def geturl(self):
            return 'https://example.org/font'

    content = b'valid content'
    digest = hashlib.sha256(content).hexdigest()
    (tmp_path / digest).write_bytes(b'corrupt')
    monkeypatch.setattr('kumitype.downloader._open', lambda *a, **k: Response(content))
    result = fetch('https://example.org/font', digest, tmp_path)
    assert result.read_bytes() == content
    assert len(list(tmp_path.iterdir())) == 1


def test_archive_symlink_rejected(tmp_path):
    archive = tmp_path / 'links.zip'
    member = zipfile.ZipInfo('link')
    member.create_system = 3
    member.external_attr = 0o120777 << 16
    with zipfile.ZipFile(archive, 'w') as bundle:
        bundle.writestr(member, '../outside')
    with pytest.raises(ValueError, match='symlinks'):
        extract_zip(archive, tmp_path / 'out')
