import pytest

from kumitype.resources import worker_count


def test_large_fonts_limit_parallel_memory():
    assert worker_count(16, memory_bytes=8 * 1024**3, cpu_count=16) == 8
    assert worker_count('auto', memory_bytes=32 * 1024**3, cpu_count=4) == 4
    assert worker_count(8, memory_bytes=32 * 1024**3, cpu_count=16, max_jobs=2) == 2


def test_low_memory_and_invalid_request():
    assert worker_count('auto', memory_bytes=100, cpu_count=8) == 1
    with pytest.raises(ValueError):
        worker_count(0)


@pytest.mark.parametrize('contents, expected', [('MemAvailable: 8388608 kB\n', 8 * 1024**3),
                                               ('MemAvailable: invalid kB\n', 4096),
                                               ('MemFree: 123 kB\n', 4096)])
def test_memavailable_and_fallback(monkeypatch, contents, expected):
    from pathlib import Path
    from kumitype.resources import available_memory

    def read(path, *args, **kwargs):
        if str(path) == '/proc/meminfo':
            return contents
        raise OSError('unavailable')
    monkeypatch.setattr(Path, 'read_text', read)
    monkeypatch.setattr('os.sysconf', lambda key: 4 if key == 'SC_AVPHYS_PAGES' else 1024)
    assert available_memory() == expected


@pytest.mark.parametrize('version', ['v1', 'v2'])
def test_cgroup_remaining_caps_memavailable(monkeypatch, version):
    from pathlib import Path
    from kumitype.resources import available_memory

    paths = ('/sys/fs/cgroup/memory.max', '/sys/fs/cgroup/memory.current') if version == 'v2' else (
        '/sys/fs/cgroup/memory/memory.limit_in_bytes', '/sys/fs/cgroup/memory/memory.usage_in_bytes')
    values = {'/proc/meminfo': 'MemAvailable: 8388608 kB\n',
              paths[0]: str(3 * 1024**3), paths[1]: str(1024**3)}
    def read(path, *args, **kwargs):
        if str(path) in values:
            return values[str(path)]
        raise OSError('unavailable')
    monkeypatch.setattr(Path, 'read_text', read)
    assert available_memory() == 2 * 1024**3


@pytest.mark.parametrize('version', ['v1', 'v2'])
def test_nested_cgroup_ancestor_limit(monkeypatch, version):
    from pathlib import Path
    from kumitype.resources import available_memory

    root = '/sys/fs/cgroup' if version == 'v2' else '/sys/fs/cgroup/memory'
    limit = 'memory.max' if version == 'v2' else 'memory.limit_in_bytes'
    usage = 'memory.current' if version == 'v2' else 'memory.usage_in_bytes'
    values = {'/proc/meminfo': 'MemAvailable: 8388608 kB\n',
              '/proc/self/cgroup': '0::/parent/leaf\n' if version == 'v2' else '4:memory:/parent/leaf\n',
              f'{root}/parent/{limit}': str(2 * 1024**3),
              f'{root}/parent/{usage}': str(1024**3),
              f'{root}/parent/leaf/{limit}': 'max',
              f'{root}/parent/leaf/{usage}': '0'}
    def read(path, *args, **kwargs):
        if str(path) in values:
            return values[str(path)]
        raise OSError('unavailable')
    monkeypatch.setattr(Path, 'read_text', read)
    assert available_memory() == 1024**3


def test_explicit_limit_diagnostic(capsys):
    worker_count(8, memory_bytes=1024**3, cpu_count=8)
    message = capsys.readouterr().err
    assert 'requested=8' in message and 'workers=1' in message and 'memory' in message
