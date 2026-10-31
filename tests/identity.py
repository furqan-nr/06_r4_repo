"""Prints one hash per corpus unit. Run under each base's interpreter; the outputs must be equal.

    python tests/identity.py corpus.json > ids_<base>.txt
"""
import hashlib
import json
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from reveal.corpus import load_unit  # noqa: E402
from reveal.generator import describe  # noqa: E402

for c in json.loads(Path(sys.argv[1]).read_text())["units"]:
    u = load_unit(c)
    print(c["unit"], hashlib.sha256(describe(u.circuit, u.bind).encode()).hexdigest()[:16])
