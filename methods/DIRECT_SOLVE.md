# Direct Solve (Gaussian Elimination / LU Decomposition) — from scratch

Implementation: [`src/solvers/direct.py`](../src/solvers/direct.py)

This is the "classic" method — the baseline every other solver in this
project is measured against, and the one that fails silently if you don't
add a safety check.

---

## 1. The problem

We want to solve a system of linear equations, written in matrix form:

```
J · Δx = rhs
```

`J` is an `n×n` matrix (the Jacobian, in this project), `rhs` is a known
vector, and `Δx` is the unknown vector we're solving for. If you've done
this by hand in school, you solved small versions of exactly this by
substitution — e.g.:

```
2x + y = 5
 x + 3y = 10
```

Direct solve is just doing that same substitution/elimination process,
generalized to work efficiently for any size `n`, done by a computer.

## 2. Gaussian elimination, from scratch

The classic algorithm:

1. Take the first equation. Use it to eliminate the first variable from
   every equation below it (subtract a multiple of row 1 from each other
   row so that column 1 becomes zero everywhere except row 1).
2. Move to the second equation. Use it to eliminate the second variable
   from every equation below *it*.
3. Repeat until you're left with an upper-triangular system — one where
   the last equation only involves the last variable, the second-to-last
   involves the last two, and so on.
4. Solve from the bottom up ("back-substitution"): the last equation
   directly gives you the last variable; plug that into the second-to-last
   equation to get the next one; and so on.

Worked example:
```
2x + y  = 5        2x + y      = 5
 x + 3y = 10   ->   (5/2)y     = 15/2      (row2 - 0.5*row1)
```
From row 2: `y = 3`. Substitute into row 1: `2x + 3 = 5 → x = 1`.

## 3. LU decomposition — the same idea, reusable

`numpy.linalg.solve(J, rhs)` doesn't repeat elimination from scratch if you
ever needed to solve with the same `J` again — it factors `J` once into two
triangular matrices:

```
J = L · U
```

- `L` (lower-triangular): records the *multipliers* used during
  elimination (i.e., "how much of row 1 did I subtract from row 3?").
- `U` (upper-triangular): the *result* of elimination — exactly the
  triangular system from step 3 above.

Once you have `L` and `U`, solving `J·Δx = rhs` becomes two *cheap*
triangular solves instead of one expensive elimination:
```
L·y  = rhs      (forward substitution, top to bottom)
U·Δx = y        (back substitution, bottom to top)
```
This is what "LU-based" means in the code's docstring, and it's exactly
what `numpy.linalg.solve` does under the hood.

## 4. Where this breaks down — the actual subject of this project

Elimination requires dividing by a "pivot" (the diagonal entry you're
eliminating around). If a pivot is *exactly* zero, you can't divide by it —
`numpy.linalg.solve` raises `LinAlgError` in that case. This project calls
that failure mode **`exact_singular`**.

But here's the trap this whole project studies: **a pivot is almost never
*exactly* zero in floating-point arithmetic**, even when the underlying
matrix is mathematically singular (recall: a floating Delta transformer
makes the true Jacobian singular). Instead, the pivot is some tiny nonzero
number like `1e-14` — and dividing by a tiny number doesn't crash, it just
**amplifies whatever rounding error already exists** in your inputs by a
huge factor.

### Why the condition number is the real signal

The condition number `κ₂(J) = σ_max/σ_min` (largest divided by smallest
"singular value" — see [SVD_PSEUDOINVERSE.md](SVD_PSEUDOINVERSE.md) for what
that means) tells you exactly how much this amplification is. Rule of
thumb: **you lose about `log10(κ)` decimal digits of accuracy** out of the
~16 available in double-precision floating point. If `κ₂ = 1e12`, you've
lost 12 of your 16 digits — the answer LU hands back still "solves" the
equation to a tiny residual (`‖J·Δx − rhs‖` looks small), but `Δx` itself
can be almost meaningless. **Residual size does not indicate correctness**
once `κ` is large — this is the single most important number in this
whole project.

## 5. What `solve_direct()` actually does ([direct.py:48-113](../src/solvers/direct.py#L48-L113))

```python
COND_NUMBER_FAIL_THRESHOLD = 1e12
```
A project-chosen early-warning cutoff (not from the paper) — well before
total precision loss (`~1/eps ≈ 4.5e15`), but high enough not to reject
merely "somewhat imprecise" solves.

```python
cond = float(np.linalg.cond(J))          # computed BEFORE attempting the solve
dx_raw = np.linalg.solve(J, rhs)          # the actual LU solve
```

Two distinct failure modes are logged, never conflated:

| `failure_mode` | What happened | Meaning |
|---|---|---|
| `exact_singular` | `numpy.linalg.solve` itself raised `LinAlgError` | a pivot was *exactly* zero — rare in practice |
| `ill_conditioned` | the solve "succeeded," but `κ₂(J) > 1e12` | the answer is numerically untrustworthy even though nothing crashed |

```python
if not np.isfinite(cond) or cond > cond_fail_threshold:
    ...
    return None, diagnostics   # dx is DISCARDED, even though LU "succeeded"
```
This is the crucial line: **the guard actively throws away a numerically
"valid" answer** rather than letting a caller (Newton-Raphson) silently use
a corrupted update. Without this, `newton_raphson()` could keep iterating
on garbage and eventually report `converged=True` on a meaningless voltage
solution.

## 6. Strengths and weaknesses

- **Strength**: cheapest of the four methods (`O(n³)` once, no extra
  decomposition machinery), and correct on any well-conditioned problem —
  this is why it's the baseline every other solver is compared against.
- **Weakness**: has *no way* to produce a sensible answer once `J` is
  actually singular or severely ill-conditioned — it can only detect the
  problem and refuse (which is exactly its job in this project: on IEEE-4
  Case B and on IEEE-13/37 at realistic load, it's *expected* to fail,
  and the point is that it fails loudly via the guard instead of silently).

See [SVD_PSEUDOINVERSE.md](SVD_PSEUDOINVERSE.md), [RRQR.md](RRQR.md), and
[TIKHONOV.md](TIKHONOV.md) for the three ways this project handles the case
where direct solve has to give up.
