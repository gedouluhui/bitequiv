"""BitEquiv: fixed-width expressions, explicit semantics, replayable counterexamples."""
from .language import InvalidProblem, Problem, parse_json
from .evaluate import evaluate
from .solver import check
from .smtlib import export_smt2
from .evidence import parse_report, replay_report

__version__ = "0.2.0"
__all__ = ["InvalidProblem", "Problem", "parse_json", "evaluate", "check", "export_smt2", "parse_report", "replay_report"]
