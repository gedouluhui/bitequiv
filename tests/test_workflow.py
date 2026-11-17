import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from bitequiv import check

ROOT = Path(__file__).resolve().parents[1]


class EvidenceWorkflowTests(unittest.TestCase):
    def run_command(self, folder, *args, without_solvers=False):
        env = dict(os.environ, PYTHONPATH=str(ROOT/"src"))
        command = [sys.executable, "-m", "bitequiv", *args]
        if without_solvers:
            code = ("import sys\nclass Block:\n def find_spec(self,name,*args):\n"
                    "  if name.split('.')[0] in ('z3','cvc5'): raise ModuleNotFoundError('solver forbidden')\n"
                    "sys.meta_path.insert(0,Block())\nfrom bitequiv.cli import main\nraise SystemExit(main(sys.argv[1:]))")
            command = [sys.executable, "-c", code, *args]
        return subprocess.run(command, cwd=folder, env=env, capture_output=True,
                              text=True, encoding="utf-8", timeout=20)

    def test_export_emits_actual_query_and_metadata_without_solving(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/"input.json"
            p.write_text(json.dumps(dict(width=8,variables=["x"],left="x",right="x+1")),"utf-8")
            r = self.run_command(tmp,"export",str(p),"--smt2","query.smt2",without_solvers=True)
            self.assertEqual(r.returncode,0,r.stderr)
            metadata = json.loads(r.stdout)
            self.assertEqual(metadata["status"],"exported")
            query = (Path(tmp)/"query.smt2").read_bytes()
            self.assertEqual(metadata["query_sha256"],hashlib.sha256(query).hexdigest())
            self.assertIn(b"(check-sat)",query)
            self.assertIn("not a verdict",metadata["scope"])
            repeat = self.run_command(tmp,"export",str(p),"--smt2","query.smt2")
            self.assertEqual(repeat.returncode,3)
            self.assertEqual((Path(tmp)/"query.smt2").read_bytes(),query)

    def test_generated_report_replays_without_z3_and_detects_tampering(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/"report.json"
            data = check(dict(width=8,variables=["x"],left="x",right="x+1"))
            p.write_text(json.dumps(data),"utf-8")
            good = self.run_command(tmp,"replay",str(p),without_solvers=True)
            self.assertEqual(good.returncode,0,good.stderr)
            self.assertEqual(json.loads(good.stdout)["verification_status"],"verified_counterexample")
            data["witness"]["left"]["value"] += 1
            p.write_text(json.dumps(data),"utf-8")
            bad = self.run_command(tmp,"replay",str(p),without_solvers=True)
            self.assertEqual(bad.returncode,1,bad.stderr)
            self.assertEqual(json.loads(bad.stdout)["verification_status"],"mismatch")

    def test_universal_claim_and_bad_json_have_distinct_exit_codes(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/"report.json"
            p.write_text(json.dumps(check(dict(width=8,variables=["x"],left="x",right="x"))),"utf-8")
            r = self.run_command(tmp,"replay",str(p),without_solvers=True)
            self.assertEqual(r.returncode,2,r.stderr)
            self.assertEqual(json.loads(r.stdout)["verification_status"],"unverifiable")
            p.write_text('{"status":NaN}',"utf-8")
            r = self.run_command(tmp,"replay",str(p))
            self.assertEqual(r.returncode,3)
            self.assertEqual(json.loads(r.stdout)["verification_status"],"invalid")

    def test_report_limit_is_separate_from_problem_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/"report.json"
            data = json.dumps(check(dict(width=8,variables=["x"],left="x",right="x+1")))
            p.write_text(" "*65536+data,"utf-8")
            r = self.run_command(tmp,"replay",str(p),without_solvers=True)
            self.assertEqual(r.returncode,0,r.stderr)
            p.write_text(" "*1048577,"utf-8")
            r = self.run_command(tmp,"replay",str(p))
            self.assertEqual(r.returncode,3)

    def test_replay_argument_errors_keep_replay_result_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            for args in (("replay",), ("replay","missing.json","--unsupported")):
                r = self.run_command(tmp,*args)
                self.assertEqual(r.returncode,3)
                self.assertEqual(json.loads(r.stdout).get("verification_status"),"invalid")
                self.assertNotIn("status",json.loads(r.stdout))

    def test_help_closed_stdout_pipe_returns_operational_error(self):
        code = ("import os,sys; from bitequiv.cli import main; "
                "r,w=os.pipe(); os.close(r); original=sys.stdout; sys.stdout=os.fdopen(w,'w'); "
                "result=main(['--help']); sys.stdout.close(); sys.stdout=original; raise SystemExit(result)")
        with tempfile.TemporaryDirectory() as tmp:
            env = dict(os.environ,PYTHONPATH=str(ROOT/"src"))
            r = subprocess.run([sys.executable,"-c",code],cwd=tmp,env=env,capture_output=True,text=True,encoding="utf-8",timeout=20)
        self.assertEqual(r.returncode,3,r.stderr)
        self.assertNotIn("Traceback",r.stderr)

    def test_export_refuses_input_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/"input.json"
            p.write_text(json.dumps(dict(width=8,variables=["x"],left="x",right="x")),"utf-8")
            before = p.read_bytes()
            r = self.run_command(tmp,"export",str(p),"--smt2",str(p))
            self.assertEqual(r.returncode,3)
            self.assertEqual(p.read_bytes(),before)


if __name__ == "__main__":
    unittest.main()
