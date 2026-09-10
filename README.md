# Robust Newton–Raphson Power Flow — Numerical Analysis Project

CSE402 Numerical Analysis, Simulation and Modelling course project. Reproduces
and extends Jang, Kim & Kim, *"Singularity Handling for Unbalanced Three-Phase
Transformers in Newton-Raphson Power Flow Analyses Using Moore-Penrose
Pseudo-Inverse,"* IEEE Access, 2023
([doi:10.1109/ACCESS.2023.3269503](https://doi.org/10.1109/ACCESS.2023.3269503)).

Full project context, terminology, and every modeling decision's rationale
live in [`handoff.md`](handoff.md) (the authoritative spec) and
[`robust_nr_powerflow_6_week_plan.md`](robust_nr_powerflow_6_week_plan.md)
(the team's implementation plan). **This file is the practical "how to run
this repo, and what state it's actually in" reference** — read `handoff.md`
first for *why*, this file for *how*.

## What this project does

Ungrounded/floating three-phase transformer connections (Yg–Delta,
Delta–Delta) can make a Newton–Raphson power-flow Jacobian singular or
severely ill-conditioned. This project implements one shared three-phase NR
solver and compares four ways of handling that linear-solve step:

| Method | File | Idea |
|---|---|---|
| Direct | [`src/solvers/direct.py`](src/solvers/direct.py) | `numpy.linalg.solve`, with an explicit condition-number guard |
| SVD / Moore–Penrose | [`src/solvers/svd_pinv.py`](src/solvers/svd_pinv.py) | Explicit thresholded pseudo-inverse |
| Rank-revealing QR | [`src/solvers/rrqr.py`](src/solvers/rrqr.py) | Pivoted QR + GELSY complete-orthogonal least squares |
| Tikhonov | [`src/solvers/tikhonov.py`](src/solvers/tikhonov.py) | Regularized augmented-system least squares |

on three reconstructed IEEE test feeders (4-bus, 13-bus, 37-bus), each
independently cross-validated against OpenDSS, plus a controlled
sensitivity investigation of the IEEE-13 feeder's anomalously large error
(the paper's own open question — see `handoff.md` section 6).

## Quick start

```bash
pip install -r requirements.txt
python -m pytest -q                      # run the test suite
python experiments/exp01_4bus.py         # IEEE 4-bus: direct solver failure reproduction
python experiments/exp02_13bus.py        # IEEE 13-bus: direct/SVD/RRQR/Tikhonov comparison
python experiments/exp03_37bus.py        # IEEE 37-bus: same comparison
```

Every experiment script is runnable standalone (`python experiments/<script>.py`)
and prints a self-contained report; none require a notebook or extra setup
beyond `requirements.txt`.

## Repository map

```text
src/
  model/          Bus/phase state representation, Ybus assembly (lines +
                   Yg/Delta transformer stamping), and the raw official
                   feeder data modules (ieee13_data.py, ieee37_data.py).
  powerflow/       Shared mismatch F(x), analytical Jacobian J(x), and the
                   Newton-Raphson loop every solver plugs into.
  solvers/         The four linear-solver implementations listed above.
  diagnostics/     Symmetrical-component (zero/pos/neg-sequence) analysis,
                   used by the IEEE-13 investigation.
  validation/      OpenDSS reference pipeline (compile/solve/export) and
                   the 4-bus NR-vs-OpenDSS crosscheck.

experiments/
  exp01_4bus.py                        IEEE 4-bus baseline (direct fail / recover)
  exp_b_svd_*.py                       SVD solver experiments + threshold sweep
  exp_c_rrqr_*.py                      RRQR experiments + RRQR-vs-SVD comparison
  exp_d_tikhonov_*.py                  Tikhonov experiments + alpha sweep
  exp02_13bus.py                       IEEE 13-bus reconstruction + 4-solver comparison
  exp02b_13bus_opendss_crosscheck.py   IEEE 13-bus independent OpenDSS validation
  exp_d_ieee13_investigation.py        IEEE-13 anomaly investigation (see below)
  exp03_37bus.py                       IEEE 37-bus reconstruction + 4-solver comparison
  exp03b_37bus_opendss_crosscheck.py   IEEE 37-bus independent OpenDSS validation
  exp04_69bus.py                       IEEE 69-bus reconstruction + 4-solver comparison
  exp_e_ieee118_scaling.py             IEEE 118-bus linear-solver runtime scaling

data/
  provenance.yml    Source and every reconstruction assumption for each feeder
  raw/ieee4/        4-bus OpenDSS reconstruction (Member E)
  raw/ieee13/        Official IEEE13Nodeckt.dss + this project's paper-modified twin
  raw/ieee37/        Official ieee37.dss + this project's paper-modified twin

tests/              pytest suite (see "Testing" below)
results/, figures/  Generated CSVs/plots from the sweep experiments (gitignored)
```

## Current status

All four solvers are implemented, unit-tested, and validated against each
other on IEEE 4/13/37-bus. This corresponds to the "Minimum Viable Scope"
in `handoff.md` section 30, items 1–9 — the project's core deliverables are
complete.

| Feeder | Reconstructed | Jacobian FD-validated | Direct/SVD/RRQR/Tikhonov run | OpenDSS cross-validated |
|---|:-:|:-:|:-:|:-:|
| IEEE 4-bus  | ✅ | ✅ | ✅ | ✅ (~1e-6 pu agreement) |
| IEEE 13-bus | ✅ | ✅ | ✅ | ✅ (median 6.6%, max 26.5% line-to-line error — see below) |
| IEEE 37-bus (radial + quasi-radial) | ✅ | ✅ | ✅ | ✅ radial (median 2.3%, max 6.5%); quasi-radial not yet cross-validated |
| IEEE 118-bus | ✅ (linear-solver scaling only, per `handoff.md` §20 — not a power-flow/singularity case) | — | — | n/a |
| IEEE 69-bus | ✅ | ✅ | ✅ | ❌ not built for this lowest-priority stretch case |

All items in `handoff.md` section 31's stretch-goal list are now done.
Nothing from the project's planned scope remains unattempted; see
`data/provenance.yml` for each feeder's open, explicitly-documented
discrepancies (never silently resolved).

### Headline findings

- **IEEE 4-bus**: reproduces the paper's qualitative failure mode. The
  direct solver's condition number reaches `κ≈7.8e11` on the
  no-secondary-load Yg-Delta case; SVD/RRQR/Tikhonov all recover. See
  [`verified_output.md`](verified_output.md).
- **IEEE 13-bus**: the *paper-specified* modification (T1 → Yg-Delta, T2 →
  Delta-Delta) leaves the **entire downstream network floating with no
  ground reference anywhere** — the flat-start Jacobian is singular to
  machine precision (`κ≈4.5e18`) with **exactly 2 near-zero singular
  values** (T1's network-wide floating secondary, plus T2's independent
  floating reference at bus 634 — a Delta-Delta transformer's zero-sequence
  transfer block is exactly zero). At this reconstruction's realistic load
  level, **SVD and RRQR's undamped minimum-norm Newton steps oscillate
  instead of converging** — only Tikhonov regularization converges
  cleanly, up to 1.25× nominal load. See
  [`experiments/exp_d_ieee13_investigation.py`](experiments/exp_d_ieee13_investigation.py).
- **Load imbalance loads almost entirely onto the zero-sequence (V0)
  component**, not positive-sequence: a direct, quantitative confirmation
  of the project's own zero-sequence hypothesis (`handoff.md` section 7).
  Grounding both transformers brings `κ` down from `4.5e18` to `~773` and
  `V0` from `0.29` to `0.01` pu.
- **IEEE 37-bus**, by contrast, does *not* show the SVD/RRQR oscillation —
  a concrete demonstration that no single solver or fixed regularization
  strength is uniformly best across feeders (motivating the project's
  whole comparative-methods premise).
- **IEEE 69-bus**: unlike IEEE-13/37, the direct solver actually
  *converges* here (`κ≈2.3e5` at flat start, growing to `~6.5e9` during
  iteration — severe, but under the guard threshold). Ybus itself still has
  an exact null direction across each floating transformer's downstream
  region (confirmed numerically), but the nonlinear Jacobian's degeneracy
  there is proportional to the real current already flowing — since this
  region carries most of the feeder's load, it's severely ill-conditioned
  rather than exactly singular. A genuine structural finding, not a
  reconstruction defect: not every floating-Delta topology produces exact
  flat-start singularity. See
  [`tests/test_ieee69.py`](tests/test_ieee69.py) for the full derivation.
- **IEEE 118-bus** (linear-solver scaling only, not a singularity case —
  `handoff.md` section 20): benchmarked on the real pandapower `case118`
  admittance matrix, block-replicated up to 8× (~1900×1900 real Jacobian
  form). All four solvers show empirical wall-clock scaling exponents
  around 2.2–2.5 across that range (sub-cubic at these sizes, as expected
  from BLAS-level dense-solver optimizations) — see
  [`experiments/exp_e_ieee118_scaling.py`](experiments/exp_e_ieee118_scaling.py).
- Every one of these numbers came from a **real bug caught by cross-
  validation**: an earlier version of the IEEE-13 per-phase load
  normalization was off by a factor of 3 (dividing by the full 3-phase
  base instead of the per-phase base). Caught via an isolated,
  well-conditioned single-transformer OpenDSS comparison, fixed, and
  re-verified to ~3e-6 pu agreement there. See the git history around
  `experiments/exp02_13bus.py` for the full investigation — a worked
  example of exactly the kind of independent-solver validation
  `handoff.md` calls for.

## Testing

```bash
python -m pytest -q                       # full suite
python -m pytest -q --ignore=tests/test_opendss.py   # skip OpenDSS-collection tests
```

Tests are organized by what they gate:

- `test_jacobian.py`, `test_ieee13.py::test_jacobian_13bus_*`,
  `test_ieee37.py::test_jacobian_37bus_*` — the mandatory finite-difference
  Jacobian validation (`handoff.md` section 22): nothing downstream is
  trusted until these pass.
- `test_linear_solvers.py`, `test_svd_pinv.py`, `test_rrqr.py`,
  `test_tikhonov.py` — controlled synthetic-matrix tests per solver.
- `test_svd_integration_4bus.py`, `test_rrqr_integration_4bus.py`,
  `test_tikhonov_integration_4bus.py` — shared-NR-loop dispatch checks.
- `test_ieee13.py`, `test_ieee37.py`, `test_ieee13_investigation.py`,
  `test_sequence_components.py` — feeder-level regression tests, including
  the structural findings above (near-zero singular value counts, solver
  convergence/oscillation behavior, V0-vs-V1 sensitivity).
- `test_opendss.py` — see "Known environment issues" below.

## Known environment issues

- **`opendssdirect` + pytest assertion-rewrite collection can crash** on
  this project's Python 3.14 / Windows environment (a native-extension
  fault, not a Python exception, observed intermittently — not every run).
  Running the same OpenDSS code as a plain script
  (`python -m src.validation.opendss`, or any `exp*_opendss_crosscheck.py`)
  is reliable; only pytest's *collection* of `tests/test_opendss.py`
  is affected. If `pytest` crashes outright with no test summary, re-run
  with `--ignore=tests/test_opendss.py` and run the OpenDSS validation
  scripts directly instead.
- `requirements.txt` is not yet frozen with exact pinned versions
  (`pip freeze > requirements-lock.txt` has not been run).

## Data provenance

[`data/provenance.yml`](data/provenance.yml) documents, for every feeder:
the official source URL and retrieval date, every paper-specified
parameter actually used, and every reconstruction assumption this project
made where the paper or the official data left something unspecified
(load-splitting rules, per-unit base choices, simplifications like merging
voltage regulators to ideal connections). Read it before citing any number
from this repo in a report — it also records open, unresolved discrepancies
(e.g. IEEE-13's "seven loads" vs. this reconstruction's eight, and the
IEEE-37 XFM1 reactance factor-of-10 question flagged in `handoff.md`
section 17) rather than silently picking an answer.

## Reproducing the OpenDSS cross-validations (Member E's track)

```bash
pip install -r requirements.txt   # includes opendssdirect
python -m src.validation.opendss             # generate OpenDSS references (4-bus)
python -m src.validation.crosscheck          # 4-bus NR vs OpenDSS
python -m src.validation.antifloat_study     # PPM_Antifloat sensitivity (4-bus)
python experiments/exp02b_13bus_opendss_crosscheck.py   # 13-bus NR vs OpenDSS
python experiments/exp03b_37bus_opendss_crosscheck.py   # 37-bus NR vs OpenDSS
```

## Sensitivity / sweep experiments

These write CSVs to `results/` and plots to `figures/` (both gitignored —
regenerate locally):

```bash
python experiments/exp_b_svd_tolerance_4bus.py       # SVD rank-threshold sweep
python experiments/exp_d_tikhonov_lambda_sweep_4bus.py  # Tikhonov alpha sweep
python experiments/exp_d_ieee13_investigation.py     # load/imbalance/transformer-config/solver-robustness studies
python experiments/exp_e_ieee118_scaling.py          # linear-solver runtime scaling (balanced, no singularity)
```

## Team ownership (per `handoff.md` section 26)

| Member | Owns |
|---|---|
| A | Core NR: `src/model/`, `src/powerflow/`, `src/solvers/direct.py`, `experiments/exp01_4bus.py` |
| B | `src/solvers/svd_pinv.py` and its experiments/tests |
| C | `src/solvers/rrqr.py` and its experiments/tests |
| D | `src/solvers/tikhonov.py`, the IEEE-13 investigation |
| E | `src/validation/` (OpenDSS), `data/provenance.yml`, this README |

The IEEE-13/37 reconstructions (`src/model/ieee13_data.py`,
`src/model/ieee37_data.py`, `experiments/exp02_13bus.py`,
`experiments/exp03_37bus.py`) and `src/diagnostics/` were built in one pass
spanning several members' nominal ownership areas (feeder reconstruction
is Member A/E's territory in the original plan) once it became clear they
were the project's critical path; see git history for the detailed
rationale at each step.
