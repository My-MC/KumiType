"""Conservative worker limits for large Japanese font transformations."""
import os
import sys
from pathlib import Path


def available_memory() -> int:
    estimates = []
    try:
        for line in Path('/proc/meminfo').read_text().splitlines():
            fields = line.split()
            if fields and fields[0] == 'MemAvailable:' and len(fields) == 3 and fields[2] == 'kB':
                value = int(fields[1]) * 1024
                if value >= 0:
                    estimates.append(value)
                break
    except (OSError, ValueError):
        pass
    if not estimates:
        try:
            estimates.append(os.sysconf('SC_AVPHYS_PAGES') * os.sysconf('SC_PAGE_SIZE'))
        except (ValueError, OSError, AttributeError):
            pass
    # Include the current cgroup and all ancestors (systemd often nests limits).
    groups = [(Path('/sys/fs/cgroup'), 'memory.max', 'memory.current'),
              (Path('/sys/fs/cgroup/memory'), 'memory.limit_in_bytes', 'memory.usage_in_bytes')]
    try:
        for line in Path('/proc/self/cgroup').read_text().splitlines():
            _, controllers, relative = line.split(':', 2)
            if '..' in Path(relative).parts:
                continue
            if not controllers:
                mount, limit_name, usage_name = groups[0]
            elif 'memory' in controllers.split(','):
                mount, limit_name, usage_name = groups[1]
            else:
                continue
            directory = mount / relative.lstrip('/')
            while directory != mount:
                groups.append((directory, limit_name, usage_name))
                directory = directory.parent
    except (OSError, ValueError):
        pass
    for directory, limit_name, usage_name in groups:
        try:
            limit = int((directory / limit_name).read_text().strip())
            usage = int((directory / usage_name).read_text().strip())
            estimates.append(max(0, limit - usage))
        except (OSError, ValueError):
            pass
    return min(estimates) if estimates else 2 * 1024**3


def worker_count(requested='auto', *, memory_bytes=None, cpu_count=None,
                 worker_memory_mb=768, max_jobs=None) -> int:
    cpus = cpu_count if cpu_count is not None else (os.cpu_count() or 1)
    memory = memory_bytes if memory_bytes is not None else available_memory()
    if worker_memory_mb <= 0:
        raise ValueError('worker_memory_mb must be positive')
    memory_limit = max(1, int(memory * 0.8) // (worker_memory_mb * 1024**2))
    desired = cpus if requested == 'auto' else int(requested)
    if desired < 1 or (max_jobs is not None and max_jobs < 1):
        raise ValueError('jobs and max_jobs must be positive')
    # Measured 504-font peak RSS: median 424 MiB, maximum 464 MiB; allow headroom.
    actual = max(1, min(desired, cpus, memory_limit, max_jobs or desired))
    print(f'workers={actual} requested={requested} cpus={cpus} '
          f'available_memory_mib={memory // 1024**2} memory_limit={memory_limit} '
          f'worker_memory_mb={worker_memory_mb} max_jobs={max_jobs}', file=sys.stderr)
    return actual


def configured_workers(config=None, jobs=None):
    settings = (config or {}).get('build', {})
    return worker_count(jobs if jobs is not None else settings.get('jobs', 'auto'),
                        worker_memory_mb=settings.get('worker_memory_mb', 768),
                        max_jobs=settings.get('max_jobs'))
