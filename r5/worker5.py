"""Run R5 items in this interpreter. stdin: JSON {"items": [...], "pickle": path, "expect": path or null}.
Each result is appended to the pickle stream as soon as it exists: (item, (status, kind, fingerprint, input, output,
cpu seconds)). With an expect file, an item whose fingerprint is in its expected set returns status "same" and no
circuits. The item about to run is written to <pickle>.cur, so the driver can name an item that hangs."""
import json
import pickle
import sys
import time
import warnings

warnings.filterwarnings("ignore")


def main():
    import r5.compat  # noqa: F401  (older Qiskit bases)
    from obsaware.oracles import fingerprint
    from r5 import items5 as I
    spec = json.loads(sys.stdin.read())
    expect = json.load(open(spec["expect"])) if spec.get("expect") else None

    def fp(res):
        try:
            return fingerprint(res)
        except Exception as e:
            return "unfingerprintable:" + type(e).__name__
    with open(spec["pickle"], "ab") as f:
        for it in spec["items"]:
            with open(spec["pickle"] + ".cur", "w") as c:
                c.write(it)
            t0 = time.process_time()
            try:
                kind, inp, res = I.run_item(it)
                c_ = time.process_time() - t0
                f_ = fp(res)
                if expect is not None and f_ in expect.get(it, ()):
                    r = ("same", kind, f_, None, None, c_)
                else:
                    r = ("ok", kind, f_, inp, res, c_)
            except BaseException as exc:          # a Rust panic surfaces as PanicException (a BaseException)
                if isinstance(exc, KeyboardInterrupt):
                    raise
                r = ("crash", f"{type(exc).__name__}: {str(exc)[:160]}", None, None, None, time.process_time() - t0)
            pickle.dump((it, r), f)
            f.flush()


if __name__ == "__main__":
    main()
