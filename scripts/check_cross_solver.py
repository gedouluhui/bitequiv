"""Explicit cross-engine gate. No missing-dependency skips; no arbitrary SMT inputs."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def corpus():
    """Expected singleton results come from plain integer arithmetic, not product code."""
    cases = []
    for width in (1, 2, 4, 8, 32, 64):
        mask = (1 << width) - 1
        high = 1 << (width - 1)
        pairs = list(dict.fromkeys([(0, 0), (mask, 1), (1, mask), (high, width & mask), (mask, mask)]))
        for op in ("+", "-", "*", "&", "|", "^", "<<", ">>"):
            for a, b in pairs:
                if op == "+": value = (a + b) & mask
                elif op == "-": value = (a - b) & mask
                elif op == "*": value = (a * b) & mask
                elif op == "&": value = a & b
                elif op == "|": value = a | b
                elif op == "^": value = a ^ b
                elif op == "<<": value = 0 if b >= width else (a << b) & mask
                else: value = 0 if b >= width else a >> b
                for expected_value, expected in ((value, "unsat"), ((value + 1) & mask, "sat")):
                    cases.append(dict(id=f"w{width}:{op}:{a}:{b}:{expected}", expected=expected,
                                      problem=dict(width=width,variables=["x","y"],left=f"x {op} y",right=str(expected_value),
                                                   ranges={"x":[a,a],"y":[b,b]})))
        for op in ("+", "-", "~"):
            for a in sorted({0,1,high,mask}):
                value = (a if op == "+" else -a if op == "-" else ~a) & mask
                for expected_value, expected in ((value,"unsat"),((value+1)&mask,"sat")):
                    cases.append(dict(id=f"w{width}:unary{op}:{a}:{expected}",expected=expected,
                                      problem=dict(width=width,variables=["x"],left=f"{op}x",right=str(expected_value),ranges={"x":[a,a]})))
        cases.append(dict(id=f"w{width}:distributivity",expected="unsat",
                          problem=dict(width=width,variables=["x","y"],left="(x+y)<<1",right="(x<<1)+(y<<1)")))
        cases.append(dict(id=f"w{width}:lost-high-bit",expected="sat",
                          problem=dict(width=width,variables=["x"],left="(x<<1)>>1",right="x")))
    for name, bounds, expected in (("overflow",None,"sat"),("bounded",{"x":[0,127],"y":[0,127]},"unsat")):
        problem = dict(width=8,variables=["x","y"],left="(x+y)>>1",right="(x&y)+((x^y)>>1)")
        if bounds is not None: problem["ranges"] = bounds
        cases.append(dict(id=name+"-mean",expected=expected,problem=problem))
    cases.append(dict(id="reserved-names",expected="unsat",problem=dict(width=8,variables=["let","ite","v0"],left="let+ite+v0",right="v0+ite+let")))
    cases.append(dict(id="constant-domain",expected="sat",problem=dict(width=8,variables=[],left="1",right="2")))
    return cases


def agree(expected, product, z3_result, cvc5_result):
    expected_product = {"sat":"different", "unsat":"equivalent"}[expected]
    return product == expected_product and z3_result == expected and cvc5_result == expected


def self_test():
    for expected in ("sat", "unsat"):
        correct = "different" if expected == "sat" else "equivalent"
        if not agree(expected,correct,expected,expected): raise AssertionError("control agreement rejected")
        for index in range(3):
            items = [correct,expected,expected]; items[index] = "unknown"
            if agree(expected,*items): raise AssertionError("unknown accepted as agreement")
    cases = corpus()
    if len({x["id"] for x in cases}) != len(cases): raise AssertionError("duplicate corpus identity")
    if {x["expected"] for x in cases} != {"sat","unsat"}: raise AssertionError("one-sided controls")


def worker():
    import cvc5
    import z3
    from bitequiv import Problem, check, evaluate, export_smt2
    passed = []
    for case in corpus():
        p = Problem.from_dict(case["problem"])
        query = export_smt2(p)
        z = z3.Solver(); z.set(timeout=5000,rlimit=2000000); z.from_string(query)
        zr = str(z.check())
        tm = cvc5.TermManager(); c = cvc5.Solver(tm)
        c.setOption("tlimit-per","5000"); c.setOption("rlimit-per","2000000"); c.setOption("produce-models","true")
        parser = cvc5.InputParser(c)
        parser.setStringInput(cvc5.InputLanguage.SMT_LIB_2_6,query,"generated-case")
        symbols = parser.getSymbolManager(); cr = None
        while True:
            command = parser.nextCommand()
            if command.isNull(): break
            if command.getCommandName() not in {"set-logic","declare-fun","assert","check-sat"}:
                raise AssertionError("export contains an unexpected command")
            output = command.invoke(c,symbols)
            if command.getCommandName() == "check-sat": cr = output.strip()
        product = check(p)["status"]
        if not agree(case["expected"],product,zr,cr):
            raise AssertionError(json.dumps(dict(id=case["id"],expected=case["expected"],product=product,z3=zr,cvc5=cr)))
        if zr == "sat":
            z_values = {name:z.model().eval(z3.BitVec(f"v{i}",p.width),model_completion=True).as_long() for i,name in enumerate(p.variables)}
            c_values = {str(term):int(c.getValue(term).getBitVectorValue(10)) for term in symbols.getDeclaredTerms()}
            for assignment in (z_values,{name:c_values[f"v{i}"] for i,name in enumerate(p.variables)}):
                if evaluate(p,"left",assignment)["value"] == evaluate(p,"right",assignment)["value"]:
                    raise AssertionError(f"{case['id']}: exported solver model does not replay")
        passed.append(case["id"])
    digest = hashlib.sha256(json.dumps(corpus(),sort_keys=True,separators=(",",":")).encode()).hexdigest()
    print(json.dumps(dict(status="passed",cases=len(passed),ids=passed,corpus_sha256=digest,
                         z3=z3.get_version_string(),cvc5=cvc5.__version__,
                         scope="Three execution paths on this finite corpus; shared parser/spec remain trusted, no proof certificate.")))
    return 0


def main():
    if hasattr(sys.stdout,"reconfigure"): sys.stdout.reconfigure(encoding="utf-8",errors="backslashreplace")
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker",action="store_true",help=argparse.SUPPRESS)
    parser.add_argument("--self-test",action="store_true")
    args = parser.parse_args(); self_test()
    if args.self_test:
        print('{"status":"passed","scope":"cross-check classifier controls only"}'); return 0
    if args.worker: return worker()
    env = dict(os.environ,PYTHONPATH=str(ROOT/"src"),PYTHONIOENCODING="utf-8")
    try:
        result = subprocess.run([sys.executable,str(Path(__file__).resolve()),"--worker"],cwd=ROOT,env=env,
                                capture_output=True,text=True,encoding="utf-8",timeout=120)
    except subprocess.TimeoutExpired:
        print('{"status":"failed","reason":"cross-solver worker exceeded 120 seconds"}'); return 1
    if result.stdout: print(result.stdout,end="")
    if result.stderr: print(result.stderr,end="",file=sys.stderr)
    if result.returncode:
        print('{"status":"failed","reason":"worker failed; missing cvc5 is not a skipped success"}')
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
