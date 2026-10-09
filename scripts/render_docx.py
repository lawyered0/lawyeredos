from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def command(name: str) -> str:
    resolved = shutil.which(name)
    if not resolved:
        raise ValueError(f"required command not found: {name}")
    return resolved


def render(input_path: Path, output_dir: Path, libreoffice: str, pdftoppm: str) -> list[Path]:
    if not input_path.is_file() or input_path.is_symlink():
        raise ValueError("input must be a regular DOCX file")
    if input_path.suffix.casefold() != ".docx":
        raise ValueError("input must have .docx extension")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError("output directory must be absent or empty")
    output_dir.mkdir(parents=True, exist_ok=True)
    soffice = command(libreoffice)
    raster = command(pdftoppm)
    with tempfile.TemporaryDirectory(prefix="lawyeredos-lo-") as profile:
        conversion = subprocess.run(
            [
                soffice,
                f"-env:UserInstallation=file://{profile}",
                "--invisible", "--headless", "--norestore",
                "--convert-to", "pdf", "--outdir", str(output_dir), str(input_path),
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=120,
        )
    pdf = output_dir / f"{input_path.stem}.pdf"
    if conversion.returncode != 0 or not pdf.is_file() or pdf.stat().st_size == 0:
        raise ValueError(f"LibreOffice render failed: {conversion.stderr.strip() or conversion.stdout.strip()}")
    result = subprocess.run(
        [raster, "-png", "-r", "150", str(pdf), str(output_dir / "page")],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=120,
    )
    pages = sorted(output_dir.glob("page-*.png"))
    if result.returncode != 0 or not pages:
        raise ValueError(f"page rasterization failed: {result.stderr.strip()}")
    return pages


def main() -> int:
    parser = argparse.ArgumentParser(description="Render DOCX to PDF and page PNGs")
    parser.add_argument("input")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--libreoffice", default="soffice")
    parser.add_argument("--pdftoppm", default="pdftoppm")
    args = parser.parse_args()
    try:
        pages = render(
            Path(args.input).expanduser().resolve(),
            Path(args.output_dir).expanduser().resolve(),
            args.libreoffice,
            args.pdftoppm,
        )
        print(f"rendered {len(pages)} page(s)")
        return 0
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        print(f"error: {exc}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
