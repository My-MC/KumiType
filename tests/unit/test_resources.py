import pytest

from kumitype.resources import worker_count


def test_large_fonts_limit_parallel_memory():
    assert worker_count(16, memory_bytes=8 * 1024**3, cpu_count=16) == 3
    assert worker_count('auto', memory_bytes=32 * 1024**3, cpu_count=4) == 4
    assert worker_count(8, memory_bytes=32 * 1024**3, cpu_count=16, max_jobs=2) == 2


def test_low_memory_and_invalid_request():
    assert worker_count('auto', memory_bytes=100, cpu_count=8) == 1
    with pytest.raises(ValueError):
        worker_count(0)
