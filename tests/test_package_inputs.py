from __future__ import annotations

import importlib.util
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from lawyeredos.setup_wizard import package_digest, _ignored

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('build_release_fixture', ROOT / 'scripts/build_release.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class PackageInputTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'candidate'
        shutil.copytree(ROOT, self.root, ignore=shutil.ignore_patterns('.git', '__pycache__', '.pytest_cache'))

    def test_private_residue_refuses_release_and_setup_digest(self):
        for relative in ('scripts/.env', 'scripts/.env.synthetic', 'fixtures/synthetic.sqlite3',
                         'tests/synthetic.log', 'fixtures/config.toml.bak'):
            with self.subTest(relative=relative):
                residue = self.root / relative
                residue.write_text('fictional residue', encoding='utf-8')
                try:
                    with self.assertRaisesRegex(ValueError, 'release input'):
                        builder.release_files(self.root)
                    with self.assertRaisesRegex(ValueError, 'release input'):
                        package_digest(self.root)
                finally:
                    residue.unlink()

    def test_digest_ignores_nonpackage_roots_and_build_residue(self):
        original = package_digest(self.root)
        for relative in ('.DS_Store', 'build/lib/synthetic.py', 'src/synthetic.egg-info/PKG-INFO',
                         'website/synthetic.txt'):
            residue = self.root / relative
            residue.parent.mkdir(parents=True, exist_ok=True)
            residue.write_text('fictional generated residue', encoding='utf-8')
        self.assertEqual(package_digest(self.root), original)
        ignored = _ignored(str(self.root), ['.DS_Store', 'build', 'website', 'src', 'README.md'])
        self.assertTrue({'.DS_Store', 'build', 'website'}.issubset(ignored))

    def test_git_checkout_refuses_untracked_allowlisted_source_file(self):
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True, capture_output=True)
        subprocess.run(['git', '-C', str(self.root), 'add', '.'], check=True, capture_output=True)
        residue = self.root / 'scripts' / 'untracked-synthetic.py'
        residue.write_text('# fictional untracked source\n', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'untracked release input'):
            builder.release_files(self.root)

    def test_unknown_binary_and_symlink_inputs_are_refused(self):
        residue = self.root / 'fixtures' / 'synthetic.dat'
        residue.write_bytes(b'fictional binary residue')
        with self.assertRaisesRegex(ValueError, 'release input'):
            builder.release_files(self.root)
        residue.unlink()
        residue.symlink_to(self.root / 'README.md')
        with self.assertRaisesRegex(ValueError, 'symlink'):
            builder.release_files(self.root)
