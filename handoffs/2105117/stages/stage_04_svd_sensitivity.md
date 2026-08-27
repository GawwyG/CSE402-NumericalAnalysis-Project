# Stage 04 — SVD Rank-Threshold Sensitivity and Spectral Diagnostics

## 1. Stage objective

Perform a reproducible SVD relative-rank-threshold sweep on the current 4-bus
team reconstruction, tie thresholding to retained rank and Newton behavior,
and preserve spectral diagnostics without changing the nonlinear model.

## 2. Branch and starting commit

- Branch: `2105117`.
- Starting commit: `f9f71f4` (`2105117(stage03): document 4-bus SVD findings`).
- The working tree was clean before Stage 04.

## 3. Pre-existing dirty files relevant to safety

None.  No pre-existing change was discarded, stashed, reset, restored,
cleaned, staged, or committed.

## 4. Files created or modified in this stage

- Created `experiments/exp_b_svd_tolerance_4bus.py`.
- Modified `tests/test_svd_pinv.py` to add a fixed-matrix retained-rank
  monotonicity regression.
- Created this handoff.
- Generated locally (intentionally ignored by existing policy):
  `results/svd_tolerance_4bus_summary.csv`,
  `results/svd_tolerance_4bus_trace.csv`, and three `figures/*.png` diagnostic
  plots.
- No shared Newton/model/Jacobian/Ybus/direct-solver or Member-A experiment
  file was changed.

## 5. Experiment and diagnostic design

`exp_b_svd_tolerance_4bus.py` imports Member A's
`build_4bus_system` unchanged and runs both loaded-secondary (`healthy`) and
no-secondary-load (`floating`) cases with the same flat start, `tol_F=1e-10`,
and `max_iter=40`.  It varies only SVD `rtol` over:

```text
default = eps(float64) * 18 = 3.9968028886505635e-15,
1e-16, 1e-14, 1e-12, 1e-10, 1e-8, 1e-6.
```

At every successful linear update it records the actual
`tau = rtol * sigma_max`, rank, truncation count, singular extrema, step norm,
linear residual, solver runtime, and full serialised spectrum.  Summary CSV
rows additionally record convergence, history/update counts, final nonlinear
mismatch, voltage-magnitude range, and total SVD-solver time.

`compute_conditioning=False` is deliberate.  The shared Newton loop otherwise
performs a second diagnostic SVD per iteration.  All reported timing below is
the SVD solver's own `runtime_sec`; no end-to-end runtime comparison is made.

Matplotlib 3.9.1 was already available; the script generated a final-default
floating spectrum plot (including `tau`), final retained-rank-vs-rtol plot,
and final nonlinear-mismatch-vs-rtol plot.  No dependency files were changed.

## 6. Validation commands and exact outcomes

Starting baseline:

```text
python -m pytest -q tests/test_svd_pinv.py tests/test_svd_integration_4bus.py
10 passed in 0.31s

python -m pytest -q
11 passed in 0.31s
```

After Stage 04 work:

```text
python experiments/exp_b_svd_tolerance_4bus.py
completed successfully (exit code 0); wrote ignored local CSV and PNG outputs

python -m pytest -q tests/test_svd_pinv.py tests/test_svd_integration_4bus.py
11 passed in 0.38s

python -m pytest -q
12 passed in 0.34s
```

No baseline or Stage 04 test failed.  The new fixed-spectrum test verifies
retained ranks `[3, 2, 1]` for increasing cutoffs `[1e-12, 1e-7, 1e-3]`.

## 7. Actual results

All values are observations from the current **team-reconstructed** 4-bus
case, not paper results and not an exact reproduction claim.  No independent
reference voltage solution exists for this reconstruction, so no voltage error
was fabricated.

### Final threshold-summary observations

Every run converged in 8 history entries with 7 successful SVD updates.  The
healthy case was insensitive over this grid: all seven settings ended at rank
18, zero truncated values, final `||F||_inf=9.308526e-15`, final
`sigma_min=3.867006e-3`, final `||dx||_2=1.377674e-9`, final linear residual
`3.563607e-23`, and voltage magnitude range `[0.980095267, 1.0]` p.u.  Its
final thresholds ranged from `8.183934e-15` (`rtol=1e-16`) to
`8.183934e-05` (`rtol=1e-6`), still far below its final smallest singular
value.

Floating-case final values were:

