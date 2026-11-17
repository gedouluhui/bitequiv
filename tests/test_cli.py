import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class CliTests(unittest.TestCase):
    def run_cli(self, cwd, *args):
        env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
        return subprocess.run([sys.executable, "-m", "bitequiv", *args], cwd=cwd,
                              capture_output=True, text=True, encoding="utf-8", env=env, timeout=20)

    def write_problem(self, folder, **changes):
        data = dict(width=8, variables=["x"], left="x", right="x+1")
        data.update(changes)
        path = Path(folder) / "input.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def test_real_roundtrip_counterexample(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_problem(tmp)
            before = path.read_bytes()
            result = self.run_cli(tmp, "check", str(path), "--json", "result.json", "--html", "result.html")
            self.assertEqual(result.returncode, 1, result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report["status"], "different")
            self.assertEqual(json.loads((Path(tmp)/"result.json").read_text("utf-8")), report)
            page = (Path(tmp)/"result.html").read_text("utf-8")
            self.assertIn(report["fingerprint"], page)
            self.assertIn("Counterexample", page)
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(result.stderr, "")

    def test_equivalent_exit_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = self.write_problem(tmp, right="x")
            result = self.run_cli(tmp, "check", str(p))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["status"], "equivalent")

    def test_unknown_exit_two(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = self.write_problem(tmp, width=32, left="x*x", right="x+1")
            result = self.run_cli(tmp, "check", str(p), "--rlimit", "1")
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertEqual(json.loads(result.stdout)["status"], "unknown")

    def test_invalid_inputs_exit_three(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = self.write_problem(tmp, width=False)
            result = self.run_cli(tmp, "check", str(p))
            self.assertEqual(result.returncode, 3, result.stderr)
            self.assertEqual(json.loads(result.stdout)["status"], "invalid")
            p.write_text('{"left":NaN}', encoding="utf-8")
            result = self.run_cli(tmp, "check", str(p))
            self.assertEqual(result.returncode, 3)

    def test_existing_output_is_not_modified(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = self.write_problem(tmp)
            output = Path(tmp)/"result.json"
            output.write_text("KEEP", encoding="utf-8")
            result = self.run_cli(tmp, "check", str(p), "--json", str(output), "--html", "new.html")
            self.assertEqual(result.returncode, 3)
            self.assertEqual(output.read_text("utf-8"), "KEEP")
            self.assertFalse((Path(tmp)/"new.html").exists())

    def test_same_output_paths_and_input_overwrite_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = self.write_problem(tmp)
            before = p.read_bytes()
            for args in (("--json", str(p)), ("--json", "same", "--html", "same")):
                result = self.run_cli(tmp, "check", str(p), *args)
                self.assertEqual(result.returncode, 3)
                self.assertEqual(p.read_bytes(), before)
                self.assertFalse((Path(tmp)/"same").exists())

    def test_missing_oversize_and_invalid_utf8_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_cli(tmp, "check", "missing.json")
            self.assertEqual(result.returncode, 3)
            path = Path(tmp)/"input.json"
            for content in (b" " * 65537, b"\xff\xfe"):
                path.write_bytes(content)
                result = self.run_cli(tmp, "check", str(path))
                self.assertEqual(result.returncode, 3)
                self.assertNotIn("Traceback", result.stderr)

    def test_html_is_escaped_and_offline(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = self.write_problem(tmp, title='</title><script>alert("x")</script>')
            result = self.run_cli(tmp, "check", str(p), "--html", "out.html")
            self.assertEqual(result.returncode, 1, result.stderr)
            text = (Path(tmp)/"out.html").read_text("utf-8")
            self.assertNotIn("<script", text.lower())
            self.assertIn("&lt;script&gt;", text)
            self.assertIn("Content-Security-Policy", text)
            self.assertNotIn("http://", text)
            self.assertNotIn("https://", text)
            self.assertIn("<details", text)

    def test_stdout_write_and_flush_failures_return_operational_error(self):
        import io
        from unittest.mock import patch
        from bitequiv.cli import main

        class FailingStream:
            def __init__(self, stage):
                self.stage = stage

            def write(self, text):
                if self.stage == "write":
                    raise OSError(28, "full")
                return len(text)

            def flush(self):
                if self.stage == "flush":
                    raise OSError(28, "full")

        with tempfile.TemporaryDirectory() as tmp:
            p = self.write_problem(tmp, right="x")
            for stage in ("write", "flush"):
                with self.subTest(stage=stage), patch("sys.stdout", FailingStream(stage)), patch("sys.stderr", io.StringIO()):
                    self.assertEqual(main(["check", str(p)]), 3)

    def test_real_broken_pipe_is_not_reported_as_counterexample(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = self.write_problem(tmp, right="x")
            code = ("import os,sys; from bitequiv.cli import main; "
                    "r,w=os.pipe(); os.close(r); original=sys.stdout; sys.stdout=os.fdopen(w,'w'); "
                    "result=main(['check',sys.argv[1]]); sys.stdout.close(); sys.stdout=original; "
                    "raise SystemExit(result)")
            env = dict(os.environ, PYTHONPATH=str(ROOT/"src"))
            result = subprocess.run([sys.executable, "-c", code, str(p)], cwd=tmp, env=env,
                                    capture_output=True, text=True, encoding="utf-8", timeout=20)
            self.assertEqual(result.returncode, 3, result.stderr)
            self.assertNotIn("Traceback", result.stderr)

    def test_cli_help_is_usable(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_cli(tmp, "--help")
            self.assertEqual(result.returncode, 0)
            self.assertIn("check", result.stdout)


if __name__ == "__main__":
    unittest.main()
