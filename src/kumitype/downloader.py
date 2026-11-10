"""Hash-verified source cache and bounded ZIP extraction."""
import hashlib
import http.client
import os
import socket
import ssl
import sys
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath


def sha256(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def _connect(address, timeout=15, source_address=None, **kwargs):
    """Try each resolved address with a bounded timeout, without global patches."""
    error = OSError('No addresses resolved')
    for family, kind, protocol, _, endpoint in socket.getaddrinfo(
            address[0], address[1], 0, socket.SOCK_STREAM):
        sock = socket.socket(family, kind, protocol)
        try:
            sock.settimeout(timeout)
            if source_address:
                sock.bind(source_address)
            sock.connect(endpoint)
            return sock
        except OSError as exc:
            error = exc
            sock.close()
    raise error


class _HTTPSRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not newurl.startswith('https://'):
            raise ValueError('Insecure download redirect')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _open(url: str, connect_timeout: float, read_timeout: float):
    class Connection(http.client.HTTPSConnection):
        def connect(self):
            self._create_connection = _connect
            super().connect()
            self.sock.settimeout(read_timeout)

    class Handler(urllib.request.HTTPSHandler):
        def https_open(self, req):
            return self.do_open(Connection, req, context=ssl.create_default_context())

    return urllib.request.build_opener(Handler(), _HTTPSRedirectHandler()).open(url, timeout=connect_timeout)


def fetch(url: str, digest: str, cache: Path, *, connect_timeout: float = 15,
          read_timeout: float = 60, attempts: int = 3, backoff: float = 1) -> Path:
    if len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest):
        raise ValueError('Expected lowercase SHA-256 digest')
    if not url.startswith('https://'):
        raise ValueError('Source URL must use HTTPS')
    cache.mkdir(parents=True, exist_ok=True)
    destination = cache / digest
    if destination.exists() and sha256(destination) == digest:
        return destination
    if connect_timeout <= 0 or read_timeout <= 0 or attempts < 1 or backoff < 0:
        raise ValueError('Timeouts and attempts must be positive; backoff must be nonnegative')
    for attempt in range(attempts):
        fd, temporary = tempfile.mkstemp(dir=cache, prefix='.download-')
        try:
            print(f'Download {url} (attempt {attempt + 1}/{attempts})', file=sys.stderr)
            with os.fdopen(fd, 'wb') as output:
                with _open(url, connect_timeout, read_timeout) as response:
                    if not response.geturl().startswith('https://'):
                        raise ValueError('Insecure download redirect')
                    total = 0
                    while chunk := response.read(1024 * 1024):
                        output.write(chunk)
                        total += len(chunk)
                        print(f'  {total} bytes', file=sys.stderr)
            if sha256(Path(temporary)) != digest:
                raise ValueError(f'SHA-256 mismatch: {url}')
            os.replace(temporary, destination)
            return destination
        except (OSError, urllib.error.URLError, http.client.HTTPException) as exc:
            if isinstance(exc, urllib.error.HTTPError) and exc.code not in (408, 429, 500, 502, 503, 504):
                raise
            if attempt + 1 == attempts:
                raise
            delay = backoff * 2 ** attempt
            print(f'  Retry in {delay:g}s: {exc}', file=sys.stderr)
            time.sleep(delay)
        finally:
            Path(temporary).unlink(missing_ok=True)
    raise AssertionError('unreachable')


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
