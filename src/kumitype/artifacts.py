"""Atomic replacement of individually validated build artifacts."""
from contextlib import contextmanager
import os
import tempfile
from pathlib import Path


def save_font(font, destination: Path, validator) -> dict:
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=destination.parent, prefix='.font-', suffix='.ttf')
    os.close(fd)
    temporary = Path(name)
    try:
        font.save(temporary)
        result = validator(temporary)
        if not result['valid']:
            raise ValueError(f'Generated font failed validation: {result["errors"]}')
        os.replace(temporary, destination)
        return result
    finally:
        temporary.unlink(missing_ok=True)


def write_text(destination: Path, text: str) -> None:
    fd, name = tempfile.mkstemp(dir=destination.parent, prefix='.manifest-')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            stream.write(text)
        os.replace(name, destination)
    finally:
        Path(name).unlink(missing_ok=True)




@contextmanager
def atomic_output(destination: Path):
    """Publish a finished artifact, retaining an existing file on any exception."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=destination.parent, prefix='.artifact-')
    os.close(fd)
    temporary = Path(name)
    try:
        yield temporary
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
