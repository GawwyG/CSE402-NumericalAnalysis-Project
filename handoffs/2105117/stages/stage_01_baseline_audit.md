# Stage 01 — Baseline Audit, Branch Setup, and Scope Lock

## 1. Stage objective

Establish a safe Member-B baseline, verify the existing numerical model,
capture its current behavior, and lock the SVD solver integration contract.
No functional source code was changed in this stage.

## 2. Branch and starting commit

- Required Member-B branch: `2105117` (created from the current `main`).
- Starting commit: `877df6d` (`preliminary commit`).
- Recent history inspected: `877df6d` and `aaa3fee`.
- Remote branches observed: `origin/main` only; the local `2105117` branch did
  not exist before this stage.

## 3. Pre-existing working-tree state

`git status --short`, `git diff --name-only`, and `git diff --stat` were clean
before creating the branch.  There were no pre-existing dirty files to preserve
or record.  No reset, restore, clean, stash, or unrelated staging was used.

## 4. Files created or modified in this stage

- Created: `handoffs/2105117/stages/stage_01_baseline_audit.md`.
- No source, test, experiment, configuration, or dependency file was modified.

## 5. Actual implementation and SVD integration contract

The current code, rather than planning documents, establishes this interface:

```python
dx, diagnostics = solve_linear_step(J, rhs, method="svd", options=options)
```

`src/powerflow/newton.py` already dispatches `method="svd"` to
`src.solvers.svd_pinv.solve_svd_pinv(J, rhs, **options)`.  Therefore Stage 02
can add only the Member-B-owned module; it does not need to modify the shared
Newton loop.  The solver must return `(dx, diagnostics)`, where `dx` is a
finite update when `diagnostics["success"]` is true, and `None` on a true
solver failure.  Newton records `solver_diagnostics`, checks
`diagnostics.get("success", False)`, and cross-checks `||J @ dx + F||_2`.

The existing direct-solver diagnostic convention includes `method`, `success`,
`runtime_sec`, `residual_norm`, `error_message`, and direct-specific
conditioning/failure keys.  The SVD implementation should preserve the common
keys and add its documented SVD threshold, singular values, numerical rank,
and truncated-singular-value count.  It must explicitly form the SVD and
filtered reciprocal singular values; it must not call `np.linalg.pinv()`.

## 6. Scope map

Member B may safely own:

- `src/solvers/svd_pinv.py` (currently absent);
- `tests/test_svd_pinv.py`, `tests/test_linear_solvers.py`,
  `tests/test_svd_integration_4bus.py`, and other new `tests/test_svd_*.py`;
- new clearly owned `experiments/exp_b_*.py` scripts (and only the permitted
  small Member-B utility when justified);
- `handoffs/2105117/**`.

Do not independently change Member-A model/state, Ybus, mismatch, Jacobian,
Newton, direct solver, or its experiment/test logic; do not change the
RRQR/Tikhonov solver owners' files, feeder provenance/OpenDSS pipeline, or
`requirements.txt`.  The shared-file exception is not needed: the existing
SVD dispatch is a clean extension point.

No `src/solvers/svd_pinv.py`, `tests/test_svd_*.py`, or
`experiments/exp_b_*.py` existed at the audit baseline.

## 7. Validation commands and exact outcomes

Commands run from the repository root:

```text
python -m pytest -q
1 passed in 1.87s

python tests/test_jacobian.py
PASS; E_J = 5.468589e-11 (tolerance 1.0e-06)

python experiments/exp01_4bus.py
completed successfully (exit code 0)
```

The pytest suite currently contains one discovered test, the analytical
Jacobian finite-difference validation.  No baseline command failed.

## 8. Observed numerical baseline

- Jacobian test: state size 6; relative Frobenius error `5.468589e-11`;
  largest entrywise difference `9.240e-10` at `J[5,4]`.
- 4-bus loaded-secondary healthy case: converged in 8 iterations; flat-start
  `kappa_2(J)=6.152739e+01`; maximum recorded `kappa_2(J)=2.558341e+04`.
- 4-bus no-secondary-load case: also converged in 8 iterations, but the
  experiment's severe-ill-conditioning criterion was observed; flat-start
  `kappa_2(J)=6.152739e+01`, maximum recorded
  `kappa_2(J)=7.849661e+11` (> `1e10`).
- In this specific run the direct solver raised no `LinAlgError` and its
  project-defined `1e12` condition-number guard did not fire.  Thus there was
  no direct-solver failure event to classify.  The implementation distinguishes
  a literal `np.linalg.solve()` exception (`exact_singular`) from a successful
  solve rejected by the guard (`ill_conditioned`); they must not be conflated.

## 9. Assumptions and limitations

- The current 4-bus topology/load values are the existing team reconstruction;
  only the transformer data cited in the experiment are paper-specified.
- The observed no-load result is a baseline observation, not a claim that the
  paper's exact private case has been reproduced.
- `compute_conditioning=True` in the shared Newton loop performs a diagnostic
  SVD each iteration; disable it for solver-runtime comparisons when required.
- Stage 01 did not introduce an SVD implementation or rank-threshold choice.

## 10. Commits created in this stage

Pending at the time this handoff was written: one commit containing only this
handoff, planned message:

```text
2105117(stage01): document baseline and implementation contract
```

## 11. Instructions for Stage 02

1. Remain on `2105117`; first re-check `git status --short` and reread the
   global contract and this handoff.
2. Implement only `src/solvers/svd_pinv.py` using explicit SVD,
   `J = U Sigma V^H`, and a documented filtered reciprocal threshold.
3. Return the established `(dx, diagnostics)` contract, recording the exact
   threshold, rank, singular values or an appropriately documented summary,
   truncated count, residual norm, runtime, success, and failure behavior.
4. Add focused Member-B tests before any integration experiment.  Cover full
   rank agreement with a direct/reference solution, rank-deficient least
   squares/minimum-norm behavior, and threshold behavior.
5. Do not modify `src/powerflow/newton.py`: its SVD dispatch is already
   present.  Record all tests and numerical outputs in the next handoff and
   commit explicitly scoped paths only.
