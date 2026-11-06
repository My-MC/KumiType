"""Hash-verified source cache and bounded ZIP extraction."""
import hashlib
import os
import shutil
import tempfile
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath


def sha256(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def fetch(url: str, digest: str, cache: Path) -> Path:
    if len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest):
        raise ValueError('Expected lowercase SHA-256 digest')
    if not url.startswith('https://'):
        raise ValueError('Source URL must use HTTPS')
    cache.mkdir(parents=True, exist_ok=True)
    destination = cache / digest
    if destination.exists() and sha256(destination) == digest:
        return destination
    fd, temporary = tempfile.mkstemp(dir=cache, prefix='.download-')
    try:
        with os.fdopen(fd, 'wb') as output:
            with urllib.request.urlopen(url, timeout=120) as response:
                if not response.geturl().startswith('https://'):
                    raise ValueError('Insecure download redirect')
                shutil.copyfileobj(response, output)
        if sha256(Path(temporary)) != digest:
            raise ValueError(f'SHA-256 mismatch: {url}')
        os.replace(temporary, destination)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return destination


def extract_zip(archive: Path, destination: Path, max_bytes: int = 2_000_000_000) -> None:
    with zipfile.ZipFile(archive) as bundle:
        total = 0
        for member in bundle.infolist():
            path = PurePosixPath(member.filename)
            if path.is_absolute() or '..' in path.parts or '\\' in member.filename:
                raise ValueError(f'Unsafe archive path: {member.filename}')
            if (member.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError('Archive symlinks are not supported')
            total += member.file_size
            if total > max_bytes:
                raise ValueError('Archive exceeds extraction size limit')
            target = (destination / member.filename).resolve()
            if not target.is_relative_to(destination.resolve()):
                raise ValueError('Archive path escapes destination')
        bundle.extractall(destination)
