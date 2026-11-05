# Deviations from registration R5

Each deviation is listed with its reason, when it was decided, and what was known at that moment.

## R5-D1. Benchmark drift above 15% in every session; all sessions accepted

**What happened.**
- Every one of the 11 sessions run (9 bases, plus single-session reruns of 1.1.2 and 2.0.3) drifted by more than the registered 15%. Drift ranged from 26.7% to 43.4%, measured from the first reading.
- In every session the cause is the first reading, which is 26% to 43% slower than all later readings. Measured from the second reading, 9 of 11 sessions stay within 15%: 1.2.4 reaches 25.1% and 2.2.3 16.6%.
- The pattern is the same for sessions run three at a time and run alone, and on Intel Xeon and AMD EPYC machines.
- **Cause:**
  - R5 does not install Qiskit Aer, because the probe is not used. The frozen reference benchmark (cart `obsaware/bench.py`) includes one probe call, which therefore runs on Qiskit's reference Statevector simulator.
  - The benchmark took 10 to 17 s per repeat in R5, against 0.47 s in R4, and its first call in a fresh process is much slower.
  - This is a property of the benchmark in R5's environment, not a change in machine speed.

**What the rule requires.** Section 5: a session whose benchmark drifts by more than 15% at any reading is rerun.

**What was done.**
- **Reruns tried:** the authors reran 1.1.2 and 2.0.3 one session at a time, and the first reading was again 43.4% and 32.8% slower. No rerun can meet the rule as written.
- **Decision:** on 2026-11-05, before any detection result of any session had been looked at, the authors decided to accept every session without further reruns.
  - **What had been inspected:** only hardware records, timings, event counts and benchmark readings.
  - **Which runs are used:** for 1.1.2 and 2.0.3, the registered analysis uses the single-session reruns (v2). The first runs are kept as superseded and are compared with the reruns as a reported reproducibility check.

**Effect.**
- **Detection and exposure:** these do not depend on machine speed.
- **Measured costs:** these are used to cut S1' to S5's cost, and both suites are measured in the same clean stage of the same session.
- **Hang limit:** the hang limit is a fixed 120 s without progress.
