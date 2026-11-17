"""Self-contained, script-free evidence report. All data enters through HTML escaping."""
from html import escape
import json

STYLE = """
:root{color-scheme:light;--ink:#222838;--muted:#566074;--paper:#f5f6fb;--line:#d8deeb;--accent:#454cc0;--fault:#a13428}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:16px/1.65 'Segoe UI',Arial,sans-serif}
main{max-width:1160px;margin:auto;padding:36px 40px 64px}header{display:flex;justify-content:space-between;gap:20px;align-items:center;border-bottom:1px solid var(--line);padding-bottom:24px}
.brand{font-weight:750;font-size:23px;letter-spacing:-.8px}.brand span{color:var(--accent)}.tag{font:12px Consolas,monospace;letter-spacing:1px;color:var(--muted)}
h1{font-size:clamp(32px,5.4vw,58px);line-height:1.12;letter-spacing:-2px;margin:20px 0 18px;max-width:850px}h2{font-size:24px;letter-spacing:-.5px;line-height:1.3;margin:0 0 16px}h3{font-size:16px;margin:0 0 8px}
.eyebrow{font:12px Consolas,monospace;letter-spacing:1.5px;text-transform:uppercase;color:var(--accent)}.intro{padding:44px 0 32px}.intro p{max-width:790px;color:var(--muted);margin:0}
.status{display:inline-block;border:1px solid var(--line);padding:6px 12px;border-radius:5px;font-size:13px;font-weight:650;background:white}.different{color:var(--fault);border-color:#dca89b;background:#fff3ee}.equivalent{color:#156b55;border-color:#9fcbbd;background:#eef9f3}.unknown,.invalid{color:#76500f;background:#fff5d9}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:20px}.card{min-width:0;border:1px solid var(--line);background:#fff;border-radius:10px;padding:26px}section{margin:24px 0}code,pre,.number{font-family:Consolas,'Courier New',monospace}code{overflow-wrap:anywhere}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px;background:var(--paper);padding:20px;border-radius:6px}p{overflow-wrap:anywhere}.expression{font-size:clamp(17px,2vw,22px);line-height:1.7;color:var(--accent);display:block;margin:16px 0}
.domain{display:flex;flex-wrap:wrap;gap:8px;margin-top:18px}.domain span{border:1px solid var(--line);border-radius:5px;padding:5px 10px;font:13px Consolas,monospace}.witness{background:#eeeffb;border-color:#c8cceb}.inputs{display:flex;flex-wrap:wrap;gap:20px}.input{min-width:100px}.input b{display:block;font:30px Consolas,monospace}.small{font-size:13px;color:var(--muted)}.result{font:38px/1.3 Consolas,monospace;margin:12px 0}
.bits{display:flex;flex-wrap:wrap;gap:4px;margin:14px 0}.bit{display:flex;flex-direction:column;align-items:center;min-width:26px;padding:4px;border:1px solid var(--line);background:var(--paper);border-radius:3px;font:18px Consolas,monospace}.bit small{font-size:9px;color:var(--muted)}.bit.diff{border-color:#c68570;background:#ffede1;color:var(--fault)}
details{background:#fff;border:1px solid var(--line);border-radius:7px;margin:14px 0}summary{cursor:pointer;font-weight:650;padding:15px 20px}summary:hover{background:#f1f2fb}summary:focus-visible{outline:3px solid var(--accent);outline-offset:3px}details .inside{padding:0 20px 20px}.scroll{overflow:auto}table{width:100%;border-collapse:collapse;font-size:14px}th{text-align:left;color:var(--muted);font-weight:600}td,th{border-bottom:1px solid var(--line);padding:10px 12px 10px 0;vertical-align:top}td:last-child{text-align:right}td code{white-space:nowrap}
.note{border-left:3px solid var(--accent);padding:0 0 0 18px;color:var(--muted);font-size:14px}.fingerprint{word-break:break-all;font:12px Consolas,monospace}.footer{border-top:1px solid var(--line);padding-top:20px;margin-top:32px;color:var(--muted);font-size:12px}
@media(max-width:680px){main{padding:22px 18px 40px}.grid{grid-template-columns:1fr}.card{padding:20px}.tag{max-width:120px;text-align:right}h1{letter-spacing:-1px}.intro{padding:30px 0 22px}}
@media print{body{background:white}main{padding:0}.card,details{break-inside:avoid}header{padding-bottom:12px}.intro{padding:20px 0}summary{padding:8px}h1{font-size:36px}.footer{margin-top:16px}}
"""


