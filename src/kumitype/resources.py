"""Conservative worker limits for large Japanese font transformations."""
import os
from pathlib import Path


def available_memory() -> int:
    estimates = []
    try:
        estimates.append(os.sysconf('SC_AVPHYS_PAGES') * os.sysconf('SC_PAGE_SIZE'))
    except (ValueError, OSError, AttributeError):
        pass
    for limit_path, usage_path in (
        ('/sys/fs/cgroup/memory.max', '/sys/fs/cgroup/memory.current'),
        ('/sys/fs/cgroup/memory/memory.limit_in_bytes', '/sys/fs/cgroup/memory/memory.usage_in_bytes'),
    ):
        try:
            limit = int(Path(limit_path).read_text().strip())
            usage = int(Path(usage_path).read_text().strip())
            estimates.append(max(0, limit - usage))
        except (OSError, ValueError):
            pass
    return min(estimates) if estimates else 2 * 1024**3


def worker_count(requested='auto', *, memory_bytes=None, cpu_count=None,
                 worker_memory_mb=2048, max_jobs=None) -> int:
    cpus = cpu_count if cpu_count is not None else (os.cpu_count() or 1)
    memory = memory_bytes if memory_bytes is not None else available_memory()
    if worker_memory_mb <= 0:
        raise ValueError('worker_memory_mb must be positive')
    memory_limit = max(1, int(memory * 0.8) // (worker_memory_mb * 1024**2))
    desired = cpus if requested == 'auto' else int(requested)
    if desired < 1 or (max_jobs is not None and max_jobs < 1):
        raise ValueError('jobs and max_jobs must be positive')
    return max(1, min(desired, cpus, memory_limit, max_jobs or desired))
