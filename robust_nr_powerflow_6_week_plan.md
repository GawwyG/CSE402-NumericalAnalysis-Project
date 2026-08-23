# Robust Newton–Raphson Power Flow Analysis — Final 6-Week Implementation Plan

## 1. Team Distribution

| Member | Primary Ownership | Main Deliverables | Jump To |
|---|---|---|---|
| **Member A** | Baseline + Core Newton–Raphson | Common NR loop, mismatch equations, Jacobian, direct solve, IEEE 4-bus baseline | [Member A Plan](#4-member-a--baseline--core-newtonraphson) |
| **Member B** | Moore–Penrose Pseudo-Inverse | SVD solver, rank threshold, singular-value diagnostics, MP-PI experiments | [Member B Plan](#5-member-b--moorepenrose-pseudo-inverse) |
| **Member C** | Rank-Revealing QR | RRQR/QRCP solver, numerical rank detection, QR-vs-SVD comparison | [Member C Plan](#6-member-c--rank-revealing-qr) |
| **Member D** | Tikhonov + IEEE 13-Bus Investigation | Tikhonov regularization, λ study, loading/imbalance/topology investigation | [Member D Plan](#7-member-d--tikhonov--ieee-13-bus-investigation) |
| **Member E** | Validation + Scaling + Integration | OpenDSS reference pipeline, feeder provenance, IEEE-118 scaling, plots/tables/reproducibility | [Member E Plan](#8-member-e--validation--scaling--integration) |

### Shared Sections

- [Project Goal](#2-project-goal)
- [Common Technical Architecture](#3-common-technical-architecture)
- [Week-by-Week Timeline](#9-week-by-week-timeline)
- [Test Systems](#10-test-systems)
- [Metrics and Diagnostics](#11-metrics-and-diagnostics)
- [IEEE 13-Bus Investigation](#12-ieee-13-bus-investigation)
- [Repository Structure](#13-repository-structure)
- [Priority and Scope Control](#14-priority-and-scope-control)
- [Final Research Questions](#15-final-research-questions)
- [Definition of Done](#16-definition-of-done)

---

## 2. Project Goal

Reproduce and extend Jang, Kim, and Kim (2023) by comparing numerical methods for handling singular or severely ill-conditioned Jacobians in unbalanced three-phase Newton–Raphson power-flow analysis.

### Core Methods

1. **Classical Newton–Raphson / direct linear solve**
2. **Moore–Penrose Pseudo-Inverse using SVD**
3. **Rank-Revealing QR (RRQR / QR with column pivoting)**
4. **Tikhonov Regularization** — stretch goal

### Main Novel Investigation

Determine why the modified **IEEE 13-bus** case shows a larger numerical error than the other tested systems.

---

## 3. Common Technical Architecture

Use **one shared Newton–Raphson implementation** for all methods.

```text
IEEE / OpenDSS feeder data
        │
        ▼
OpenDSSDirect / DSS-Python
- inspect feeder
- obtain reference solution
- validate element data
        │
        ▼
Normalized 3-phase Python model
- Ybus
- loads
- transformers
- phase/node mapping
        │
        ▼
Shared Newton–Raphson loop
        │
        ▼
J Δx = -F
        │
        ├── Direct solve
        ├── SVD MP-PI
        ├── RRQR
        └── Tikhonov
        │
        ▼
Diagnostics + convergence logs
        │
        ▼
OpenDSS validation + benchmark tables
```

### Shared NR Equations

\[
J_k \Delta x_k = -F(x_k)
\]

\[
x_{k+1} = x_k + \Delta x_k
\]

Only the linear-solver function changes:

```python
dx, diagnostics = solve_linear_step(
    J,
    -F,
    method="direct" | "svd" | "rrqr" | "tikhonov"
)
```

### Important Rule

No member should create a separate version of:

- mismatch equations,
- Jacobian equations,
- state indexing,
- convergence logic,
- network model,
- initialization.

All solver comparisons must use the **same nonlinear model**.

---

# 4. Member A — Baseline + Core Newton–Raphson

## Responsibilities

Own the common nonlinear power-flow implementation.

### Implement

- three-phase state representation,
- bus/phase indexing,
- mismatch function \(F(x)\),
- Jacobian \(J(x)\),
- Newton–Raphson loop,
- convergence criteria,
- direct linear solve,
- IEEE 4-bus baseline.

### Direct Solver

Solve:

\[
J\Delta x=-F
\]

using:

```python
numpy.linalg.solve(J, rhs)
```

or an appropriate sparse solver.

Do **not** compute:

```python
numpy.linalg.inv(J) @ rhs
```

### Jacobian Validation

Validate the analytical Jacobian against centered finite differences:

\[
J_{ij}^{FD}
\approx
\frac{F_i(x+h e_j)-F_i(x-h e_j)}{2h}
\]

Compute:

\[
E_J=
\frac{\|J_{\text{analytic}}-J_{\text{FD}}\|_F}
{\|J_{\text{FD}}\|_F}
\]

### Main Deliverables

- `src/powerflow/newton.py`
- `src/powerflow/mismatch.py`
- `src/powerflow/jacobian.py`
- `src/solvers/direct.py`
- `tests/test_jacobian.py`
- IEEE 4-bus direct-solver failure reproduction

---

# 5. Member B — Moore–Penrose Pseudo-Inverse

## Responsibilities

Implement and validate the base paper's numerical fix.

### Method

Compute:

\[
J=U\Sigma V^T
\]

Then:

\[
\Delta x
=
V\Sigma^+U^T(-F)
\]

### Record

- \(\sigma_{\max}\)
- \(\sigma_{\min}\)
- numerical rank
- SVD tolerance
- condition number
- solve residual
- runtime

### Rank Threshold

Use an explicit relative threshold such as:

\[
\sigma_i >
\epsilon \max(m,n)\sigma_{\max}
\]

The threshold must be logged and reported.

### Main Deliverables

- `src/solvers/svd_pinv.py`
- singular-value diagnostics
- numerical-rank plots
- MP-PI results for IEEE 4/13/37
- SVD tolerance sensitivity study

---

# 6. Member C — Rank-Revealing QR

## Responsibilities

Implement the primary alternative numerical method.

### Method

Use QR with column pivoting:

\[
JP=QR
\]

Estimate the numerical rank from the diagonal structure of \(R\), then solve the rank-deficient least-squares problem.

### Recommended SciPy Implementation

```python
scipy.linalg.lstsq(
    J,
    rhs,
    lapack_driver="gelsy"
)
```

### Important

Do **not** use ordinary QR + simple back-substitution for an exactly singular Jacobian.

### Record

- estimated rank,
- pivot ordering,
- smallest accepted \(|R_{ii}|\),
- residual norm,
- runtime,
- iteration count.

### Main Deliverables

- `src/solvers/rrqr.py`
- rank-detection tests
- RRQR results for IEEE 4/13/37
- RRQR-vs-SVD comparison
- runtime comparison

---

# 7. Member D — Tikhonov + IEEE 13-Bus Investigation

## Responsibilities

Implement regularization and lead the anomaly analysis.

## Tikhonov Method

Solve:

\[
\min_{\Delta x}
\left(
\|J\Delta x+F\|_2^2+
\lambda\|\Delta x\|_2^2
\right)
\]

Prefer the augmented system:

\[
\begin{bmatrix}
J\\
\sqrt{\lambda}I
\end{bmatrix}
\Delta x
\approx
\begin{bmatrix}
-F\\
0
\end{bmatrix}
\]

Do not explicitly form:

\[
(J^TJ+\lambda I)^{-1}
\]

### λ Parameterization

Use:

\[
\lambda=\alpha\sigma_{\max}^2
\]

Suggested sweep:

\[
\alpha\in
\{10^{-12},10^{-10},10^{-8},10^{-6},10^{-4},10^{-2}\}
\]

### Main Deliverables

- `src/solvers/tikhonov.py`
- λ sensitivity experiment
- IEEE 13-bus loading study
- imbalance study
- transformer-configuration study
- zero-sequence investigation
- anomaly discussion

---

# 8. Member E — Validation + Scaling + Integration

## Responsibilities

Own independent validation and reproducibility.

### OpenDSS Tasks

- acquire official feeder files,
- document source/provenance,
- compile each feeder,
- export reference voltages,
- inspect transformer connections,
- record OpenDSS convergence,
- investigate `PPM_Antifloat`.

### Reference Output Format

Export at least:

```text
bus
phase
V_real
V_imag
V_mag
V_angle
```

### Scaling Tasks

Use IEEE 118-bus only as a **balanced computational scaling benchmark**.

Possible loading:

```python
import pandapower.networks as pn
net118 = pn.case118()
```

### Main Deliverables

- `src/validation/opendss.py`
- `data/provenance.yml`
- OpenDSS reference CSV files
- IEEE-118 runtime benchmark
- final plots/tables
- reproducibility verification
- README/environment files

---

# 9. Week-by-Week Timeline

## Week 1 — Infrastructure and Linear-Solver Unit Tests

### Member A
- create common NR skeleton,
- define state and solver interfaces,
- prepare synthetic test matrices.

### Member B
- implement SVD pseudo-inverse,
- add rank and singular-value logging.

### Member C
- implement RRQR/GELSY,
- test on full-rank and rank-deficient matrices.

### Member D
- implement Tikhonov augmented solve,
- prepare λ sweep.

### Member E
- install/configure OpenDSSDirect,
- download feeder files,
- create provenance records.

### Week 1 Milestone

All four linear solvers pass controlled matrix tests for:

- well-conditioned,
- ill-conditioned,
- rank-deficient systems.

---

## Week 2 — IEEE 4-Bus + Jacobian Validation

### Member A
- implement full 3-phase NR,
- construct/reconstruct IEEE 4-bus,
- validate Jacobian using finite differences,
- reproduce classical failure.

### Member B
- integrate MP-PI into common NR,
- reproduce convergence.

### Member C
- integrate RRQR,
- reproduce convergence.

### Member D
- run initial Tikhonov experiments.

### Member E
- generate OpenDSS reference outputs,
- validate model parameters.

### Week 2 Milestone

Complete end-to-end IEEE 4-bus experiment.

---

## Week 3 — IEEE 13 and IEEE 37

### Member A
- reconstruct modified IEEE 13-bus case.

### Member B
- run MP-PI on IEEE 13-bus.

### Member C
- run RRQR on IEEE 13-bus.

### Member D
- begin 13-bus anomaly experiments.

### Member E
- prepare IEEE 37-bus OpenDSS model/reference.

### Week 3 Milestone

IEEE 4, 13, and 37 data/model pipelines are operational.

---

## Week 4 — Main Experimental Week

Run full solver comparisons on:

- IEEE 4-bus,
- IEEE 13-bus,
- IEEE 37-bus.

### Main IEEE 13-Bus Experiments

- load scaling,
- phase imbalance,
- transformer connections,
- zero-sequence behavior,
- rank thresholds,
- OpenDSS anti-float behavior.

### Week 4 Milestone

Core scientific results complete.

---

## Week 5 — Robustness + Scaling

### Complete

- SVD tolerance ablation,
- RRQR tolerance ablation,
- Tikhonov λ study,
- IEEE 37 quasi-radial case if ready,
- IEEE 69 only if provenance is resolved,
- IEEE 118 runtime scaling,
- final tables and plots.

### Week 5 Milestone

**Freeze results.**

No new major method should be added after this point.

---

## Week 6 — Verification + Final Report

### Complete

- rerun from a clean environment,
- verify numerical outputs,
- finalize figures,
- finalize tables,
- write methodology,
- write solver comparison,
- write IEEE 13-bus analysis,
- document limitations,
- clean repository,
- prepare presentation/demo.

### Week 6 Milestone

Fully reproducible final submission.

---

# 10. Test Systems

## IEEE 4-Bus — Development / Reproduction Case

Purpose:

- easiest system for debugging,
- inspect Jacobian manually,
- reproduce singularity,
- verify all solvers.

Use it as the first hard gate.

---

## IEEE 13-Bus — Main Investigation Case

Purpose:

- reproduce paper's modified system,
- investigate higher reported error,
- test loading, imbalance, grounding, and numerical sensitivity.

This is the **main novelty case**.

---

## IEEE 37-Bus — Main Realistic Ungrounded Case

Purpose:

- realistic three-phase unbalanced feeder,
- extensive delta configuration,
- validate numerical robustness on a larger system.

Optional:

- reconstruct the quasi-radial modification from the paper.

---

## IEEE 69-Bus — Secondary Stretch Case

Only include if the exact benchmark parameter source can be established.

Do not delay the primary experiments for this case.

---

## IEEE 118-Bus — Scaling Only

Use only for:

- runtime,
- solver scaling,
- comparison on larger full-rank systems.

Do not treat this as evidence about ungrounded-transformer singularity.

---

# 11. Metrics and Diagnostics

Log the following **at every Newton iteration**:

| Metric | Purpose |
|---|---|
| \(||F_k||_\infty\) | nonlinear convergence |
| \(||\Delta x_k||_2\) | update stability |
| \(\kappa_2(J_k)\) | conditioning |
| \(\sigma_{\min}(J_k)\) | proximity to rank deficiency |
| numerical rank | singularity diagnosis |
| \(||J\Delta x+F||_2\) | linear-solver residual |
| linear-solve runtime | solver cost |
| total iteration runtime | overall cost |
| voltage min/max | physical sanity |
| fallback/switch count | hybrid behavior if used |

At final convergence compare:

- maximum voltage-magnitude error,
- mean voltage-magnitude error,
- voltage-angle error,
- line-to-ground voltage error,
- line-to-line voltage error,
- symmetrical-component error,
- total power-balance error,
- number of NR iterations,
- total runtime.

---

# 12. IEEE 13-Bus Investigation

## A. Loading

Suggested load factors:

- 0.50
- 0.75
- 1.00
- 1.25
- 1.50

Measure effects on:

- condition number,
- singular values,
- iteration count,
- final voltage error,
- solver success/failure.

---

## B. Phase Imbalance

Suggested imbalance levels:

- 0%
- 10%
- 20%
- 30%

Goal:

Determine whether imbalance alone explains the anomaly.

---

## C. Transformer Configuration

Compare relevant cases such as:

- Yg–Δ,
- Δ–Δ,
- grounded alternatives where physically meaningful.

Goal:

Determine whether floating/unreferenced network regions generate the rank deficiency.

---

## D. Zero-Sequence / Voltage-Reference Analysis

Compare symmetrical components:

\[
V_0,\quad V_1,\quad V_2
\]

Also compare:

\[
V_{ab},\quad V_{bc},\quad V_{ca}
\]

Main hypothesis to test:

The comparatively larger 13-bus discrepancy may be concentrated in common-mode/zero-sequence voltage rather than physically important line-to-line voltage.

Treat this as a **hypothesis**, not an assumed explanation.

---

## E. Numerical Parameter Sensitivity

Test:

- SVD rank threshold,
- RRQR rank threshold,
- Tikhonov λ,
- initial voltage guess.

---

## F. OpenDSS Regularization

Inspect:

- `PPM_Antifloat = default`
- `PPM_Antifloat = 0`
- line shunt capacitance
- capacitor bank restoration/removal
- distributed-load restoration/removal

Goal:

Determine whether the reference simulator is automatically regularizing a floating network.

---

# 13. Repository Structure

```text
project/
│
├── data/
│   ├── raw/
│   │   ├── ieee4/
│   │   ├── ieee13/
│   │   └── ieee37/
│   │
│   ├── paper_reconstruction/
│   │   ├── ieee4_jang2023/
│   │   ├── ieee13_jang2023/
│   │   ├── ieee37_radial/
│   │   ├── ieee37_quasiradial/
│   │   └── ieee69/
│   │
│   └── provenance.yml
│
├── src/
│   ├── model/
│   │   ├── network.py
│   │   ├── ybus.py
│   │   ├── loads.py
│   │   └── transformer.py
│   │
│   ├── powerflow/
│   │   ├── mismatch.py
│   │   ├── jacobian.py
│   │   └── newton.py
│   │
│   ├── solvers/
│   │   ├── direct.py
│   │   ├── svd_pinv.py
│   │   ├── rrqr.py
│   │   └── tikhonov.py
│   │
│   ├── validation/
│   │   └── opendss.py
│   │
│   └── diagnostics/
│       ├── conditioning.py
│       └── sequence_components.py
│
├── experiments/
│   ├── exp01_4bus.py
│   ├── exp02_13bus.py
│   ├── exp03_37bus.py
│   ├── exp04_13bus_ablation.py
│   └── exp05_scaling.py
│
├── tests/
│   ├── test_linear_solvers.py
│   ├── test_jacobian.py
│   ├── test_transformer.py
│   └── test_4bus.py
│
├── results/
├── figures/
├── requirements.txt
└── README.md
```

---

# 14. Priority and Scope Control

## Must Complete

1. shared three-phase NR implementation,
2. Jacobian finite-difference validation,
3. IEEE 4-bus reproduction,
4. Moore–Penrose solver,
5. RRQR solver,
6. IEEE 13-bus experiments,
7. IEEE 37-bus experiments,
8. OpenDSS validation,
9. 13-bus anomaly investigation.

## Stretch Goals

1. Tikhonov regularization,
2. IEEE 37 quasi-radial case,
3. IEEE 69 reconstruction,
4. IEEE 118 scaling.

## Drop If Time Is Limited

- ML classifier,
- IEEE 123-bus,
- very large feeders,
- GPU implementation,
- additional numerical solvers.

---

# 15. Final Research Questions

### RQ1 — Robustness

How reliably do SVD pseudo-inverse, RRQR, and Tikhonov regularization handle singular or severely ill-conditioned Newton–Raphson Jacobians?

### RQ2 — Numerical Conditioning

How are condition number, numerical rank, and singular-value spectrum related to convergence and voltage error?

### RQ3 — IEEE 13-Bus Anomaly

Which factors—loading, topology, transformer grounding, zero-sequence reference, numerical-rank tolerance, or regularization—best explain the comparatively elevated error in the modified IEEE 13-bus system?

### RQ4 — Computational Cost

What accuracy, convergence, and runtime trade-offs exist among direct solving, SVD, RRQR, and Tikhonov regularization?

---

# 16. Definition of Done

The project is considered complete when:

- [ ] The common three-phase NR solver works.
- [ ] The analytical Jacobian passes finite-difference validation.
- [ ] Classical NR failure is reproduced on at least one singular case.
- [ ] Moore–Penrose successfully handles the same case.
- [ ] RRQR successfully handles the same case.
- [ ] IEEE 13-bus and IEEE 37-bus experiments are completed.
- [ ] OpenDSS reference results are stored and documented.
- [ ] Conditioning and numerical-rank diagnostics are logged.
- [ ] The IEEE 13-bus anomaly receives a controlled sensitivity analysis.
- [ ] Runtime and accuracy comparisons are produced.
- [ ] Results can be reproduced from a clean environment.
- [ ] Data sources and modifications are documented.
- [ ] Final figures, tables, and report are generated from saved experiment outputs.

---

# Final Priority

The project should remain focused on:

\[
\boxed{
\text{Direct NR}
\rightarrow
\text{SVD MP-PI}
\rightarrow
\text{RRQR}
\rightarrow
\text{13-bus investigation}
}
\]

Tikhonov, IEEE 69, IEEE 118, and any additional methods should only be attempted after the core comparison is stable and reproducible.
