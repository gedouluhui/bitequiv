import importlib.util
import io
from pathlib import Path
import tarfile
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1]/"scripts"/"check_package.py"
spec = importlib.util.spec_from_file_location("package_guard", SCRIPT)
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


class PackageGuardTests(unittest.TestCase):
    def fixture(self, folder):
        root = Path(folder)/"source"; root.mkdir()
        files = {"README.md":b"readme", "README.zh-CN.md":b"zh", "LICENSE":b"MIT",
                 "MANIFEST.in":b"include README.md", "pyproject.toml":b"[project]\nversion='0.2.0'\n",
                 "src/bitequiv/__init__.py":b"__version__='0.2.0'\n", "docs/DESIGN.md":b"design",
                 "examples/example.json":b"{}", "scripts/check_mutations.py":b"pass\n"}
        for name, data in files.items():
            path = root/name; path.parent.mkdir(parents=True,exist_ok=True); path.write_bytes(data)
        return root, files

    def archive(self, folder, files):
        target = Path(folder)/"bundle.tar.gz"
        with tarfile.open(target,"w:gz") as bundle:
            for name, data in files.items():
                entry = tarfile.TarInfo("bitequiv-0.2.0/"+name); entry.size=len(data)
                bundle.addfile(entry,io.BytesIO(data))
        return target

    def test_full_source_contents_are_verified(self):
        with tempfile.TemporaryDirectory() as tmp:
            root,files=self.fixture(tmp)
            guard.verify_sdist(self.archive(tmp,files),root,"0.2.0")

    def test_document_only_archive_cannot_hide_behind_a_good_wheel(self):
        with tempfile.TemporaryDirectory() as tmp:
            root,files=self.fixture(tmp)
            files={n:d for n,d in files.items() if not n.startswith("src/") and n not in ("pyproject.toml","MANIFEST.in")}
            with self.assertRaisesRegex(AssertionError,"missing"):
                guard.verify_sdist(self.archive(tmp,files),root,"0.2.0")

    def test_changed_source_member_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root,files=self.fixture(tmp)
            files["src/bitequiv/__init__.py"]=b"tampered"
            with self.assertRaisesRegex(AssertionError,"drift"):
                guard.verify_sdist(self.archive(tmp,files),root,"0.2.0")


if __name__ == "__main__": unittest.main()
