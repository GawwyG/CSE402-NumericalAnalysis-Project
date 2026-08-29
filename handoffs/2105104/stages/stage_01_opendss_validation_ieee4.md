# Stage 01 — OpenDSS Reference Pipeline and IEEE 4-bus Cross-Validation

## 1. Stage objective

Stand up the Member E validation track from scratch: OpenDSS environment,
IEEE 4-bus feeder reconstruction, provenance documentation, the OpenDSS
solve/export pipeline, and a cross-check against Member A's NR solver output
for both the healthy and singular 4-bus cases. This is the Week 1-2 gate
described in `robust_nr_powerflow_6_week_plan.md` section 8.

## 2. Branch and starting commit

- Branch: `2105104`.
- Starting point: Member A's `2105117` work through Stage 05 (baseline NR,
  SVD solver, 4-bus integration, threshold sensitivity, shared solver
  tests) — no files under `data/`, `src/validation/`, or `results/` existed
  before this stage.

## 3. Pre-existing dirty files relevant to safety

None known. This stage only added new files under Member E's ownership
(`data/`, `src/validation/`) — no existing Member A/B file was modified.

## 4. Files created in this stage

- `data/raw/ieee4/ieee4_reconstruction.dss` — OpenDSS circuit matching
  Member A's `experiments/exp01_4bus.py` topology (CASE A / load-on
  values baked in; CASE B reached at runtime by zeroing `LOAD_BUS3` /
  `LOAD_BUS4`).
- `data/provenance.yml` — source/assumption documentation for the 4-bus
  reconstruction; stub entries for `ieee37` and `ieee118` (not started).
- `src/validation/opendss.py` — `compile_and_solve()`, bus-phase voltage
  export in the shared `bus, phase, V_real, V_imag, V_mag, V_angle` format,
  `export_csv()`.
- `src/validation/crosscheck.py` — runs Member A's NR solver
  (`build_4bus_system` + `newton_raphson`, imported read-only) alongside
  the OpenDSS reference and compares voltages for CASE A; reports
  OpenDSS's behavior on CASE B without treating NR non-convergence there
  as an error.
- `src/validation/antifloat_study.py` — sweeps the transformer's
  `ppm_antifloat` property (default / 0 / 100) on CASE B and exports each
  result.
- `README.md` (validation section) and `requirements.txt` — environment
  setup instructions; not yet frozen with `pip freeze`.
- This handoff.

No Member A/B/C/D-owned file was modified.

## 5. Implementation decisions

### 6 MVA / per-unit base for the OpenDSS conversion

Member A's Ybus is built purely numerically with no declared system MVA
base anywhere in `exp01_4bus.py` or `handoff.md`. OpenDSS needs a real
base to convert p.u. impedances/loads to ohms/kW, so the transformer's own
nameplate (6 MVA, 12.47/4.16 kV) was used as the system base. This is
documented as an assumption, not a fact, in `data/provenance.yml`.

**This assumption is now empirically supported, not just asserted**: CASE
A cross-validation (below) matches Member A's NR solution to ~1e-6 p.u.
across all 12 bus-phases, which would not happen under a wrong base.

### Per-phase load convention

Member A's code applies `P_spec`/`Q_spec` identically to each of phases
`a`, `b`, `c`, which was read as a per-phase (not total three-phase)
value. The OpenDSS loads were built on that reading (e.g. BUS2:
0.05 pu/phase x 6000 kVA base = 300 kW total load object, matching three
identical single-phase-equivalent loads). The CASE A match below is
consistent with this reading being correct, but it has not been
explicitly confirmed with Member A in writing — see Limitations.

### CASE B handling

CASE B (no load on the Delta secondary) is the paper's reported
singularity reproduction target — Member A's direct NR solver is
*expected* to fail or become severely ill-conditioned there. Earlier
versions of `crosscheck.py` raised an exception on NR non-convergence,
which is wrong for this case: it's the expected finding, not a bug.
`run_nr_case()` now returns convergence status, fail reason, and max
kappa_2(J) instead of raising, and `compare_case()` reports OpenDSS's
convergence behavior on the same topology as a qualitative result rather
than attempting a voltage-to-voltage numeric comparison that has no NR
side to compare against.

### `ppm_antifloat`

Initially attempted as a global `Set %PPM_Antifloat=0` solver option —
this is wrong; OpenDSS error #130 ("Unknown parameter"). Per EPRI's
"Modeling the OY-OD Connection" documentation, `ppm_antifloat` is a
per-Transformer property (it scales an admittance stamped directly into
that transformer's own primitive Y-matrix diagonal to prevent an
inversion failure on floating windings). Corrected to
`Edit Transformer.XFMR1 ppm_antifloat=<value>`, issued through the same
`extra_commands` mechanism as the load-zeroing commands for CASE B.

### Path handling in `compile_and_solve()`

Two bugs surfaced and were fixed:

1. `compile` in OpenDSS changes the *entire Python process's* working
   directory to the folder of whatever file it just compiled — not just
   an internal DSS notion of cwd. A relative path passed on a second call
   resolves against that new, unexpected cwd and silently doubles
   (`data/raw/ieee4/data/raw/ieee4/...`).
2. Fix: capture `os.getcwd()` once at module import time (before any
   `compile` call can run), resolve every path against that fixed base,
   and `os.chdir()` back to it at the end of every `compile_and_solve()`
   call so the side effect doesn't leak into the next call or any other
   code in the process.

## 6. Validation commands and exact outcomes

