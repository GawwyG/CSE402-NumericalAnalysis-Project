# Rank-Revealing QR (RRQR) — from scratch

Implementation: [`src/solvers/rrqr.py`](../src/solvers/rrqr.py)

RRQR reaches almost the same *kind* of answer as SVD (see
[SVD_PSEUDOINVERSE.md](SVD_PSEUDOINVERSE.md)) — separate the well-determined
directions from the undetermined ones, and give a minimum-norm answer — but
via a different, sometimes cheaper, factorization.

---

## 1. Ordinary QR decomposition, from scratch

Any matrix `J` can be written as:

```
J = Q · R
```

- `Q` is **orthogonal** — its columns are mutually perpendicular unit
  vectors (so `Qᵀ·Q = I`; multiplying by `Qᵀ` is just a rotation/reflection,
  which never amplifies error).
- `R` is **upper-triangular**.

The idea: build `Q`'s columns one at a time from `J`'s own columns, each
time subtracting off whatever part of the new column already points along
a previous `Q` column (this is the Gram-Schmidt process — "make this new
direction perpendicular to everything already chosen"). `R` just records
how much of each original column was "used up" by each `Q` direction.

Once you have this, solving `J·Δx = rhs` becomes:
```
Q·R·Δx = rhs
R·Δx   = Qᵀ·rhs        (since Qᵀ·Q = I, multiplying both sides by Qᵀ cancels Q)
```
and `R·Δx = (Qᵀ·rhs)` is upper-triangular, solvable directly by
back-substitution (same idea as direct solve's step 4) — no separate `L`
needed, since `Q` already plays that role.

## 2. Why plain QR breaks on a singular/rank-deficient matrix

Back-substitution on `R·Δx = c` works by solving the *last* equation first
(it only involves the last variable, divided by `R`'s bottom-right entry),
then working upward. If `J` is singular, `R`'s bottom-right diagonal entry
comes out **at or near zero** — exactly the same division-by-near-zero
problem direct solve has, just relocated to a different matrix. Plain QR +
naive back-substitution gives you no more protection against the
project's central failure mode than plain LU does.

## 3. The fix, part 1: column pivoting reveals the rank

Instead of processing `J`'s columns in their original left-to-right order,
**at each step, pick whichever remaining column has the largest
"leftover" length** (the part not yet explained by previously-chosen
directions) to process next:

```
J[:, piv] = Q · R
```
`piv` is the resulting column order. Because we always pick the
*strongest remaining* direction first, `R`'s diagonal entries `|R_ii|` come
out **non-increasing** in practice — largest first, dropping toward zero
exactly where the matrix runs out of genuinely independent directions.

**This is the "rank-revealing" part**: you can literally read off the
numerical rank by looking at where `|R_ii|` drops from "normal-sized" to
"near zero." The point where it drops is a diagnostic for the same
phenomenon SVD reports via its singular values — a run of large `|R_ii|`
values (well-determined directions) followed by a run of tiny ones (the
undetermined, floating directions).

### The one real difference from SVD's rank rule

SVD's singular values are provably sorted and provably non-negative —
counting "how many exceed `τ`" is unambiguous no matter what. Pivoted QR's
`|R_ii|` sequence is *usually* decreasing but isn't mathematically
guaranteed to be, so this project's rank rule specifically counts only the
**leading run** of values above the threshold `τ`, stopping at the first
one that drops below it ([rrqr.py:164-169](../src/solvers/rrqr.py#L164-L169)) — deliberately choosing not to
"readmit" some later value that happens to bounce back above `τ` after an
earlier drop. This is a real, documented distinction between the two
methods' rank-counting conventions, not just a stylistic difference.

## 4. The fix, part 2: what to do once rank-deficiency is found

Knowing the rank isn't enough — you still need an actual answer for
`Δx`, and plain back-substitution on a now-known-to-be-rank-deficient `R`
still divides by near-zero in its bottom rows. The standard remedy is a
**complete orthogonal factorization**: apply *another* set of orthogonal
transformations, this time to eliminate the extra structure in `R`'s
rank-deficient trailing block, until you're left with something of the
shape `[[T, 0], [0, 0]]` (`T` invertible, everything genuinely-undetermined
zeroed out) — from which the **minimum-norm** least-squares solution can be
read off directly, the same "give the smallest possible answer among all
equally-valid ones" idea as the pseudo-inverse.

This project does **not** implement that second step by hand — it calls
LAPACK's battle-tested `GELSY` routine
(`scipy.linalg.lstsq(..., lapack_driver="gelsy")`), which performs exactly
this pivoted-QR-plus-elimination procedure internally and returns the
minimum-norm answer directly.

## 5. What `solve_rrqr()` actually does ([rrqr.py:51-259](../src/solvers/rrqr.py#L51-L259))

Two separate LAPACK calls, driven by the **same** threshold, doing two
different jobs:

```python
_, R, piv = sla.qr(J_work, mode="economic", pivoting=True)
```
Step one: **diagnostics only**. This computes the pivoted QR purely to
expose `|R_ii|`, the pivot order, and the rank — it does **not** produce
`Δx` itself.

```python
r_max = float(r_diagonal[0])
rank_tolerance = max(atol_used, rtol_used * r_max)
```
Same cutoff formula as SVD's (`max(atol, rtol·(strongest value))`), applied
here to `|R_ii|` instead of singular values.

```python
rcond_used = rank_tolerance / r_max
dx, _, lapack_rank, _ = sla.lstsq(J_work, rhs_work, cond=rcond_used, lapack_driver="gelsy")
```
Step two: the **actual solve**, via GELSY, driven by the *same* threshold
(rescaled into the relative-cutoff form GELSY expects) — so the rank this
module *reports* and the rank GELSY *actually used internally* describe
the same cutoff, not two independently-chosen numbers that could quietly
disagree. `lapack_rank` is kept separately in the diagnostics precisely so
this can be cross-checked against the module's own `numerical_rank`.

```python
condition_number = ... r_max / smallest_accepted_r_diagonal
```
An `|R_00| / |R_(rank-1)|` estimate mirroring SVD's own reported condition
number, for direct side-by-side comparison between the two methods.

A special case at [rrqr.py:171-194](../src/solvers/rrqr.py#L171-L194): if `J` is (numerically) the
all-zero matrix, `r_max = 0`, and the function short-circuits to
`Δx = 0` directly (dividing to get `rcond` would be undefined otherwise).

## 6. Strengths and weaknesses (as found by this project)

- **Strength**: reaches essentially the same *kind* of principled
  minimum-norm answer as SVD, via a route that's sometimes computationally
  cheaper (no full SVD needed, just pivoted QR + one more factorization
  pass).
- **Weakness, discovered empirically**: RRQR shows the **exact same
  oscillation** as SVD on IEEE-13 at realistic load — switching from SVD to
  RRQR does **not** fix the underlying problem, because both give the
  *exact* (undamped) solution to the linearized step, and it's that
  exactness/undamped-ness itself that overshoots on this network's
  particular near-null-space structure, not a quirk of one specific
  factorization technique. This is an important negative result in this
  project: "try a different rank-revealing method" is not, by itself, a
  fix — see [TIKHONOV.md](TIKHONOV.md) for the one method that actually
  does converge there, by deliberately giving up exactness in favor of
  damping.

See [DIRECT_SOLVE.md](DIRECT_SOLVE.md), [SVD_PSEUDOINVERSE.md](SVD_PSEUDOINVERSE.md),
and [TIKHONOV.md](TIKHONOV.md).
