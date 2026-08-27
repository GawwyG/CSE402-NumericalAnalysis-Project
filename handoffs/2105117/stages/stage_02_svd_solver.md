# Stage 02 — Explicit SVD Moore-Penrose Solver and Unit Tests

## 1. Stage objective

Implement Member B's transparent SVD Moore-Penrose pseudo-inverse linear
solver and controlled numerical tests, without changing the shared nonlinear
model or Newton loop.

## 2. Branch and starting commit

- Branch: `2105117`.
- Starting commit: `1a09576` (`2105117(stage01): document baseline and
  implementation contract`).
- The working tree was clean before Stage 02.

## 3. Pre-existing dirty files relevant to safety

None.  `git status --short`, `git diff --name-only`, and `git diff --stat`
were clean before implementation.  No pre-existing work was discarded,
stashed, reset, restored, cleaned, staged, or committed.

## 4. Files created or modified in this stage

- Created `src/solvers/svd_pinv.py`.
- Created `tests/test_svd_pinv.py`.
- Created this handoff.
- No Member-A/shared core, Member-C, Member-D, Member-E, dependency, feeder,
  or existing experiment/test file was modified.

## 5. Implementation and API decisions

`solve_svd_pinv(J, rhs, *, rtol=None, atol=0.0)` implements the existing
shared dispatch contract:

```python
dx, diagnostics = solve_linear_step(J, rhs, method="svd", options=options)
```

No change to `src/powerflow/newton.py` was needed because its SVD dispatch was
already present.  The solver explicitly computes the economy decomposition
`J = U @ diag(s) @ Vh` with `np.linalg.svd(..., full_matrices=False)` and
forms the update using filtered reciprocal singular values:

```python
dx = Vh.conj().T @ (s_plus * (U.conj().T @ rhs))
```

For real Jacobians this is the usual `V @ diag(s_plus) @ U.T @ rhs` formula;
the conjugate transpose also makes the helper valid for complex arrays.
Production code does not call `np.linalg.pinv()`.

Rank semantics are explicit:

```text
tau = max(atol, rtol_used * sigma_max)
rtol_used = eps(float64) * max(J.shape) when rtol is None
retain sigma_i iff sigma_i > tau
```

Values equal to `tau` are truncated.  The solver supports nonempty rectangular
matrices as well as the square NR case.  Rank deficiency returns a successful
minimum-norm least-squares update; a nonzero residual is recorded but is not
called a failure.  Dimension/tolerance contract errors raise `ValueError`;
non-finite array data, SVD non-convergence, or a non-finite result return
`(None, diagnostics)`.

Diagnostics have stable keys: `method`, `success`, `error_message`,
`runtime_sec`, `residual_norm`, `step_norm`, `sigma_max`, `sigma_min`,
serializable `singular_values`, `rank_tolerance`, `rtol`, `atol`,
`numerical_rank`, `truncated_singular_values`, raw `condition_number`, and
`effective_condition_number`.  Raw conditioning uses the reported smallest
singular value; effective conditioning uses the smallest retained value and is
therefore distinct from rank thresholding.

## 6. Tests and exact outcomes

Baseline before coding:

```text
python -m pytest -q
1 passed in 0.19s
```

Stage 02 validation after implementing tests:

```text
python -m pytest -q tests/test_svd_pinv.py
7 passed in 0.30s

python -m pytest -q
8 passed in 0.28s
```

The focused suite covers a full-rank square solution versus `np.linalg.solve`,
an inconsistent exact-rank-deficient least-squares solution versus
`np.linalg.pinv`, known-spectrum `rtol` rank changes, underdetermined
minimum-norm behavior versus `np.linalg.pinv`, diagnostic consistency,
non-finite inputs, and invalid dimensions.  No test was weakened and no
baseline test failed.

## 7. Key observed numerical outputs

- Full-rank smoke check on `[[3, 1], [1, 2]]` with RHS `[7, 5]` returned
  `dx = [1.8, 1.6]`, numerical rank 2, tolerance
  `1.6067298552746114e-15`, and residual norm `0.0`.
- The known spectrum `[1, 1e-6, 1e-12]` produced rank 2 at `rtol=1e-9` and
  rank 1 at `rtol=1e-5`, exactly following the strict retained-value rule.

These are controlled synthetic-matrix checks, not feeder or paper results.

## 8. Assumptions

- The project uses NumPy's double-precision epsilon for the default relative
  threshold even when inputs have a lower-precision dtype; inputs are promoted
  to at least float64/complex128 for consistent SVD arithmetic.
- The current shared Newton loop requests an SVD separately for optional
  conditioning diagnostics.  Solver runtime recorded by this implementation
  does not include that optional loop-level diagnostic SVD.

## 9. Limitations and blockers

- No blockers occurred.
- Stage 02 intentionally does not run a 4-bus SVD Newton experiment or modify
  convergence behavior; that is later-stage integration work.
- The serializable full singular-value list is suitable for current small
  matrices; later large-feeder experiment reporting should choose storage and
  summary policy deliberately rather than silently omitting diagnostics.

## 10. Commits created in this stage

- `d70d1a9` — `2105117(stage02): implement explicit SVD pseudoinverse solver`
- `e07c6f1` — `2105117(stage02): validate SVD solver on controlled matrices`
- Pending at handoff-writing time: this handoff-only commit,
  `2105117(stage02): document SVD solver handoff`.

## 11. Instructions for the next stage

1. Read the global Member-B contract and this handoff, re-check branch/status,
   and preserve any subsequently appearing unrelated work.
2. Use `method="svd"` through the already-existing shared Newton dispatch;
   do not create another NR loop and do not alter `newton.py` unless the shared
   exception is genuinely satisfied.
3. For any 4-bus integration work, keep the exact existing state, mismatch,
   Jacobian, initial state, tolerance, topology, and feeder reconstruction
   identical across solvers; vary only the linear solver.
4. Record the solver's `rank_tolerance`, rank, truncation count, raw/effective
   conditioning, residual, and runtime distinctly.  Do not interpret a
   nonzero MP-PI residual or rank deficiency alone as solver failure.
5. Run focused and full tests before committing the next stage handoff.
