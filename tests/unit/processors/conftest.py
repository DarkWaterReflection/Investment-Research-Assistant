"""Make the shared fixture corpus importable from processor test modules.

The ``tests`` tree is not an installed package, so add ``tests/fixtures`` to
``sys.path`` here; test modules then ``from corpus import build_corpus``.
"""

import sys
from pathlib import Path

_FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"
if str(_FIXTURES) not in sys.path:
    sys.path.insert(0, str(_FIXTURES))
