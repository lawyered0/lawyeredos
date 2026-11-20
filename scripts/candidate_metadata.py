"""Create local immutable aliases and checksum metadata from one checked build."""
from __future__ import annotations

import argparse
import json
import re
import tomllib
import zipfile
from pathlib import Path

from public_release_check import ROOT, check_archive, digest, load_policy


def prepare(archive: Path, output: Path) -> dict:
    if output.exists():
        raise ValueError("candidate output must be absent")
    policy = load_policy(ROOT)
    if check_archive(archive, ROOT, policy, []):
        raise ValueError("candidate archive did not pass the release gate")
    with zipfile.ZipFile(archive) as package:
        def read(name):
            return package.read("lawyeredos/"+name).decode("utf-8")
        version = tomllib.loads(read("pyproject.toml"))["project"]["version"]
        versions = [
            json.loads(read(".claude-plugin/plugin.json"))["version"],
            re.search(r'__version__ = "([^"]+)"', read("src/lawyeredos/__init__.py")).group(1),
            re.search(r'VERSION = "([^"]+)"', read("src/lawyeredos/setup_wizard.py")).group(1),
        ]
        if not re.fullmatch(r"\d+\.\d+\.\d+", version) or any(v != version for v in versions):
            raise ValueError("candidate package versions disagree")
        members = {i.filename:digest(package.read(i)) for i in package.infolist()}
    data = archive.read_bytes()
    sha256 = digest(data)
    names = [f"lawyeredos-{version}-macos-beta.1.zip", f"lawyeredos-{version}-macos-codex-beta.1.zip"]
    manifest = {"schema_version":1,"version":version,"candidate":"beta.1","publication_status":"local-review-only","sha256":sha256,"size_bytes":len(data),"member_count":len(members),"files":names,"members":members}
    output.mkdir(parents=True)
    for name in names:
        (output/name).write_bytes(data)
    (output/"release-manifest.json").write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
    (output/"SHA256SUMS").write_text("".join(f"{sha256}  {name}\n" for name in names),encoding="utf-8")
    return manifest


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive",required=True,type=Path)
    parser.add_argument("--output",required=True,type=Path)
    args=parser.parse_args()
    try:
        result=prepare(args.archive,args.output)
    except (OSError,ValueError,KeyError,AttributeError,zipfile.BadZipFile):
        print("candidate metadata generation failed closed")
        return 2
    print(f"Prepared local {result['version']} {result['candidate']} ({result['member_count']} members), SHA-256 {result['sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
