# Stage 03 — Shared-NR 4-Bus SVD Integration and Regression

## 1. Stage objective

Run Member B's SVD solver through the existing shared Newton-Raphson dispatch
on Member A's unmodified 4-bus builder; compare loaded-secondary and
no-secondary-load cases with the direct solver; and add integration regression
coverage.

## 2. Branch and starting commit

- Branch: `2105117`.
- Starting commit: `350854e` (`2105117(stage02): document SVD solver handoff`).
- The working tree was clean before this stage.

## 3. Pre-existing dirty files relevant to safety

None.  No pre-existing work was discarded, stashed, reset, restored, cleaned,
staged, or committed.

## 4. Files created or modified in this stage

- Created `experiments/exp_b_svd_4bus.py`.
- Created `tests/test_svd_integration_4bus.py`.
- Created this handoff.
- No Member-A core file or existing 4-bus experiment was changed.  In
  particular, the Member-B experiment imports
  `experiments.exp01_4bus.build_4bus_system` unchanged, and uses the existing
  `newton_raphson(..., method="svd")` dispatch.

## 5. Implementation/API decisions

`exp_b_svd_4bus.py` runs the four required combinations using identical
network/Ybus, flat initial state, `tol_F=1e-10`, `max_iter=40`, and shared
Newton loop.  Only `method` changes.  `compute_conditioning=True` is used for
diagnostic visibility, so its timings are not end-to-end runtime comparisons:
the shared loop itself performs an additional diagnostic SVD each iteration.

The experiment prints each SVD solve's rank, raw singular extrema, threshold,
truncation count, step norm, linear residual, and solver runtime.  It counts
actual linear solves separately from the terminal history entry that detects
convergence without solving.  It does not change the solver threshold or add
any artificial grounding/regularization.

The new regression tests verify shared `method="svd"` dispatch, healthy-case
convergence and direct/SVD state agreement, exposure of SVD diagnostics through
NR history, and non-crashing SVD behavior for the floating case.  The floating
test deliberately does **not** assert convergence, even though this observed
run did converge, so it does not hard-code a topology-sensitive narrative.

## 6. Commands and exact pass/fail summary

Starting validation:

```text
python -m pytest -q tests/test_svd_pinv.py
7 passed in 0.26s

python -m pytest -q
8 passed in 0.27s
```

Stage validation:

```text
python experiments/exp_b_svd_4bus.py
completed successfully (exit code 0)

python -m pytest -q tests/test_svd_pinv.py tests/test_svd_integration_4bus.py
10 passed in 0.39s

python -m pytest -q
11 passed in 0.33s
```

No baseline or Stage 03 test failed.

## 7. Actual 4-bus numerical observations

All figures below are outputs from this repository's current team-reconstructed
4-bus case, not exact reproduction claims for Jang et al.'s private case.

| Case | Converged | History / linear solves | Final `||F||_inf` |
| --- | --- | ---: | ---: |
| loaded secondary, direct | yes | 8 / 7 | `9.343221e-15` |
| loaded secondary, SVD | yes | 8 / 7 | `9.308526e-15` |
| no secondary load, direct | yes | 8 / 7 | `1.535530e-14` |
| no secondary load, SVD | yes | 8 / 7 | `5.107847e-14` |

The loaded-case maximum direct-vs-SVD state difference was `2.686740e-13`.
Loaded final voltage magnitudes agreed: BUS1 `(1, 1, 1)`, BUS2
`(0.993158010, 0.993158010, 0.993158010)`, BUS3
`(0.984382278, 0.984382278, 0.984382278)`, and BUS4
`(0.980095267, 0.980095267, 0.980095267)` p.u.

For the no-secondary-load direct run, the final direct-solver condition number
was `7.849661e11`, below its project-defined `1e12` guard; no `LinAlgError`
occurred and no guard failure occurred.  This does not negate the experiment's
severe-ill-conditioning finding (the existing `1e10` reporting criterion was
exceeded); it distinguishes it from a literal/guarded direct failure.

### SVD iteration diagnostics

The SVD default is `tau = eps(float64) * 18 * sigma_max`.  `residual` below is
the solver's `||J dx - rhs||_2`; it is not the nonlinear mismatch.

