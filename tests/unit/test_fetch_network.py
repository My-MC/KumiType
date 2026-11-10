import hashlib
import io
import socket
import urllib.error

import pytest

from kumitype import downloader


class Response(io.BytesIO):
    headers = {}
    code = 200
    msg = 'OK'

    def info(self):
        return self.headers

    def geturl(self):
        return 'https://example.org/font'


def test_download_retries_with_exponential_backoff(tmp_path, monkeypatch, capsys):
    content = b'font'
    attempts, delays = [], []

    def open_source(url, connect_timeout, read_timeout):
        attempts.append((connect_timeout, read_timeout))
        if len(attempts) < 3:
            raise urllib.error.URLError(TimeoutError('timeout'))
        return Response(content)

    monkeypatch.setattr('urllib.request.urlopen', lambda *a, **k: pytest.fail('legacy unbounded transport'))
    monkeypatch.setattr(downloader, '_open', open_source, raising=False)
    monkeypatch.setattr('time.sleep', delays.append)
    digest = hashlib.sha256(content).hexdigest()
    assert downloader.fetch('https://example.org/font', digest, tmp_path).read_bytes() == content
    assert attempts == [(15, 60)] * 3
    assert delays == [1, 2]
    assert '4 bytes' in capsys.readouterr().err
    assert not list(tmp_path.glob('.download-*'))


def test_connection_falls_back_between_families(monkeypatch):
    addresses = [(socket.AF_INET6, socket.SOCK_STREAM, 6, '', ('::1', 443, 0, 0)),
                 (socket.AF_INET, socket.SOCK_STREAM, 6, '', ('127.0.0.1', 443))]
    monkeypatch.setattr(socket, 'getaddrinfo', lambda *a: addresses)
    events = []

    class Socket:
        def __init__(self, family, *args):
            self.family = family

        def settimeout(self, timeout):
            events.append(('timeout', timeout))

        def connect(self, address):
            events.append(('connect', address))
            if self.family == socket.AF_INET6:
                raise TimeoutError('IPv6 stalled')

        def close(self):
            events.append(('close', self.family))

    monkeypatch.setattr(socket, 'socket', Socket)
    result = downloader._connect(('example.org', 443), 15)
    assert result.family == socket.AF_INET
    assert events == [('timeout', 15), ('connect', ('::1', 443, 0, 0)),
                      ('close', socket.AF_INET6), ('timeout', 15),
                      ('connect', ('127.0.0.1', 443))]


@pytest.mark.parametrize('failure', [TimeoutError('read stalled'),
    urllib.error.HTTPError('https://example.org/font', 503, 'unavailable', {}, None)])
def test_retry_exhaustion_keeps_existing_cache(tmp_path, monkeypatch, failure):
    digest = hashlib.sha256(b'expected').hexdigest()
    (tmp_path / digest).write_bytes(b'old')
    calls = []
    def fail(*args):
        calls.append(args)
        raise failure
    monkeypatch.setattr(downloader, '_open', fail)
    monkeypatch.setattr('time.sleep', lambda delay: None)
    with pytest.raises(type(failure)):
        downloader.fetch('https://example.org/font', digest, tmp_path, attempts=2)
    assert len(calls) == 2
    assert (tmp_path / digest).read_bytes() == b'old'
    assert not list(tmp_path.glob('.download-*'))


def test_connection_uses_read_timeout_after_tls(monkeypatch):
    events = []
    class Sock:
        def settimeout(self, timeout):
            events.append(timeout)
    def connect(self):
        self.sock = Sock()
        assert self._create_connection is downloader._connect
    monkeypatch.setattr('http.client.HTTPSConnection.connect', connect)
    def do_open(handler, connection, req, **kwargs):
        conn = connection('example.org', timeout=15)
        assert conn.timeout == 15
        conn.connect()
        return Response(b'font')
    monkeypatch.setattr('urllib.request.HTTPSHandler.do_open', do_open)
    with downloader._open('https://example.org/font', 15, 42) as response:
        assert response.read() == b'font'
    assert events == [42]


def test_https_redirect_cannot_downgrade():
    request = downloader.urllib.request.Request('https://example.org/font')
    handler = downloader._HTTPSRedirectHandler()
    with pytest.raises(ValueError, match='Insecure download redirect'):
        handler.redirect_request(request, None, 302, 'Found', {}, 'http://example.org/font')