| rtol | final tau | rank / truncated | final sigma_min | final step | final linear residual | final `||F||_inf` | Vmag range |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| default (`3.9968e-15`) | 3.315550e-13 | 18 / 0 | 1.117803e-10 | 5.796379e-5 | 9.473035e-19 | 5.107847e-14 | [0.998874965, 1.0] |
| 1e-16 | 8.295507e-15 | 18 / 0 | 1.117803e-10 | 5.796379e-5 | 9.473035e-19 | 5.107847e-14 | [0.998874965, 1.0] |
| 1e-14 | 8.295507e-13 | 18 / 0 | 1.117803e-10 | 5.796379e-5 | 9.473035e-19 | 5.107847e-14 | [0.998874965, 1.0] |
| 1e-12 | 8.295507e-11 | 18 / 0 | 1.117803e-10 | 5.796379e-5 | 9.473035e-19 | 5.107847e-14 | [0.998874965, 1.0] |
| 1e-10 | 8.295507e-09 | 16 / 2 | 2.524472e-15 | 5.120496e-10 | 5.657709e-15 | 7.230327e-15 | [0.998897940, 1.0] |
| 1e-8 | 8.295507e-07 | 16 / 2 | 2.524472e-15 | 5.120496e-10 | 5.657709e-15 | 7.230327e-15 | [0.998897940, 1.0] |
| 1e-6 | 8.295507e-05 | 16 / 2 | 1.361827e-15 | 5.120498e-10 | 3.621977e-15 | 1.407302e-14 | [0.998897940, 1.0] |

The raw `sigma_min` remains reported even after a mode is truncated.  Thus the
last three rows have rank 16 because two smallest modes are below `tau`, not
because the raw SVD literally has only 16 singular values.

### Threshold → rank → Newton-step connection

At `rtol=1e-10`, the floating run remained rank 18 through iterations 0–4.
At iteration 5, `sigma_max=8.295611e1`, `sigma_min=1.102104e-9`, and
`tau=8.295611e-9`; two modes became sub-threshold and rank fell to 16.  The
rank stayed 16 at iteration 6, when raw `sigma_min=2.524472e-15` and
`tau=8.295507e-9`.  The final step was `5.120496e-10`, compared with
`5.796379e-5` when default thresholding retained all modes.  The corresponding
final nonlinear mismatch was `7.230327e-15` rather than `5.107847e-14`.

At `rtol=1e-6`, rank fell to 16 one iteration earlier (iteration 4) because
the threshold was larger.  Nonetheless, it converged with a similar final
rank/step, while its final mismatch was `1.407302e-14`.  This demonstrates
sensitivity of effective rank and late Newton steps to the cutoff in this
case; it does **not** identify a universally optimal threshold or prove an
accuracy improvement from convergence/mismatch alone.

Individual observed solver calls were roughly `1.3e-4` to `1.1e-3` seconds
and total solver-only time per 7-update run roughly `1.0e-3` to `3.1e-3`
seconds.  These are local variability observations, not a performance result.

## 8. Assumptions

- The imported topology/load values are existing team reconstruction
  assumptions; all SVD runs retain them unchanged.
- The threshold grid and default `eps * max(J.shape)` policy are project
  numerical-analysis choices, not a paper-specified prescription.
- The plots/CSV are reproducible local artifacts and intentionally remain
  untracked under the repository's existing ignore policy.

## 9. Limitations/blockers

- No blocker occurred.
- The observed rank transition is limited to this current 18-state 4-bus
  reconstruction and late NR iterations.  It must not be generalized to IEEE
  13/37 or other feeder models.
- No independent reference solution was available, so convergence and a small
  nonlinear mismatch do not establish physical correctness, voltage accuracy,
  or uniqueness of the floating phase-to-ground component.
- Solver residual may be nonzero after truncation without representing solver
  failure; it is a linear least-squares diagnostic, distinct from nonlinear
  mismatch.
- No end-to-end runtime claim is made because the experiment intentionally
  disables shared loop conditioning and reports only solver-local timing.

## 10. Commits created in this stage

- `fa5da29` — `2105117(stage04): add SVD rank-threshold sweep`
- `81d7b68` — `2105117(stage04): test SVD rank monotonicity`
- Pending at handoff-writing time: this handoff-only commit,
  `2105117(stage04): document threshold sensitivity`.

## 11. Instructions for the next stage

1. Read the global contract and this handoff before acting; remain on
   `2105117` and preserve unrelated work.
2. Re-run `experiments/exp_b_svd_tolerance_4bus.py` when needing its ignored
   CSV/plots; do not commit generated results unless team policy changes.
3. Keep future solver comparisons on the same model, initial state, tolerance,
   and case.  Change only solver/options and record raw versus effective rank
   separately.
4. Present the Stage 04 cutoff transition as a reconstruction-specific
   sensitivity observation, not an accuracy proof or threshold recommendation
   for IEEE 13/37.
5. Use solver-local `runtime_sec` for SVD timing and state explicitly whenever
   shared `compute_conditioning=True` adds diagnostic SVD cost.
