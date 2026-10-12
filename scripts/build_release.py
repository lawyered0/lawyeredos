from __future__ import annotations

import argparse
import stat
import zipfile
from pathlib import Path


import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from lawyeredos.package_inputs import ROOT_FILES, ROOT_DIRECTORIES, EXCLUDED_PARTS, release_files


FIXED_TIME = (2026, 1, 1, 0, 0, 0)


def package_root() -> Path:
    return Path(__file__).resolve().parents[1]


def build(output: Path) -> dict[str, int | str]:
    root = package_root()
    output = output.expanduser().absolute()
    if output.exists():
        raise ValueError(f"output already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    files = release_files(root)
    temporary = output.with_name(f".{output.name}.partial")
    if temporary.exists():
        raise ValueError(f"partial output already exists: {temporary}")
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for path in files:
                relative = Path("lawyeredos") / path.relative_to(root)
                info = zipfile.ZipInfo(relative.as_posix(), FIXED_TIME)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = (stat.S_IFREG | 0o644) << 16
                archive.writestr(info, path.read_bytes())
        temporary.replace(output)
    except Exception:
        if temporary.exists():
            temporary.unlink()
        raise
    return {"output": str(output), "file_count": len(files), "size_bytes": output.stat().st_size}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build an allowlisted LawyeredOS source archive")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        result = build(Path(args.output))
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        print(f"error: {exc}")
        return 2
    print(f"Built {result['file_count']} files: {result['output']} ({result['size_bytes']} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
