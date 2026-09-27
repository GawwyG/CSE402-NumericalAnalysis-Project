# SVD & the Moore-Penrose Pseudo-Inverse — from scratch

*(This is the method the base paper — Jang, Kim & Kim, IEEE Access 2023 —
proposes as its fix. This project reproduces it here and then asks whether
it's actually the best choice.)*

Implementation: [`src/solvers/svd_pinv.py`](../src/solvers/svd_pinv.py)

---

## 1. The idea: re-express any matrix as "stretch along independent directions"

Every real matrix `J` (square, rectangular, singular, whatever) can be
written as a product of three matrices:

```
J = U · Σ · Vᵀ
```

- `V` is an orthogonal matrix — its columns `v_1, v_2, ..., v_n` are
  mutually perpendicular unit vectors ("directions" in the *input* space).
- `Σ` is diagonal — entries `σ_1 ≥ σ_2 ≥ ... ≥ σ_n ≥ 0` (the **singular
  values**, always non-negative, always sorted largest-first).
- `U` is orthogonal too — its columns `u_1, u_2, ..., u_n` are perpendicular
  unit vectors in the *output* space.

**Geometric picture**: multiplying any vector by `J` is *always* equivalent
to three steps: (1) rotate/reflect via `Vᵀ`, (2) stretch each axis
independently by `σ_i` via `Σ`, (3) rotate/reflect again via `U`. This
decomposition **always exists**, for *any* matrix — square or not,
singular or not. That's what makes SVD the right tool for exactly this
project's problem: unlike LU, it never "fails" just because the matrix is
singular; it just reports some `σ_i = 0`.

Each singular value `σ_i` tells you exactly how much the matrix "listens
to" the corresponding input direction `v_i`: if `σ_i` is large, that
direction is strongly, reliably determined by the equations. If `σ_i` is
tiny or exactly zero, that direction is the "floating" one this whole
project is about — nudging along `v_i` produces almost no change in the
output at all (recall the null-space / graph-Laplacian discussion: `C_DELTA`'s
`(1,1,1)` null vector shows up here as a `σ_i` at or near zero).

## 2. Why you can't just "invert" `Σ` naively

If `J` were invertible, `J⁻¹ = V · Σ⁻¹ · Uᵀ`, where `Σ⁻¹` just has `1/σ_i`
on the diagonal. But if any `σ_i = 0`, `1/σ_i` is undefined — this is
*literally* singularity, expressed through the SVD lens.

## 3. The fix: the Moore-Penrose pseudo-inverse

Instead of inverting every singular value, **only invert the ones that are
big enough to trust, and set the reciprocal of everything else to exactly
zero**:

```
σ_i⁺ = 1/σ_i   if σ_i > τ  (trustworthy — invert it)
σ_i⁺ = 0        if σ_i ≤ τ  (too close to zero — throw this direction away)
```

where `τ` is a chosen cutoff ("how small counts as basically zero"). Then:

```
Δx = V · Σ⁺ · Uᵀ · rhs
```

This `Δx` has two provable properties that make it the standard, principled
answer to "what do I do when the equations don't fully determine the
answer":
- Among all vectors that best satisfy `J·Δx ≈ rhs` (in the least-squares
  sense — smallest possible `‖J·Δx − rhs‖`), it picks the one with the
  **smallest possible `‖Δx‖`** ("minimum-norm"). In the discarded
  directions, it doesn't "guess" — it deliberately contributes exactly
  zero.
- If `J` is actually invertible (no small singular values at all), this
  formula reduces to the ordinary inverse — it's a strict generalization,
  not a different method that happens to agree sometimes.

## 4. A worked tiny example

Take a deliberately singular 2×2 matrix (analogous in spirit to
`C_DELTA`'s rank-2-ness, just scaled down to 2×2 for hand computation):
```
J = [[1, 1],
     [1, 1]]
```
This matrix's SVD is `σ_1 = 2`, `σ_2 = 0` — one well-determined direction
(the "sum," `(1,1)/√2`) and one completely undetermined direction (the
"difference," `(1,−1)/√2`), exactly the common-mode / differential-mode
split you'd expect. Given `rhs = [4, 4]`:
- `σ_1⁺ = 1/2`, `σ_2⁺ = 0`.
- The pseudo-inverse solution comes out to `Δx = [2, 2]` — it fully
  explains the "sum" direction (`4 = 2+2`✓) and contributes *nothing* extra
  along the undetermined "difference" direction, even though `[3,1]`,
  `[5,-1]`, etc. would *also* satisfy `J·Δx = rhs` exactly. `[2,2]` is
  singled out as the answer specifically because it's the smallest such
  vector.

## 5. What `solve_svd_pinv()` actually does ([svd_pinv.py:39-192](../src/solvers/svd_pinv.py#L39-L192))

```python
U, singular_values, Vh = np.linalg.svd(J_work, full_matrices=False)
```
Computes the decomposition directly — deliberately **not** calling
`numpy.linalg.pinv()`, so every decision below is visible and logged,
rather than hidden inside a library call.

```python
rank_tolerance = max(atol_used, rtol_used * sigma_max)
retained = singular_values > rank_tolerance
```
The cutoff `τ` is `max(atol, rtol · σ_max)` — a combination of an absolute
floor and a floor relative to the *strongest* direction (so the cutoff
scales sensibly regardless of the matrix's overall units/magnitude).
Default `rtol = eps · max(shape)` (machine epsilon times matrix size — the
standard textbook rule, same one used in `newton.py`'s own
`_numerical_rank()` diagnostic). Note strict `>`: a singular value sitting
*exactly* at the threshold is deliberately truncated, not kept.

```python
reciprocal_singular_values[retained] = 1.0 / singular_values[retained]
dx = Vh.conj().T @ (reciprocal_singular_values * (U.conj().T @ rhs_work))
```
This is the pseudo-inverse formula from §3, written out explicitly
(`.conj().T` handles the complex case; for the real Jacobians this project
actually uses, that's just an ordinary transpose).

```python
raw_condition_number = ... sigma_max / sigma_min                      # uses the SMALLEST reported σ
effective_condition_number = ... sigma_max / smallest RETAINED σ      # uses the smallest KEPT σ
```
Two different condition numbers are reported, and the module is careful
never to conflate them: the **raw** one reflects how singular `J` truly is;
the **effective** one reflects how well-conditioned the *retained* subspace
is (which is what actually matters for the reliability of `Δx`, since the
discarded directions were zeroed out deliberately, not because they were
merely "risky").

A rank-deficient result (`numerical_rank < n`) is **not** treated as a
failure by this function — that's expected and normal whenever the
Jacobian genuinely has a floating direction; the function's job is just to
handle it in a principled way, not to flag it as an error.

## 6. Strengths and weaknesses (as found by this project)

- **Strength**: always produces *a* well-defined answer, even for an
  exactly singular `J` — no crash, no arbitrary garbage, a specific,
  reproducible, minimum-norm choice.
- **Weakness, discovered empirically in this project**: the pseudo-inverse
  step is the *exact* solution to the *linearized* problem at each Newton
  iteration — but on IEEE-13's more severely (2-D) near-null Jacobian at
  realistic load, this exact-but-undamped step **overshoots and oscillates**
  rather than converging (see [experiments/exp_d_ieee13_investigation.py](../experiments/exp_d_ieee13_investigation.py)'s
  module docstring and `solver_robustness_study()`). On IEEE-37, by
  contrast, SVD converges cleanly — so the pseudo-inverse's reliability
  here depends on the specific *shape* of the singularity, not merely
  "singular vs. not," which is exactly this project's central finding
  against the base paper's universal recommendation.

See [DIRECT_SOLVE.md](DIRECT_SOLVE.md), [RRQR.md](RRQR.md) (a different
route to almost the same kind of answer), and [TIKHONOV.md](TIKHONOV.md)
(the damped alternative that avoids the oscillation, at the cost of
needing its own strength parameter tuned per network).
