"""catan_eval: a clocked, hidden-information match harness for catanatron agents.

Importing this package applies the determinism fix described in `catan_eval._patch`. Import it
before you create any Game.
"""
from catan_eval import _patch

_patch.apply()

__all__ = ["_patch"]
__version__ = "1.0.0"
