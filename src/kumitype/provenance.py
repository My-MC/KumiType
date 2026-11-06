"""Capture the implementation and dependency identity when the worker starts."""
import hashlib
import importlib.metadata
import platform
from pathlib import Path


def implementation_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.glob('*.py')):
        digest.update(path.name.encode())
        digest.update(b'\0')
        digest.update(path.read_bytes())
        digest.update(b'\0')
    return digest.hexdigest()


WORKER_PROVENANCE = {
    'implementation_sha256': implementation_digest(Path(__file__).parent),
    'python': platform.python_version(),
    'dependencies': {name: importlib.metadata.version(name) for name in ('fonttools', 'PyYAML')},
}