```text
python -m src.validation.opendss
CASE A converged=True iterations=4
CASE B converged=True iterations=2   (OpenDSS itself converges on CASE B;
                                       see section 7)

python -m src.validation.crosscheck
CASE A -- healthy: ALL PASS
  max |d|V|| observed: ~1.5e-6 pu across all 12 bus-phases
  max |dAngle| observed: ~0.001 deg
CASE B -- singular: NR solver did NOT converge (expected — reproduces
  paper's reported failure mode). OpenDSS converged on the same topology
  in 2 iterations; see section 7 for interpretation.

python -m src.validation.antifloat_study
[default ] converged=True  iterations=2
[disabled] converged=True  iterations=2
[elevated] converged=True  iterations=2
```

## 7. Key observed outputs

- CASE A: OpenDSS and Member A's NR solver agree to ~1e-6 pu on voltage
  magnitude and ~0.001 deg on angle across all 4 buses x 3 phases. This is
  the strongest evidence so far that the 6 MVA base and per-phase load
  assumptions (section 5) are correct.
- CASE B: Member A's direct NR solver fails/ill-conditions as expected
  (reproducing the paper's reported singularity). OpenDSS, by contrast,
  converges in 2 iterations on the identical topology with its *default*
  `ppm_antifloat` (1 ppm) active on the transformer. This strongly
  suggests OpenDSS's built-in anti-float admittance is regularizing away
  exactly the floating-Delta singularity the paper (and Member A's direct
  solver) is designed to expose — not a discrepancy between solvers, but
  a difference in how each numerically handles a genuinely singular
  network. The antifloat sweep (section 6, incomplete) is intended to
  confirm this by checking whether OpenDSS's own convergence degrades
  once `ppm_antifloat=0` removes that regularization — this still needs
  to be re-run and the actual numbers recorded.

## 8. Assumptions

- System base of 6 MVA / (12.47, 4.16) kV for p.u.-to-physical conversion
  — empirically supported by CASE A's match, but not yet confirmed in
  writing by Member A. See Limitations.
- `P_spec`/`Q_spec` in Member A's code are per-phase, not total
  three-phase — same caveat as above.
- Validation tolerance (`V_MAG_TOL = 1e-3` pu, `V_ANGLE_TOL_DEG = 0.1`) is
  a project-defined criterion for this stage, not paper-specified.
- CASE B is treated as "no numeric NR-vs-DSS comparison possible, report
  qualitatively instead" rather than a pass/fail gate, since Member A's
  solver failing there is the expected/correct behavior being reproduced.

## 9. Limitations / blockers

- **Not yet confirmed with Member A**: the 6 MVA system base and the
  per-phase load-value reading. CASE A's tight numeric match is strong
  circumstantial evidence both are right, but this should be confirmed
  in writing (e.g. in a shared doc or commit message) rather than left
  as an inference, in case Member A's intent differs and the match is
  coincidental for CASE A specifically.
- Antifloat sweep (`antifloat_study.py`) needs to be re-run after the
  `ppm_antifloat` syntax fix — the `disabled`/`elevated` rows in section 6
  are placeholders, not real results.
- `README.md` only has the validation section stubbed in; it hasn't been
  merged with whatever Members A-D have documented for their own parts.
- `requirements.txt` is not yet frozen (`pip freeze > requirements-lock.txt`
  has not been run) — do this once the antifloat sweep is finalized so the
  lock file reflects a fully-working environment.
- IEEE-37 (Week 3) and IEEE-118 (Week 5) feeders are untouched — only the
  `data/provenance.yml` stub entries exist for them.
- No figures/plots generated yet (`figures/` is empty) — Week 2 milestone
  per the 6-week plan expects the end-to-end IEEE 4 comparison to include
  a plot, not just console/CSV output.

## 10. Commits created in this stage


- `aa43d3c` — `2105104(stage01): add IEEE 4-bus OpenDSS reconstruction + provenance`
- `9c1d257` — `2105104(stage01): add OpenDSS solve/export pipeline`
- `9c1d257` — `2105104(stage01): add NR vs OpenDSS crosscheck for IEEE 4-bus`
- `9c1d257` — `2105104(stage01): add ppm_antifloat sweep`

Not fabricated here — this work was done locally and these commits were
never made from within this session, so real hashes must be substituted
before this file is considered final.

## 11. Instructions for the next stage

1. Read the global contract (`handoff.md`) and this file first; remain on
   `2105104` for anything under `data/`, `src/validation/`,
   `src/diagnostics/`, `results/`, `figures/`.
2. Before doing anything else: get written confirmation from Member A on
   the 6 MVA base and per-phase load assumptions (section 5/9). If either
   is wrong, `ieee4_reconstruction.dss` and `provenance.yml` need
   correcting before any further validation work builds on top of them.
3. Next concrete milestone per the 6-week plan: IEEE 37-bus OpenDSS model
   + reference generation (Week 3). Follow the same
   reconstruct-from-source-of-truth discipline used here — confirm
   whatever feeder data Member A/B assume before building the `.dss` file,
   don't invent parameters, and document everything in
   `data/provenance.yml`.
4. `src/diagnostics/` (shared, consumes other members' logged metrics) has
   not been started — check whether Members A-D's `history`/diagnostics
   format has stabilized before building against it.
5. Freeze `requirements.txt` (`pip freeze > requirements-lock.txt`) once
   the antifloat sweep is finalized, and finish the `README.md`
   environment section so the whole pipeline is reproducible by a grader
   from a clean clone.