def render_html(report):
    e = lambda value: escape(str(value), quote=True)
    status = report["status"]
    labels = {"different": "Counterexample found", "equivalent": "Equivalent in the declared domain",
              "unknown": "No conclusion", "invalid": "Input rejected"}
    subtitles = {"different": "One concrete input is enough to disprove equivalence. The values below were replayed independently of the solver.",
                 "equivalent": "Z3 proved that no differing output exists for these expressions within the declared input ranges.",
                 "unknown": "The checker did not establish an answer. A timeout or resource limit is not a proof of equivalence.",
                 "invalid": "The input is outside the supported language or limits. No equivalence claim is made."}
    label = labels.get(status, labels["unknown"])
    p = report.get("problem")
    parts = [f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">',
             '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'; base-uri \'none\'; form-action \'none\'">',
             f'<title>BitEquiv — {e(p["title"] if p else label)}</title><style>{STYLE}</style></head><body><main>',
             '<header><div class="brand">Bit<span>Equiv</span></div><div class="tag">FIXED-WIDTH / REAL EVIDENCE</div></header>',
             f'<div class="intro"><div class="eyebrow">Unsigned expression verification</div><h1>{e(p["title"] if p else label)}</h1>',
             f'<p>{e(subtitles.get(status, subtitles["unknown"]))}</p></div>',
             f'<span class="status {e(status if status in labels else "unknown")}">{e(label)}</span>']
    if report.get("reason"):
        parts.append(f'<p class="note">{e(report["reason"])}</p>')
    if p:
        parts.append('<section class="grid" aria-label="Expressions">')
        for side in ("left", "right"):
            parts.append(f'<article class="card"><div class="eyebrow">{side} expression</div><code class="expression">{e(p[side])}</code><div class="small">Every intermediate wraps to {p["width"]} bits.</div></article>')
        parts.append('</section><section><h2>The declared domain</h2><div class="domain">')
        for name, bounds in p["ranges"].items():
            parts.append(f'<span>{e(name)}: {bounds[0]} … {bounds[1]}</span>')
        parts.append(f'</div><p class="small">{e(report["coverage"]["domain_assignments"])} possible assignments · {p["width"]}-bit unsigned · nonempty domain</p></section>')
    witness = report.get("witness")
    if witness:
        parts.append('<section class="card witness"><div class="eyebrow">Concrete counterexample</div><h2>Same inputs. Different bits.</h2><div class="inputs">')
        for name, value in witness["assignment"].items():
            parts.append(f'<div class="input"><span class="small">{e(name)}</span><b>{value}</b><code class="small">0x{value:x}</code></div>')
        if not witness["assignment"]:
            parts.append('<p>No variables: these are constant expressions.</p>')
        parts.append('</div></section><section class="grid" aria-label="Counterexample outputs">')
        for side in ("left", "right"):
            value = witness[side]["value"]
            bits = []
            for i in reversed(range(p["width"])):
                css = "bit diff" if i in witness["different_bits"] else "bit"
                bits.append(f'<span class="{css}" title="bit {i}">{(value >> i) & 1}<small>{i}</small></span>')
            parts.append(f'<article class="card"><div class="eyebrow">{side} output</div><div class="result">{value}</div><code class="small">0x{value:x}</code><div class="bits">{"".join(bits)}</div></article>')
        parts.append('</section><p class="small">Highlighted cells differ. Bit positions are zero-based; bit 0 is the least significant bit.</p>')
        for side in ("left", "right"):
            rows = []
            for i, step in enumerate(witness[side]["steps"], 1):
                rows.append(f'<tr><td>{i}</td><td><code>{e(step["expression"])}</code></td><td><code>{step["value"]}</code></td></tr>')
            parts.append(f'<details><summary>Inspect the {side} evaluation trace</summary><div class="inside scroll"><table><thead><tr><th>Step</th><th>Expression</th><th>Unsigned value</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div></details>')
    if p:
        parts.append(f'<section class="note"><h3>What this establishes — and what it does not</h3><p>{e(report["semantics"])}</p><p>{e(report["coverage"]["scope"])} The solver and translation are trusted; no independently checkable proof certificate is emitted. A counterexample is not necessarily the smallest one. This report contains input expressions and witness values.</p></section>')
        parts.append(f'<details><summary>Reproduce this result</summary><div class="inside"><p>Save the JSON below as <code>case.json</code>, then run:</p><pre>python -m bitequiv check case.json --json result.json --html result.html</pre><pre>{e(json.dumps(p, indent=2, ensure_ascii=True))}</pre><p class="small">Use new output names; existing files are never overwritten. Solver limits constrain the query, not whole-process memory or runtime.</p></div></details>')
        engine = report["engine"]
        parts.append(f'<footer class="footer">BitEquiv 0.1.0 · {e(engine["name"])} {e(engine.get("version", "unavailable"))} · timeout {engine["timeout_ms"]} ms · resource limit {engine["rlimit"]}<p>Canonical problem SHA-256</p><div class="fingerprint">{e(report["fingerprint"])}</div><p>Offline report. No scripts, external assets, or telemetry.</p></footer>')
    parts.append('</main></body></html>')
    return "\n".join(parts) + "\n"
