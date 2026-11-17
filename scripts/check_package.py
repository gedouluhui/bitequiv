"""Verify release contents and run the built wheel outside the source checkout."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import venv
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def run(command, cwd, env):
    result = subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=120)
    if result.returncode:
        raise AssertionError(f"command failed: {command[0]} ({result.returncode})\n{result.stdout}\n{result.stderr}")
    return result


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    dist = ROOT / "dist"
    wheel = dist / "bitequiv-0.1.0-py3-none-any.whl"
    archive = dist / "bitequiv-0.1.0.tar.gz"
    required = ["README.md", "README.zh-CN.md", "LICENSE", "docs/DESIGN.md", "scripts/check_mutations.py"]
    required += ["examples/" + p.name for p in (ROOT / "examples").glob("*.json")]
    assert len(required) > 5, "no source examples found"
    with tarfile.open(archive, "r:gz") as bundle:
        names = bundle.getnames()
        for path in required:
            name = "bitequiv-0.1.0/" + path
            assert name in names, f"sdist missing runnable/documented asset: {path}"
            assert bundle.extractfile(name).read() == (ROOT / path).read_bytes(), f"sdist drift: {path}"
        assert not any("/.local/" in name or "/.venv/" in name for name in names)
    with zipfile.ZipFile(wheel) as bundle:
        for source in (ROOT / "src" / "bitequiv").glob("*.py"):
            assert bundle.read("bitequiv/" + source.name) == source.read_bytes(), f"wheel source drift: {source.name}"
        assert not any(".local/" in name or ".venv/" in name for name in bundle.namelist())
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "PYTHONHOME")}
    env["PYTHONIOENCODING"] = "utf-8"
    with tempfile.TemporaryDirectory(prefix="bitequiv-wheel-") as temp:
        folder = Path(temp)
        venv.EnvBuilder(with_pip=True).create(folder / "venv")
        binary = folder / "venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        run([str(binary), "-m", "pip", "install", str(wheel)], folder, env)
        probe = run([str(binary), "-c", "import bitequiv,json; print(json.dumps({'file':bitequiv.__file__,'version':bitequiv.__version__}))"], folder, env)
        identity = json.loads(probe.stdout)
        assert Path(identity["file"]).is_relative_to(folder / "venv"), "source checkout shadowed wheel"
        cases = {"overflow-mean.json": 1, "bounded-mean.json": 0, "shift-distribution.json": 0, "lost-high-bit.json": 1}
        for name, expected in cases.items():
            output = folder / (name + ".result.json")
            html = folder / (name + ".html")
            result = subprocess.run([str(binary), "-m", "bitequiv", "check", str(ROOT / "examples" / name),
                                     "--json", str(output), "--html", str(html)], cwd=folder, env=env,
                                    capture_output=True, text=True, encoding="utf-8", timeout=30)
            assert result.returncode == expected, (name, result.returncode, result.stderr)
            report = json.loads(result.stdout)
            assert report == json.loads(output.read_text("utf-8")), "stdout/disk report mismatch"
            assert report["fingerprint"] in html.read_text("utf-8"), "HTML identifies a different input"
            print(json.dumps({"case": name, "status": report["status"], "exit": result.returncode}), flush=True)
    summary = {"status": "passed", "wheel_sha256": hashlib.sha256(wheel.read_bytes()).hexdigest(),
               "sdist_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(), "cases": len(cases),
               "installed_version": identity["version"], "outside_source_checkout": True}
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
