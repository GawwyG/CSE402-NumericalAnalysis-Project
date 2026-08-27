# Stage 05 — Common Solver Tests and Member-B Experiment Utility

## 1. Stage objective

Improve cross-solver reliability using controlled synthetic matrices and remove
only proven duplicated Member-B experiment reporting logic.  No RRQR or
Tikhonov solver implementation, placeholder, or test was created.

## 2. Branch and starting commit

- Branch: `2105117`.
- Starting commit: `311377e` (`2105117(stage04): document threshold sensitivity`).
- The working tree was clean before this stage.

## 3. Pre-existing dirty files relevant to safety

None.  No pre-existing change was discarded, stashed, reset, restored,
cleaned, staged, or committed.

## 4. Files created or modified in this stage

- Created `tests/test_linear_solvers.py`.
- Created `experiments/member_b_utils.py`.
- Modified only Member-B-owned scripts `experiments/exp_b_svd_4bus.py` and
  `experiments/exp_b_svd_tolerance_4bus.py` to import the helper.
- Created this handoff.
- No solver implementation, Member-A core/experiment, Member-C RRQR,
  Member-D Tikhonov, feeder, environment, or dependency file was changed.

## 5. Implementation decisions

### Common test matrices

`tests/test_linear_solvers.py` uses only public `solve_direct` and
`solve_svd_pinv` interfaces.  It deliberately leaves a clear extension point
for future solver owners without importing unavailable modules.

The deterministic cases are:

- a well-conditioned tridiagonal full-rank 3-by-3 matrix, where direct and SVD
  must agree;
- full-rank `diag(1, 1e-5, 1e-10)`, condition about `1e10`, below the direct
  `1e12` guard, where both methods should provide finite matching updates;
- full-rank `diag(1, 1e-13)`, condition `1e13`, where `np.linalg.solve`
  itself returns a finite solution but the project direct guard deliberately
  returns `None` with `failure_mode="ill_conditioned"`;
- exact-rank-deficient `diag(1, 1e-2, 1e-6, 1e-12, 0)`, where direct reports
  `exact_singular` and SVD is intentionally successful with rank 4;
- the same controlled spectrum wrapped by deterministic orthogonal factors,
  confirming rank/spectrum diagnostics outside a diagonal special case.

The tests document why direct guard failure is not a claim that NumPy's direct
routine threw a literal singularity exception.  They do not weaken the guard.

### Minimal experiment helper

Stage 03 and Stage 04 each independently scanned shared NR history for
`solver_diagnostics`, counted linear updates, and extracted terminal mismatch.
`experiments/member_b_utils.py` now provides only `summarise_nr_history` for
those exact repeated reporting metrics.  It is stdlib-only, does not alter its
input, contains no model or solver behavior, and is used by both existing
Member-B experiment scripts.  CSV/plot functionality remains local to the
threshold sweep because it was not duplicated.

## 6. Validation commands and exact outcomes

Starting validation:

```text
python -m pytest -q tests/test_svd_pinv.py tests/test_svd_integration_4bus.py
11 passed in 0.28s

python -m pytest -q
12 passed in 0.30s
```

After Stage 05 additions:

```text
python experiments/exp_b_svd_4bus.py
completed successfully (exit code 0); same convergence summary as Stage 03

python -m pytest -q tests/test_svd_pinv.py tests/test_linear_solvers.py
13 passed in 0.30s

python -m pytest -q
17 passed in 0.35s
```

No baseline or Stage 05 test failed.

## 7. Key observed outputs

- The direct guard controlled case (`diag(1, 1e-13)`) reported condition
  number `1.0e13`, `failure_mode="ill_conditioned"`, returned `dx=None`, and
  had a finite computed residual of `0.0`.  This verifies the project guard
  semantics; it is not a literal `np.linalg.solve` exception.
- On the exact rank-deficient spectrum, SVD reported numerical rank 4,
  one truncated singular value, default threshold
  `1.1102230246251565e-15`, residual `0.5` for the intentionally inconsistent
  right-hand side, and finite step norm `3.872983346207417`.  The nonzero
  least-squares residual is intentional and not treated as failure.
- After helper extraction, the rerun 4-bus experiment still had healthy and
  floating direct/SVD runs converge in 8 history entries with 7 actual linear
  solves.  The helper changed reporting duplication only, not numerical logic.

## 8. Assumptions

- The synthetic matrices are deterministic numerical test fixtures, not feeder
  data or paper results.
- The direct condition threshold remains Member A's existing project-defined
  `1e12` constant; this stage only tests its public behavior.
- The small helper is intentionally limited to reporting logic used by two
  existing Member-B scripts.  It is not a new experiment framework.

## 9. Limitations/blockers

- No blocker occurred.
- RRQR and Tikhonov files were not present; this stage intentionally neither
  creates them nor makes failing tests for them.  Their owners can later extend
  `test_linear_solvers.py` with their public interfaces.
- The controlled matrices validate linear-solver behavior, not power-flow
  modeling or feeder accuracy.
- No runtime comparison was performed in Stage 05.

## 10. Commits created in this stage

- `3bee40d` — `2105117(stage05): factor repeated Member B experiment summaries`
- `4d8a87e` — `2105117(stage05): add controlled linear solver test matrices`
- Pending at handoff-writing time: this handoff-only commit,
  `2105117(stage05): document shared test handoff`.

## 11. Instructions for the next stage

1. Read the global contract and this handoff first; remain on `2105117` and
   preserve unrelated working-tree changes.
2. Use `tests/test_linear_solvers.py` only through public solver interfaces.
   If RRQR/Tikhonov become available, their owners should add their own focused
   cases rather than alter Member B's solver behavior.
3. Reuse `summarise_nr_history` in future Member-B experiment scripts when the
   same NR reporting metrics are needed; keep model-specific logic local.
4. Do not infer feeder behavior from the synthetic matrix outcomes.  Continue
   to distinguish direct guard refusal, literal linear-algebra exceptions, and
   successful pseudoinverse least-squares results.
5. Run focused and full tests before the next stage handoff, and commit only
   Member-B-owned files.
