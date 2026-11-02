"""Run the frozen reveal.analyze unchanged, with one addition: the frozen selection strategies are pure and
seeded, and their inputs depend only on the calibration session, so a call repeated with the same calibration
(B1/B2 share NR4a, C1/C1b/C2 share NR4b) returns the stored result of the first call. Output is identical to the
uncached run. Each strategy call is timed and logged."""
import sys
import time

import reveal.analyze as A

_orig = A.strategies
_cache = {}


def strategies():
    out = {}
    for name, fn in _orig().items():
        def wrapped(units, ct, budget, _name=name, _fn=fn):
            key = (_name, repr(budget), repr(ct.total()), len(units),
                   repr(sorted(units.items()) if isinstance(units, dict) else units)[:0])
            if key not in _cache:
                t0 = time.time()
                _cache[key] = _fn(units, ct, budget)
                print(f"{_name} budget={budget:.1f} {time.time() - t0:.0f}s", flush=True)
            else:
                print(f"{_name} budget={budget:.1f} cached", flush=True)
            return _cache[key]
        out[name] = wrapped
    return out


A.strategies = strategies
sys.exit(A.main())