| Case, k | rank | `sigma_max` | `sigma_min` | `tau` | trunc. | `||dx||_2` | residual | solve s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| loaded, 0 | 18 | 8.756893e1 | 1.423251e0 | 3.499957e-13 | 0 | 3.263265e0 | 1.388294e-13 | 6.935e-4 |
| loaded, 1 | 18 | 1.667223e2 | 2.400590e0 | 6.663561e-13 | 0 | 1.659220e0 | 1.429078e-13 | 1.752e-4 |
| loaded, 2 | 18 | 1.107042e2 | 4.432948e-1 | 4.424630e-13 | 0 | 6.871962e-1 | 2.834791e-14 | 1.472e-4 |
| loaded, 3 | 18 | 8.769029e1 | 2.028448e-2 | 3.504808e-13 | 0 | 1.710166e-1 | 4.974365e-15 | 1.524e-4 |
| loaded, 4 | 18 | 8.218868e1 | 3.212578e-3 | 3.284920e-13 | 0 | 1.191742e-2 | 3.560676e-16 | 1.580e-4 |
| loaded, 5 | 18 | 8.184102e1 | 3.863174e-3 | 3.271024e-13 | 0 | 5.811215e-5 | 1.627408e-18 | 1.513e-4 |
| loaded, 6 | 18 | 8.183934e1 | 3.867006e-3 | 3.270957e-13 | 0 | 1.377674e-9 | 3.563607e-23 | 1.799e-4 |
| no load, 0 | 18 | 8.756893e1 | 1.423251e0 | 3.499957e-13 | 0 | 3.191729e0 | 1.360954e-13 | 1.630e-4 |
| no load, 1 | 18 | 1.648778e2 | 2.312486e0 | 6.589839e-13 | 0 | 1.618851e0 | 9.807032e-14 | 1.548e-4 |
| no load, 2 | 18 | 1.103978e2 | 4.274617e-1 | 4.412384e-13 | 0 | 6.578050e-1 | 3.133471e-14 | 1.580e-4 |
| no load, 3 | 18 | 8.836738e1 | 2.190769e-2 | 3.531870e-13 | 0 | 1.546809e-1 | 3.227183e-15 | 1.621e-4 |
| no load, 4 | 18 | 8.325921e1 | 7.777707e-5 | 3.327706e-13 | 0 | 9.494025e-3 | 1.430053e-16 | 1.693e-4 |
| no load, 5 | 18 | 8.295611e1 | 1.102104e-9 | 3.315592e-13 | 0 | 3.606281e-5 | 1.611169e-18 | 1.627e-4 |
| no load, 6 | 18 | 8.295507e1 | 1.117803e-10 | 3.315550e-13 | 0 | 5.796379e-5 | 9.473035e-19 | 1.595e-4 |

Thus, despite the floating case's small final singular value and raw condition
number of roughly `7.42e11` for the SVD final linear solve, the Stage 02
default tolerance did **not** truncate the near-null mode: all 18 singular
values remained retained.  Its small linear residual only says the update
satisfies this finite-precision linear system; it does not establish that the
floating phase-to-ground direction is physically identifiable.

No-load SVD final voltage magnitudes were BUS1 `(1, 1, 1)`, BUS2
`(0.998897940, 0.998897940, 0.998897940)`, BUS3
`(0.998874965, 0.998912714, 0.998906140)`, and BUS4
`(0.998874965, 0.998912714, 0.998906140)` p.u.

## 8. Assumptions

- The imported 4-bus topology and non-transformer loads are existing team
  reconstruction assumptions.  The comparison preserved them exactly.
- Default SVD thresholding is the Stage 02 project implementation choice, not
  a threshold specified by the base paper.
- Per-solve timing is an observed local measurement, not a benchmark; timings
  vary across runs and shared conditioning diagnostics add separate cost.

## 9. Limitations/blockers

- No blocker occurred.
- This configuration converged under both methods, so it does not yet
  demonstrate pseudoinverse truncation or superiority over direct solve at the
  default threshold.  A later sensitivity experiment may study defensible
  threshold choices without changing the underlying model.
- No conclusion about zero-sequence/common-mode voltage ambiguity can be drawn
  from these scalar magnitude comparisons alone.

## 10. Commits created in this stage

- `5b52241` — `2105117(stage03): add 4-bus SVD integration experiment`
- `33b3112` — `2105117(stage03): add SVD NR integration regression tests`
- Pending at handoff-writing time: this handoff-only commit,
  `2105117(stage03): document 4-bus SVD findings`.

## 11. Instructions for the next stage

1. Read the global contract, this handoff, and the next stage prompt before
   acting; remain on `2105117` and preserve unrelated work.
2. Reuse `exp_b_svd_4bus.py` and its imported builder for any SVD threshold
   investigation; do not rewrite `exp01_4bus.py` or the shared NR/model code.
3. Keep direct and SVD runs identical except for the linear-solver options.
   Log both raw conditioning and thresholded rank/truncation behavior.
4. Treat the observed no-load convergence as a finite-precision result of this
   reconstruction, not an exact reproduction or physical uniqueness claim.
5. Run focused and full tests, record actual outputs, and commit only
   Member-B-owned files and the next handoff.
