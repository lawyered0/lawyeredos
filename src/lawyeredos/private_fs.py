from __future__ import annotations

import os
import shutil
import stat
import tempfile
from pathlib import Path


PRIVATE_DIRECTORY_MODE = 0o700
PRIVATE_FILE_MODE = 0o600


def _mode(path: Path) -> int:
    return stat.S_IMODE(path.lstat().st_mode)


def migration_error(path: Path, expected: int) -> ValueError:
    return ValueError(
        f"private LawyeredOS path has unsafe permissions: {path} "
        f"(found {_mode(path):04o}, require {expected:04o}); "
        "review and migrate this existing path explicitly, then build a new setup plan"
    )


def assert_private_directory(path: Path) -> None:
    """Validate an existing app-owned confidential directory without changing it."""
    if path.is_symlink() or not path.is_dir():
        raise ValueError(f"private LawyeredOS directory is missing, a symlink, or not a directory: {path}")
    if _mode(path) != PRIVATE_DIRECTORY_MODE:
        raise migration_error(path, PRIVATE_DIRECTORY_MODE)


def ensure_private_directory(path: Path) -> bool:
    """Create one directory as 0700, or validate an existing directory.

    Parents are deliberately not created: callers must distinguish app-owned paths
    from user-owned workspace parents rather than recursively changing either.
    """
    if path.exists() or path.is_symlink():
        assert_private_directory(path)
        return False
    os.mkdir(path, PRIVATE_DIRECTORY_MODE)
    created = path.lstat()
    try:
        # A restrictive umask can make the just-created directory mode 000,
        # which cannot be opened even by its owner. chmod the exact new inode
        # before opening it, then bind and verify through a no-follow fd.
        os.chmod(path, PRIVATE_DIRECTORY_MODE, follow_symlinks=False)
        flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(path, flags)
        try:
            details = os.fstat(descriptor)
            if (details.st_dev, details.st_ino) != (created.st_dev, created.st_ino):
                raise ValueError(f"private LawyeredOS directory changed during creation: {path}")
            os.fchmod(descriptor, PRIVATE_DIRECTORY_MODE)
        finally:
            os.close(descriptor)
        assert_private_directory(path)
    except BaseException:
        try:
            current = path.lstat()
            if (
                not path.is_symlink()
                and path.is_dir()
                and (current.st_dev, current.st_ino) == (created.st_dev, created.st_ino)
            ):
                path.rmdir()
        except OSError:
            pass
        raise
    return True


def assert_private_file(path: Path) -> None:
    """Validate a confidential regular file and reject aliases/special entries."""
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"private LawyeredOS file is a symlink or not a regular file: {path}")
    details = path.stat(follow_symlinks=False)
    if details.st_nlink != 1:
        raise ValueError(f"private LawyeredOS file has multiple hard links: {path}")
    if stat.S_IMODE(details.st_mode) != PRIVATE_FILE_MODE:
        raise migration_error(path, PRIVATE_FILE_MODE)


def assert_private_tree(path: Path) -> None:
    assert_private_directory(path)
    for item in sorted(path.rglob("*")):
        if item.is_symlink():
            raise ValueError(f"private LawyeredOS tree contains a symlink: {item}")
        if item.is_dir():
            assert_private_directory(item)
        elif item.is_file():
            assert_private_file(item)
        else:
            raise ValueError(f"private LawyeredOS tree contains a special filesystem entry: {item}")


def create_private_file(path: Path, data: bytes = b"", *, mode: int = PRIVATE_FILE_MODE) -> None:
    """Exclusively create a regular file with its private mode at creation time."""
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, mode)
    try:
        os.fchmod(descriptor, mode)
        with os.fdopen(descriptor, "wb", closefd=True) as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        try:
            path.unlink()
        except OSError:
            pass
        raise
    if mode == PRIVATE_FILE_MODE:
        assert_private_file(path)


def replace_private_file(path: Path, data: bytes) -> None:
    """Atomically create/replace a private file, preserving no unsafe predecessor."""
    if not path.exists() and not path.is_symlink():
        create_private_file(path, data)
        return
    assert_private_file(path)
    descriptor, raw = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(raw)
    try:
        os.fchmod(descriptor, PRIVATE_FILE_MODE)
        with os.fdopen(descriptor, "wb", closefd=True) as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        assert_private_file(temporary)
        os.replace(temporary, path)
        assert_private_file(path)
    finally:
        if temporary.exists():
            temporary.unlink()


def copy_private_file(source: Path, destination: Path) -> None:
    if source.is_symlink() or not source.is_file():
        raise ValueError(f"backup source is a symlink or not a regular file: {source}")
    if source.stat(follow_symlinks=False).st_nlink != 1:
        raise ValueError(f"backup source has multiple hard links: {source}")
    create_private_file(destination, source.read_bytes())


def copy_private_tree(source: Path, destination: Path) -> None:
    """Copy a regular, link-free tree with private modes on every new entry."""
    if source.is_symlink() or not source.is_dir():
        raise ValueError(f"backup source is a symlink or not a directory: {source}")
    ensure_private_directory(destination)
    for item in sorted(source.iterdir(), key=lambda value: value.name):
        target = destination / item.name
        if item.is_symlink():
            raise ValueError(f"backup source tree contains a symlink: {item}")
        if item.is_dir():
            copy_private_tree(item, target)
        elif item.is_file():
            if item.stat(follow_symlinks=False).st_nlink != 1:
                raise ValueError(f"backup source tree contains a hard-linked file: {item}")
            copy_private_file(item, target)
        else:
            raise ValueError(f"backup source tree contains a special filesystem entry: {item}")
