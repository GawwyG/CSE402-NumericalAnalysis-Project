# STRUCTURE.md — Resume-from-here reference for a fresh Claude Code agent

**If you are a Claude Code agent picking this repository up on a new
device/session: read this entire file before touching anything.** It is
written to be self-contained — you should not need any other document to
understand what this project is, what state it's in, how it's organized,
or how to keep working on it correctly. Verify anything time-sensitive
(test counts, branch state) against the actual repo rather than trusting
a stale number here, since this file is a snapshot, not a live view.

---

## 1. What this project is

A university course project (CSE402, "Numerical Analysis, Simulation and
Modelling") reproducing and extending:

> J. Jang, D. Kim, I. Kim, "Singularity Handling for Unbalanced Three-Phase
> Transformers in Newton-Raphson Power Flow Analyses Using Moore-Penrose
> Pseudo-Inverse," IEEE Access, 2023. doi:10.1109/ACCESS.2023.3269503
> (the PDF is checked into the repo root).

**The physical problem.** In a three-phase distribution feeder, a
transformer winding connected in Delta (or ungrounded wye) has no path for
zero-sequence current. If such a winding's secondary side has no other
connection to ground anywhere, the *common-mode* voltage of that whole
region (adding the same complex offset to phases a, b, c simultaneously)
changes no branch current anywhere — the network equations cannot
determine it.

**The numerical consequence.** Newton-Raphson power flow repeatedly solves
`J_k · Δx_k = −F(x_k)`. A floating region shows up as a null direction of
the admittance matrix, making the Jacobian exactly singular or
numerically indistinguishable from it. A plain LU solve then either
throws, or — worse — returns a numerically meaningless update whose
residual looks deceptively small (residual measures consistency with the
linear system, not closeness to the true solution).

**The research question.** The base paper proposes fixing this with a
Moore-Penrose pseudo-inverse via SVD. This project asks: is that actually
the best fix, or does the right linear solver depend on the *structure* of
the rank deficiency (how much of the network the floating region spans)?
And separately: why did the paper's own IEEE-13 case show
disproportionately large error, relative to its other test cases?

**The answer this project found** (its headline result): no single solver
wins uniformly. On IEEE-13, SVD and RRQR's undamped minimum-norm steps
*oscillate and never converge* at realistic load — only Tikhonov
regularization converges. On IEEE-37, the exact reverse happens: SVD/RRQR
converge cleanly and the same Tikhonov setting fails. A controlled
zero-sequence investigation shows IEEE-13's load imbalance loads almost
entirely onto the (undetermined) zero-sequence voltage component rather
than the physically meaningful positive-sequence component — a structural,
partial explanation for the paper's own open question.

---

## 2. Current status (verify against the repo, this is a snapshot)

- All four linear solvers (direct, SVD, RRQR, Tikhonov) implemented,
  unit-tested, and integration-tested through one shared Newton-Raphson
  loop.
- All planned feeders reconstructed from official public data: IEEE 4-bus,
  13-bus, 37-bus (radial + quasi-radial variant), 69-bus, plus IEEE-118
  used only as a linear-solver runtime-scaling benchmark (not a
  power-flow/singularity case).
- Every feeder's analytical Jacobian is validated against finite
  differences (hard gate — see §6).
- Every feeder except the 118-bus scaling benchmark is independently
  cross-validated against an OpenDSS solve of a matching circuit.
- `python -m pytest -q` should report on the order of 85+ passing tests
  (check the actual number when you run it — it grows as work continues).
- A full draft paper exists at `report/paper.tex` (IEEEtran conference
  format), with a compiled `report/paper.pdf` checked into the repo, a
  bibliography (`report/refs.bib`), and 6 figures in `report/figures/`
  generated from live experiment runs by `report/make_figures.py`.
- The base paper's own PDF is checked into the repo root for reference.

**What's realistically left, if you want more to do:** polish/finalize the
paper (author names are still a placeholder — see `report/paper.tex`'s
`\author{}` block), explore the open discrepancies in
`data/provenance.yml` (never silently resolve these — see §8), or extend
the shared model to true delta-connected loads (currently approximated as
wye-equivalent — see §8) if more physical fidelity is wanted.

---

## 3. The architecture — read this before writing any code

There is **one shared Newton-Raphson loop**. Every solver comparison in
this project runs through the *exact same* nonlinear iteration — same
state representation, same mismatch function, same analytical Jacobian,
same flat start, same convergence tolerance. **Only the linear-solve step
inside each iteration differs** between "direct", "svd", "rrqr", and
"tikhonov". This is the single most important design fact in the
codebase: if you ever feel tempted to write a second Newton-Raphson loop
for a new solver or a new feeder, don't — extend
`solve_linear_step()`'s dispatch in `src/powerflow/newton.py` instead.

```
newton_raphson(state, Ybus, x0, method, solver_options, tol_F, max_iter)
        │
        │  each iteration:
        ├─ F(x)   ← src/powerflow/mismatch.py         (same for every method)
        ├─ J(x)   ← src/powerflow/jacobian.py          (same for every method)
        └─ solve J·Δx = −F  ← src/powerflow/newton.py's solve_linear_step()
                 dispatches by the `method` string to exactly ONE of:
                    src/solvers/direct.py      method="direct"
                    src/solvers/svd_pinv.py    method="svd"
                    src/solvers/rrqr.py        method="rrqr"
                    src/solvers/tikhonov.py    method="tikhonov"
```

All four solver modules share one `(dx, diagnostics)` return contract:
`dx=None` signals failure; a nonzero least-squares residual after rank
truncation is NOT itself a failure.

### Data flow, end to end

```
official feeder data (verbatim, unmodified)
  src/model/ieee13_data.py / ieee37_data.py / ieee69_data.py
        │
        ▼  apply the paper's stated modifications + documented assumptions
experiments/expNN_*.py :: build_*_system()
        │
        ├──► NetworkState   (src/model/state.py)   — who are the unknowns
        └──► Ybus            (src/model/ybus.py)    — the network admittance
        │
        ▼
src/powerflow/newton.py :: newton_raphson()   ← the one shared NR loop (see above)
        │
        ▼
result = {converged, x, iterations, history, fail_reason}
        │
        ├──► src/diagnostics/sequence_components.py   (V0/V1/V2, line-to-line)
        ├──► results/*.csv                              (gitignored, regenerate locally)
        ├──► report/figures/*.{pdf,png}                 (tracked — paper deliverable)
        └──► OpenDSS cross-validation (experiments/exp*b/*c_*crosscheck.py)
```

### Module reference

**`src/model/`**
- `state.py` — `BusPhase` (one phase at one bus: name, phase, active,
  is_slack, V_slack, P_spec, Q_spec) and `NetworkState` (two index maps:
  `busphase_index` for all active bus-phases, `unknown_index` for
  non-slack only). Rectangular coordinates `(e=Re(V), f=Im(V))`, not
  polar — this avoids trig terms in the Jacobian and angle-wrap issues.
  `init_flat_start()`, `unpack()`/`pack()` convert between the flat real
  vector and a `{(bus,phase): complex}` dict.
- `ybus.py` — `stamp_line_series_admittance()` (phase-coupled series
  branch; `Yprim = inv(Z)`, the **matrix inverse**, not elementwise
  reciprocal — real distribution lines have genuine mutual coupling) and
  `stamp_transformer()` (Yg/Delta winding connection matrices; this is
  where the singularity is actually born — `C_DELTA` has both row and
  column sums equal to zero, i.e. it's rank 2 with null vector `(1,1,1)`,
  which is the algebraic origin of the floating common-mode direction;
  ungrounded wye `"y"` deliberately raises `NotImplementedError` rather
  than silently returning a wrong answer, since it needs a Kron reduction
  the current lumped model doesn't do).
- `ieee13_data.py`, `ieee37_data.py`, `ieee69_data.py` — verbatim official
  source data (line codes, branches, loads). Paper modifications are
  applied in the corresponding `experiments/expNN_*.py`, NOT here — keep
  that separation when adding a new feeder.

**`src/powerflow/`**
- `mismatch.py` — `compute_mismatch(x, state, Ybus) → F`. Only
  constant-PQ loads are supported (a documented limitation — see §8 on
  delta loads).
- `jacobian.py` — `compute_jacobian(x, state, Ybus) → J`, the analytical
  Jacobian. **Must pass finite-difference validation before being
  trusted** (see §6 — this is a hard gate, not optional).
- `newton.py` — the shared loop, described above. `compute_conditioning=True`
  costs an extra O(n³) SVD per iteration purely for diagnostics (κ₂,
  σ_min, σ_max, rank) — turn it off for any runtime measurement.

**`src/solvers/`** (all four share the same call/return contract)
- `direct.py` — `numpy.linalg.solve` (LU) + an explicit condition-number
  guard: if `κ₂(J) > 1e12`, the update is discarded even though LU
  nominally succeeded (LU only throws when a pivot is *exactly* zero,
  which almost never happens for merely near-singular matrices). Two
  distinct failure modes are logged and must not be conflated:
  `exact_singular` (LinAlgError) vs `ill_conditioned` (guard fired).
- `svd_pinv.py` — explicit `J = UΣVᴴ`, threshold `τ = max(atol, rtol·σ_max)`,
  retain `σ_i > τ` strictly, `Δx = V·diag(σ⁺)·Uᴴ·rhs`. Deliberately does
  NOT call `numpy.linalg.pinv`, so the rank decision is visible and
  logged. Reports both a raw condition number (smallest reported σ) and
  an effective one (smallest *retained* σ) — these differ once truncation
  happens; don't conflate them.
- `rrqr.py` — pivoted QR (`scipy.linalg.qr(..., pivoting=True)`, used only
  for rank/pivot/`|R_ii|` diagnostics) + LAPACK GELSY
  (`scipy.linalg.lstsq(..., lapack_driver="gelsy")`, the actual
  minimum-norm least-squares solve via complete orthogonal
  factorization). Ordinary unpivoted QR + back-substitution is
  deliberately avoided — for singular `J`, `R` is itself rank-deficient
  and back-substitution divides by a near-zero pivot.
- `tikhonov.py` — solves `min ‖JΔx − rhs‖² + λ‖Δx‖²` via the **augmented
  system** `[[J],[√λ·I]]·Δx ≈ [[rhs],[0]]`. Never forms `JᵀJ` explicitly
  (would square the condition number — the exact failure mode under
  study, not a fix for it). `λ = α·σ_max(J)²` (scale-aware, so a fixed α
  means comparable damping across differently-scaled Jacobians).

**`src/diagnostics/sequence_components.py`** — the standard Fortescue
`abc ↔ 012` transform. `V0` is precisely the common-mode component a
floating delta leaves undetermined — the key analytical tool for the
IEEE-13 zero-sequence investigation. Also `line_to_line_magnitudes()`,
used throughout cross-validation because line-to-line voltages stay
physically well-determined even when phase voltages don't.

**`src/validation/`** (pre-existing OpenDSS pipeline, 4-bus)
- `opendss.py` — compile/solve/export. Note: OpenDSS's `compile` command
  changes the whole process's working directory as a side effect; this
  module captures `os.getcwd()` at import time and explicitly `chdir`s
  back afterward so it doesn't leak into the next call.
- `crosscheck.py` — 4-bus NR vs OpenDSS with PASS/FAIL tolerances.
- `antifloat_study.py` — sweeps OpenDSS's `PPM_Antifloat` transformer
  property, investigating whether OpenDSS silently regularizes away the
  very singularity this project studies.

**`experiments/`** — one runnable script per experiment, each with a
docstring explaining what it does and why:
- `exp01_4bus.py` — 4-bus baseline (Case A healthy / Case B singular).
- `exp02_13bus.py` — `build_13bus_system()`, with a long, important
  docstring documenting every reconstruction assumption.
- `exp02b_13bus_opendss_crosscheck.py` — IEEE-13 vs OpenDSS.
- `exp_d_ieee13_investigation.py` — the project's centerpiece: solver
  robustness vs load, load scaling, phase imbalance (0-30%), transformer
  grounding configuration.
- `exp_d_ieee13_tikhonov_alpha_sweep.py` — reproducible α-sensitivity
  sweep pinning the reported `alpha=1e-8` choice.
- `exp03_37bus.py` — `build_37bus_system()`, including a
  `quasi_radial=True` variant generated programmatically (not a second
  hand-maintained copy).
- `exp03b_37bus_opendss_crosscheck.py` / `exp03c_37bus_quasiradial_opendss_crosscheck.py`
  — IEEE-37 radial / quasi-radial vs OpenDSS.
- `exp04_69bus.py` — `build_69bus_system()`.
- `exp04b_69bus_opendss_crosscheck.py` — IEEE-69 vs OpenDSS.
- `exp_e_ieee118_scaling.py` — **not a power-flow case**; loads the real
  `pandapower.case118` admittance matrix, block-replicates it to build a
  runtime-scaling curve from genuine sparse structure, and times all four
  solvers directly.
- `exp_b_svd_*.py` / `exp_c_rrqr_*.py` / `exp_d_tikhonov_*.py` — per-solver
  4-bus experiments and threshold/alpha sweeps.
- `member_{b,c,d}_utils.py` — small per-owner reporting helpers,
  deliberately duplicated rather than shared across files to respect
  each original team member's file-ownership boundaries.
- Every `exp*b_*`/`exp*c_*` OpenDSS crosscheck script's `compare()`
  function **returns** `(median_rel_err, max_rel_err)` in addition to
  printing, so `report/make_figures.py` can call them directly to build
  figures from live data — keep this contract if you add another one.

**`tests/`** — mirrors the above. Several test files carry long
docstrings containing actual derivations, not just assertions — read
these when a feeder's behavior surprises you:
- `test_jacobian.py` — the finite-difference gate (also runnable as a
  plain script).
- `test_{svd_pinv,rrqr,tikhonov}.py` — synthetic-matrix unit tests.
- `test_linear_solvers.py` — cross-solver comparisons on controlled
  spectra.
- `test_*_integration_4bus.py` — shared-loop dispatch checks.
- `test_ieee{13,37,69}.py` — per-feeder FD gate + structural regressions
  (e.g. `test_ieee13.py::test_flat_start_jacobian_has_exactly_two_near_zero_singular_values`
  explains *why* it's 2, not 1; `test_ieee69.py::test_flat_start_jacobian_is_ill_conditioned_but_not_exactly_singular`
  carries the full argument for why that feeder differs from 13/37).
- `test_ieee13_investigation.py`, `test_sequence_components.py`,
  `test_ieee118_scaling.py`, `test_opendss.py`.

**`data/`**
- `provenance.yml` — **the authoritative record.** Source URL + retrieval
  date for every feeder, every paper-specified parameter actually used,
  every reconstruction assumption, every unresolved discrepancy. Read
  this before citing any number from this repo.
- `raw/ieee{4,13,37,69}/` — official `.dss`/data files plus this
  project's paper-modified OpenDSS twins (used for cross-validation). The
  IEEE-69 twin is *generated* by `gen_ieee69_dss.py` from
  `ieee69_data.py` — regenerate it that way if the data ever changes;
  don't hand-edit 65 branches.

**`report/`**
- `paper.tex` / `paper.pdf` / `refs.bib` — the draft paper.
- `make_figures.py` — regenerates all figures in `report/figures/` from
  live experiment runs, not remembered numbers. Rerun this if any cited
  experiment changes before treating a paper draft as final.
- `figures/*.{pdf,png}` — tracked (unlike the top-level `results/`,
  `figures/` dirs, which hold ephemeral sweep output and are gitignored).

**`README.md`** — the public-facing "how to run this, what state it's in"
reference. Some content overlaps this file but is written for outside
readers rather than as an onboarding document for continuing work.

---

## 4. How to run things

### Setup and test
```bash
pip install -r requirements.txt     # numpy, scipy, opendssdirect.py, pandas,
                                     # pyyaml, pandapower, matplotlib, pytest
python -m pytest -q
```

Known environment quirk: `opendssdirect` + pytest's assertion-rewrite
collection has intermittently crashed (a native-extension fault, not a
Python exception) on Python 3.14/Windows — not every run, and running the
same OpenDSS code as a plain script is always reliable. If `pytest`
crashes with no summary, re-run with `--ignore=tests/test_opendss.py`.

### Core experiments (each prints a self-contained report)
```bash
python experiments/exp01_4bus.py
python experiments/exp02_13bus.py
python experiments/exp03_37bus.py
python experiments/exp04_69bus.py
```

### Sensitivity sweeps (write CSVs + plots to results/, figures/ — gitignored, regenerate locally)
```bash
python experiments/exp_b_svd_tolerance_4bus.py
python experiments/exp_d_tikhonov_lambda_sweep_4bus.py
python experiments/exp_d_ieee13_tikhonov_alpha_sweep.py
python experiments/exp_d_ieee13_investigation.py     # the main investigation
python experiments/exp_e_ieee118_scaling.py
```

### OpenDSS cross-validation (plain scripts, never under pytest)
```bash
python -m src.validation.opendss
python -m src.validation.crosscheck
python -m src.validation.antifloat_study
python experiments/exp02b_13bus_opendss_crosscheck.py
python experiments/exp03b_37bus_opendss_crosscheck.py
python experiments/exp03c_37bus_quasiradial_opendss_crosscheck.py
python experiments/exp04b_69bus_opendss_crosscheck.py
```

### Producing the report
```bash
python report/make_figures.py
cd report && pdflatex paper.tex && bibtex paper && pdflatex paper.tex && pdflatex paper.tex
```

---

## 5. Why the OpenDSS cross-validation errors vary so much by feeder

IEEE-13 and IEEE-37 have a genuinely **underdetermined** subspace (the
floating common-mode direction discussed in §1/§3). This project's
Tikhonov regularization and OpenDSS's own internal `PPM_Antifloat`
admittance each pick a *different legitimate point* within that subspace
— that is the phenomenon under study, not a validation failure. IEEE-69
has no such ambiguity (verified: its flat-start Jacobian has zero
near-zero singular values, unlike IEEE-13's 2 and IEEE-37's 4), which is
exactly why its cross-validation agreement is near machine precision.
That contrast is the negative control supporting the whole reading — if
you see a large cross-validation discrepancy on 13/37, that alone is not
evidence of a bug; check whether it's concentrated at bus/phase pairs
aligned with the near-null subspace before assuming otherwise.

---

## 6. The one hard gate: Jacobian finite-difference validation

Before trusting **any** result from a new or modified feeder
reconstruction, validate the analytical Jacobian against centered finite
differences:

```
E_J = ‖J_analytic − J_FD‖_F / ‖J_FD‖_F      must be < 1e-6
```

All four existing feeders sit around `1e-11`. This is implemented in
`tests/test_jacobian.py` (reusable helpers `finite_difference_jacobian()`
and `compute_relative_frobenius_error()`) and repeated per-feeder in each
`test_ieee*.py`. Do this FIRST, before running any solver comparison on a
new system — an unvalidated Jacobian invalidates everything downstream of
it.

---

## 7. The per-unit load convention — this caused two real, separate bugs

```
P_pu = P_phase_actual_kW / (S_base_kVA / 3)
```

Note the **per-phase** base, `S_base/3`. If what you have is a bus's
*total* three-phase load (e.g. a MATPOWER-style `Pd`, or an OpenDSS
3-phase load object's `kW`), you must divide by 3 **first** to get the
per-phase actual value, THEN apply the formula above.

Two independent bugs of this exact category were found and fixed during
this project's development:
- **IEEE-13**: per-phase load was normalized against the *full* 3-phase
  base instead of the per-phase base → every load 3x too light.
- **IEEE-69**: a bus's already-*total* load was applied directly to every
  phase without dividing by 3 → every load 3x too heavy.

Both were caught the same way, and this is the single most valuable
methodological habit in this codebase: **cross-validate a small,
well-conditioned sub-circuit against OpenDSS BEFORE trusting a
comparison on the full, already-ill-conditioned system.** On an
ill-conditioned full system, a genuine scale bug and the expected
disagreement from an underdetermined null space are difficult to tell
apart (the IEEE-69 bug's full-system symptom was an unremarkable-looking
~33% error at one bus, not an obviously-wrong number); on an isolated,
well-conditioned sub-circuit there is no such ambiguity. **Do this every
time you add a feeder or touch load-scaling code, not just when something
already looks wrong.**

---

## 8. Documented approximations and open discrepancies — do not silently resolve these

**Deliberate approximations** (real simplifications, not bugs):
- Delta-connected loads are approximated as wye-equivalent (a delta leg's
  kW/kvar split evenly across its two phases), because
  `src/powerflow/mismatch.py` only supports phase-to-neutral constant-PQ
  injection, not true delta-branch current stamping. Extending the shared
  model to true delta loads would be a legitimate next project.
- All loads are treated as constant-PQ regardless of the official
  source's per-load model number.
- Voltage regulators and near-zero-impedance switches are merged to ideal
  (zero-impedance) connections — modeling discrete tap-changing control
  is a different (hybrid discrete/continuous) numerical problem, out of
  scope for this NR-solver comparison project.
- Line shunt (charging) capacitance is not modeled.

**Open discrepancies** (in `data/provenance.yml`, flagged rather than
resolved):
- IEEE-13: the paper states its modified case has "seven loads"; the
  official data, after removing the one location clearly meant (the
  distributed-load stand-in), still has eight distinct load locations.
  Kept all eight rather than arbitrarily deleting one.
- IEEE-37: the paper reports XFM1 reactance X≈0.00181 pu; official
  OpenDSS data gives `Xhl=1.81%` (0.0181 pu on its own base) — an apparent
  factor-of-10 discrepancy. `build_37bus_system()` exposes
  `xfm1_xhl_percent` so either can be built; the official value is the
  default.
- IEEE-69: the paper's transformer table gives 13.8 kV; the actual
  `case69` bus voltage base is 12.66 kV. The network's real voltage
  (12.66 kV) is used, and the mismatch is flagged rather than "fixed".
- No 30%-unbalanced variant exists for IEEE-13 or IEEE-69: neither the
  paper nor the official data specify a phase-by-phase construction rule
  for it. The zero-sequence finding (§1) uses an explicitly documented,
  project-defined imbalance rule instead — not an attempt to reproduce
  this specific unspecified construction.

---

## 9. Working conventions to keep following

- Every non-obvious modeling choice gets a code comment or docstring
  explaining WHY (not just what) — citing either the relevant handoff/plan
  reasoning or an empirical finding from developing that file. This is
  what makes every reconstruction assumption auditable; keep doing it.
- Before trusting a new feeder reconstruction: (1) validate the Jacobian
  against finite differences FIRST (§6), (2) if introducing a new
  per-unit/scaling convention, verify it against an isolated,
  well-conditioned sub-circuit compared to OpenDSS BEFORE building the
  full (likely ill-conditioned) system (§7) — do not assume a full-system
  comparison alone will catch a scale bug.
- Tests are the source of truth for current numerical behavior, not just
  a pass/fail check — several encode the actual structural reasoning
  behind a finding (§3's `tests/` reference above). Read them, don't just
  run them.
- Prefer editing/extending the shared architecture (one NR loop, one
  dispatch point in `src/powerflow/newton.py`) over writing a parallel
  code path for a new solver or feeder.
- Commit messages in this repo: terse, state only what changed, no
  references to internal planning/process documents.
- This file (`STRUCTURE.md`) is tracked and public — unlike some other
  internal working documents that may exist in a `.gitignore`d state in
  this repo (check `.gitignore` if you're looking for prior session notes
  and don't find them tracked; they may still be present locally on the
  device that wrote them, just not shared via git).
