"""Verify release contents and run the built wheel outside the source checkout."""
import argparse
import hashlib
import tomllib
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


def verify_sdist(archive, root, version):
    required = {"README.md", "README.zh-CN.md", "LICENSE", "MANIFEST.in", "pyproject.toml", "docs/DESIGN.md", "scripts/check_mutations.py"}
    source_files = list((root/"src"/"bitequiv").glob("*.py"))
    assert source_files, "no package source files to verify"
    for pattern in ("src/bitequiv/*.py", "examples/*.json", "scripts/*.py", "tests/*.py", "docs/*.md", "docs/*.json", "docs/*.html"):
        required.update(p.relative_to(root).as_posix() for p in root.glob(pattern))
    with tarfile.open(archive, "r:gz") as bundle:
        names = bundle.getnames()
        assert len(names) == len(set(names)), "duplicate sdist members"
        for path in sorted(required):
            name = f"bitequiv-{version}/" + path
            assert name in names, f"sdist missing required asset: {path}"
            member = bundle.getmember(name)
            assert member.isfile(), f"sdist required asset is not a file: {path}"
            assert bundle.extractfile(member).read() == (root/path).read_bytes(), f"sdist drift: {path}"
        assert not any(set(Path(name).parts) & {".local", ".venv", ".git"} for name in names)


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    parser = argparse.ArgumentParser()
    parser.add_argument("--dist-dir", type=Path, default=ROOT/"dist")
    args = parser.parse_args()
    version = tomllib.loads((ROOT/"pyproject.toml").read_text("utf-8"))["project"]["version"]
    dist = args.dist_dir.resolve()
    wheel = dist / f"bitequiv-{version}-py3-none-any.whl"
    archive = dist / f"bitequiv-{version}.tar.gz"
    verify_sdist(archive, ROOT, version)
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
        run([str(binary), "-m", "pip", "install", "--no-deps", str(wheel)], folder, env)
        run([str(binary), "-c", "import importlib.util; assert importlib.util.find_spec('z3') is None; assert importlib.util.find_spec('cvc5') is None"], folder, env)
        export = run([str(binary), "-m", "bitequiv", "export", str(ROOT/"examples"/"overflow-mean.json"),
                      "--smt2", str(folder/"query.smt2")], folder, env)
        assert json.loads(export.stdout)["status"] == "exported"
        assert (folder/"query.smt2").is_file()
        replay = run([str(binary), "-m", "bitequiv", "replay", str(ROOT/"docs"/"example-report.json")], folder, env)
        assert json.loads(replay.stdout)["verification_status"] == "verified_counterexample"
        missing = subprocess.run([str(binary), "-m", "bitequiv", "check", str(ROOT/"examples"/"bounded-mean.json")],
                                 cwd=folder, env=env, capture_output=True, text=True, encoding="utf-8", timeout=30)
        assert missing.returncode == 2 and json.loads(missing.stdout)["status"] == "unknown", "missing solver misreported"
        print(json.dumps({"solver_free_export": True, "solver_free_replay": True, "missing_solver": "unknown"}), flush=True)
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
            replay = subprocess.run([str(binary), "-m", "bitequiv", "replay", str(output)], cwd=folder, env=env,
                                    capture_output=True, text=True, encoding="utf-8", timeout=30)
            assert replay.returncode == (0 if expected == 1 else 2), (name, "replay", replay.stderr)
            assert json.loads(replay.stdout)["verification_status"] == ("verified_counterexample" if expected == 1 else "unverifiable")
            print(json.dumps({"case": name, "status": report["status"], "exit": result.returncode,
                              "replay": json.loads(replay.stdout)["verification_status"]}), flush=True)
    summary = {"status": "passed", "wheel_sha256": hashlib.sha256(wheel.read_bytes()).hexdigest(),
               "sdist_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(), "cases": len(cases),
               "installed_version": identity["version"], "outside_source_checkout": True}
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
