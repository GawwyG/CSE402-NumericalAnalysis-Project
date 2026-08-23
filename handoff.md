# Project Handoff Context

You are taking over as a rigorous academic research assistant and numerical-analysis/engineering tutor for a university group project. Treat everything below as the current project state. Do **not restart topic selection** or propose an unrelated research direction unless you identify a serious methodological flaw.

When making technical claims, distinguish clearly between:

* facts explicitly stated in the base paper,
* information from official IEEE/EPRI/MATPOWER sources,
* our reconstruction assumptions,
* your own interpretation or proposed methodology.

Do not invent missing feeder parameters, references, implementation details, or results.

---

# 1. Project Context

We are a **5-person undergraduate CS/AI/ML team** doing a project for a course titled:

**Numerical Analysis, Simulation and Modelling**

Timeline:

* approximately **6 weeks**
* moderate Python experience
* little prior power-systems background
* no paid software/resources
* implementation must be reproducible using public data/software

The course covers or relates to:

* Newton–Raphson
* Gauss elimination
* LU decomposition
* QR decomposition
* eigenvalue decomposition
* condition numbers
* numerical error
* optimization
* numerical modelling/simulation

The project's topic and general contribution are already finalized.

---

# 2. Base Paper

**J. Jang, D. Kim, and I. Kim**

> "Singularity Handling for Unbalanced Three-Phase Transformers in Newton-Raphson Power Flow Analyses Using Moore-Penrose Pseudo-Inverse"

**IEEE Access, 2023**

DOI:

https://doi.org/10.1109/ACCESS.2023.3269503

The original PDF should ideally be supplied to you as an attachment as well.

The paper develops a Newton–Raphson power-flow method in MATLAB where a **Moore–Penrose pseudo-inverse computed using SVD** is used when the Jacobian is singular or nearly singular.

The paper evaluates modified versions of:

1. IEEE 4-bus
2. IEEE 13-node
3. IEEE 37-bus radial
4. modified IEEE 37-bus quasi-radial
5. modified IEEE 69-bus radial

The authors use **DIgSILENT PowerFactory** as the comparison/reference solver.

We cannot use PowerFactory because it is commercial.

---

# 3. Core Problem From the Paper

Standard Newton–Raphson power flow repeatedly solves a system of the form

[
J_k \Delta x_k = -F(x_k)
]

where:

* (J_k) = Jacobian at iteration (k)
* (F(x_k)) = active/reactive power mismatch
* (\Delta x_k) = state correction

and

[
x_{k+1}=x_k+\Delta x_k.
]

In ungrounded three-phase systems, particularly with transformer connections such as:

* Yg–Delta
* Y–Delta
* Delta–Delta
* ungrounded wye

the zero-sequence network can become open.

This may leave parts of the network without a unique phase-to-ground reference.

The resulting admittance/Jacobian matrices may be singular or extremely ill-conditioned.

The base paper reports Jacobian condition numbers that can become enormous; one 4-bus Yg–Delta configuration with no load on the delta secondary reaches approximately

[
5.62\times10^{160}.
]

Classical NR fails in such cases.

The proposed paper solution is the Moore–Penrose pseudo-inverse.

---

# 4. Important Correction: Do Not Describe NR as Explicitly Inverting J

Although the paper often writes equations in terms of (J^{-1}), our implementation and report should say:

> Newton–Raphson requires solving a linear system involving the Jacobian at each iteration.

Do **not** implement

```python
np.linalg.inv(J) @ rhs
```

for the classical baseline.

Instead use something equivalent to:

```python
np.linalg.solve(J, rhs)
```

or an appropriate sparse solver.

The numerical failure we study is failure/instability of the Jacobian linear solve due to singularity or severe ill-conditioning.

---

# 5. Our Finalized Contribution

Our project is a **methodological extension + comparative numerical study**.

## Core contribution

Compare four approaches for the same Newton–Raphson Jacobian problem:

### A. Classical Direct Solve

Baseline.

Solve

[
J\Delta x=-F.
]

Expected to fail or become unstable for rank-deficient systems.

---

### B. Moore–Penrose Pseudo-Inverse

Reproduce the base paper.

Using:

[
J=U\Sigma V^T
]

and

[
J^+=V\Sigma^+U^T.
]

Then:

[
\Delta x=J^+(-F).
]

Record singular values, numerical rank, tolerance, condition number and runtime.

---

### C. Rank-Revealing QR

This is our **primary alternative**.

An earlier idea was ordinary QR + back-substitution, but that is insufficient for an exactly singular Jacobian because (R) itself becomes rank-deficient.

Therefore the method should be:

**Rank-Revealing QR / QR with Column Pivoting (RRQR / QRCP)**

[
JP=QR.
]

Use rank detection and a rank-deficient least-squares solve.

A suitable SciPy implementation is:

```python
scipy.linalg.lstsq(
    J,
    rhs,
    lapack_driver="gelsy"
)
```

GELSY uses pivoted QR / complete orthogonal factorization.

Do not claim that ordinary unpivoted QR automatically fixes singularity.

---

### D. Tikhonov Regularization

Stretch goal.

Conceptual problem:

[
\min_{\Delta x}
\left(
|J\Delta x+F|_2^2+
\lambda|\Delta x|_2^2
\right).
]

Do **not** implement the explicit inverse

[
(J^TJ+\lambda I)^{-1}J^T.
]

Forming (J^TJ) squares the condition number:

[
\kappa(J^TJ)=\kappa(J)^2.
]

Instead solve the augmented least-squares system:

[
\begin{bmatrix}
J\
\sqrt{\lambda}I
\end{bmatrix}
\Delta x
\approx
\begin{bmatrix}
-F\
0
\end{bmatrix}.
]

A scale-aware parameterization is:

[
\lambda=\alpha\sigma_{\max}^2
]

with a possible sweep:

[
\alpha\in
{10^{-12},10^{-10},10^{-8},10^{-6},10^{-4},10^{-2}}.
]

Tikhonov should be reported as a sensitivity/regularization study unless a defensible fixed-(\lambda) selection procedure is developed.

---

# 6. Main Novel Investigation: IEEE 13-Node Error

An earlier summary incorrectly described the error as roughly **0.2%**.

Correct value from the paper:

[
0.000208\text{ p.u.}
]

which corresponds to

[
0.0208%.
]

The paper explicitly states that the IEEE 13-node case exhibits the largest error among its test cases.

The authors suggest that:

* small system size,
* heavy loading,
* radial structure,
* system sensitivity

may contribute.

However, their IEEE 37 results indicate that **imbalance alone cannot explain the effect**.

They call for further study into why the 13-node case has comparatively high error.

Our key research contribution is therefore a **controlled numerical/spectral investigation of the IEEE 13-node anomaly**.

Do not claim beforehand that we already know the cause.

---

# 7. Particularly Important 13-Bus Hypothesis

One hypothesis worth explicitly testing is **zero-sequence/common-mode voltage ambiguity**.

Ungrounded networks may not have a unique phase-to-ground reference.

Therefore two numerical solutions may differ in common-mode voltage while agreeing much more closely on physically meaningful line-to-line voltages.

Compare both:

[
V_a,;V_b,;V_c
]

and

[
V_{ab},;V_{bc},;V_{ca}.
]

Also transform voltage error into symmetrical components:

[
V_0,;V_1,;V_2.
]

Investigate whether the 13-node discrepancy is concentrated primarily in

[
\Delta V_0
]

rather than positive-sequence, negative-sequence or line-to-line voltage.

This is a **hypothesis**, not an established conclusion.

---

# 8. Final Recommended Software Architecture

Do **not** make pandapower's three-phase power-flow solver the core numerical implementation.

Recommended architecture:

```text
IEEE / EPRI / MATPOWER feeder data
              │
              ▼
OpenDSSDirect.py / DSS-Python
- parse or inspect feeder
- check phase/node definitions
- obtain reference solution
- inspect transformer/line parameters
              │
              ▼
Normalized custom Python 3-phase model
- phase/node indexing
- Ybus
- loads
- transformer models
              │
              ▼
OUR Newton–Raphson loop
              │
              ▼
J Δx = -F
              │
      ┌───────┼──────────┬─────────────┐
      ▼       ▼          ▼             ▼
    Direct   SVD        RRQR       Tikhonov
              │
              ▼
conditioning / convergence diagnostics
              │
              ▼
OpenDSS comparison
```

The main scientific solver should therefore be implemented using:

* Python
* NumPy
* SciPy

OpenDSS is primarily:

* feeder source,
* model-inspection tool,
* independent reference solver.

---

# 9. Why Not Use pandapower as the Main Solver?

pandapower is still useful, but not ideal for reproducing this paper's exact failure mechanism.

Its ordinary balanced NR implementation can be inspected/modified.

However, pandapower's three-phase power flow uses a sequence-based approach in which positive sequence and zero/negative sequence are not handled as the same full three-phase NR formulation used in this study.

Therefore pandapower should be used only for things such as:

* balanced sanity tests,
* IEEE-118 scaling,
* optional cross-checks.

Do not build the main ungrounded-three-phase experiment around `runpp_3ph()`.

---

# 10. OpenDSS / DSS-Python / OpenDSSDirect

OpenDSS is maintained by EPRI and contains machine-readable implementations of many IEEE distribution feeders.

Recommended Python access:

```bash
pip install OpenDSSDirect.py
```

or DSS-Python.

OpenDSSDirect.py is a cross-platform interface from DSS-Extensions, not the Windows COM interface.

Use OpenDSS to:

* load IEEE feeders,
* inspect bus/node structures,
* inspect transformers,
* inspect line impedances,
* generate reference voltages,
* compare converged results.

Do not let OpenDSS perform our custom Jacobian linear-solver experiment.

---

# 11. Very Important OpenDSS Issue: Anti-Float Regularization

OpenDSS includes a transformer parameter called:

```text
PPM_Antifloat
```

whose default small grounding admittance is intended to prevent numerical singularity in floating transformer windings.

This is directly relevant because we are intentionally studying the singularity that a simulator may automatically suppress.

Therefore document and, where possible, compare:

```text
PPM_Antifloat = default
```

versus

```text
PPM_Antifloat = 0
```

Also investigate:

* line shunt capacitance,
* explicit capacitor banks,
* grounded loads,
* neutral conductors,

because these may provide a ground reference and remove the mathematical floating condition.

---

# 12. Dataset / Test-Feeder Strategy

The paper does **not use an ML-style dataset**.

It uses electrical benchmark networks.

The complete modified MATLAB case files are not publicly supplied in the paper, so our methodology is:

```text
official/public base feeder
        ↓
apply modifications explicitly described by Jang et al.
        ↓
document any assumptions
        ↓
save reconstructed feeder
        ↓
use identical feeder for every solver
```

Do not claim that our reconstructed files are the authors' exact private dataset.

Use wording such as:

> reconstructed test cases based on the published IEEE benchmark data and the modifications reported by Jang et al.

---

# 13. Essential Data Links

## IEEE PES Distribution Test Feeder Resources

https://cmte.ieee.org/pes-testfeeders/resources/

## IEEE Radial Distribution Test Feeders data document

Contains feeder engineering information such as bus, line, load, impedance and transformer data:

https://cmte.ieee.org/pes-testfeeders/wp-content/uploads/sites/167/2017/08/testfeeders.pdf

## EPRI/OpenDSS IEEE Test Cases

Machine-readable DSS implementations:

https://sourceforge.net/p/electricdss/code/HEAD/tree/trunk/Version8/Distrib/IEEETestCases/

## IEEE 13-node OpenDSS folder

https://sourceforge.net/p/electricdss/code/HEAD/tree/trunk/Version8/Distrib/IEEETestCases/13Bus/

## IEEE 13-node main circuit file

https://sourceforge.net/p/electricdss/code/HEAD/tree/trunk/Version8/Distrib/IEEETestCases/13Bus/IEEE13Nodeckt.dss

## MATPOWER IEEE/69-Bus Benchmark

Public `case69.m`:

https://github.com/MATPOWER/matpower/blob/master/data/case69.m

---

# 14. IEEE 4-Bus Reconstruction

Use the IEEE/OpenDSS 4-bus transformer cases as the base.

Paper experiment:

* transformer between buses 2 and 3
* Yg–Delta configuration
* 6 MVA
* 12.47/4.16 kV
* (R=0.01) p.u.
* (X=0.06) p.u.

The authors compare configurations where the load is on either side of the transformer.

The important singular case has **no load on the delta secondary side**.

Their condition-number study compares all nine combinations of:

* Yg
* Y
* Delta

on primary and secondary transformer windings.

Use IEEE 4-bus as the first development/debugging system because all matrices are small enough to inspect manually.

---

# 15. IEEE 13-Node Reconstruction

This is our most important feeder.

Start from the official IEEE/OpenDSS 13-node system.

The paper explicitly modifies it by:

1. removing the distributed load,
2. removing the capacitor bank,
3. producing a system with 13 buses,
4. using seven loads,
5. making T1 Yg–Delta,
6. making T2 Delta–Delta.

Paper transformer data:

| Transformer | MVA | High kV | Low kV | R p.u. | X p.u. |
| ----------- | --: | ------: | -----: | -----: | -----: |
| T1          |   5 |     115 |   4.16 |   0.08 |   0.10 |
| T2          | 0.5 |    4.16 |   0.48 |   0.02 |  0.011 |

The paper runs both:

* balanced
* approximately 30%-unbalanced

versions.

Important reproducibility limitation:

The paper does **not fully specify a machine-readable phase-by-phase definition of the 30% imbalance**.

Any rule we use to generate that imbalance must therefore be explicitly documented as a reconstruction assumption.

Do not silently invent the rule.

---

# 16. IEEE 37-Bus Radial

Use the official IEEE/OpenDSS 37-node feeder.

This is especially relevant because it is naturally a three-wire delta/ungrounded system.

The paper states:

* 4.8-kV feeder,
* two Delta–Delta transformers,
* entire feeder ungrounded,
* transformer XFM between buses 709 and 775,
* no load on the XFM secondary.

This makes IEEE 37 a strong realistic validation of the ungrounded-singularity problem.

---

# 17. Potential IEEE-37 Transformer Parameter Discrepancy

A potential discrepancy was identified between the paper's transformer table and public OpenDSS data.

The paper reports approximately:

[
X=0.00181\text{ p.u.}
]

for the XFM transformer.

A public OpenDSS IEEE-37 model uses:

```text
Xhl = 1.81
```

which, because OpenDSS specifies this quantity in percent, corresponds approximately to:

[
0.0181\text{ p.u.}
]

This appears to be a factor-of-10 difference.

Do not silently choose one.

Maintain, if necessary:

```text
ieee37_official
ieee37_jang2023
```

and explicitly investigate/verify whether this reflects:

* a typo,
* a per-unit conversion difference,
* or an intentional modification.

Treat this point as something requiring verification, not as a settled error in the paper.

---

# 18. IEEE 37-Bus Quasi-Radial Reconstruction

The quasi-radial case is not a separate IEEE standard feeder.

The paper constructs it from IEEE 37 by adding three lines.

Connections:

* 718–733
* 729–742
* 736–741

The paper gives both zero-sequence and positive/negative-sequence impedance approximately as:

[
0.01+j0.001;\Omega/\text{km}.
]

The resulting system has three additional loops.

Generate this feeder programmatically from the radial IEEE-37 base case rather than manually maintaining two unrelated copies.

---

# 19. IEEE 69-Bus Reconstruction

The 69-bus system is not the same kind of IEEE PES feeder package as IEEE 13/37.

Use the public MATPOWER `case69.m` as a reproducible base source.

The base network is fundamentally a balanced representation.

Jang et al. modify it by adding three **Yg–Delta transformers** at:

[
3\rightarrow4
]

[
3\rightarrow28
]

[
3\rightarrow36.
]

Paper transformer parameters:

| Location | MVA | High kV | Low kV | R p.u. | X p.u. |
| -------- | --: | ------: | -----: | -----: | -----: |
| 3–4      |  10 |    13.8 |   13.8 | 0.0007 | 0.0018 |
| 3–28     |  10 |    13.8 |   13.8 | 0.0023 | 0.0056 |
| 3–36     |  10 |    13.8 |   13.8 | 0.0023 | 0.0056 |

The modified system has:

* 69 buses
* 48 loads
* 3 added transformers

Because the public case is balanced and the paper does not completely document the phase-specific 30%-imbalance construction, treat our IEEE-69 case as a **reconstruction**, not an exact reproduction.

IEEE-69 is lower priority than IEEE 4, 13 and 37.

---

# 20. IEEE 118-Bus

IEEE-118 is optional and should only be used for **computational scaling**.

It can be obtained through pandapower/PYPOWER/MATPOWER.

Example:

```python
import pandapower.networks as pn

net = pn.case118()
```

Do not present IEEE-118 as evidence about the ungrounded three-phase transformer singularity because it is primarily a balanced transmission benchmark.

Use it to ask questions such as:

* SVD runtime scaling,
* RRQR runtime scaling,
* direct-solver runtime,
* Tikhonov overhead.

---

# 21. Common NR Code Architecture

All four numerical methods must share the same nonlinear model.

Recommended interface:

```python
dx, diagnostics = solve_linear_step(
    J,
    rhs,
    method="direct" | "svd" | "rrqr" | "tikhonov",
    options=...
)
```

Everything else remains identical:

* (F(x))
* (J(x))
* initial state
* convergence tolerance
* iteration maximum
* network data
* voltage update
* logging

This is essential for a fair numerical comparison.

---

# 22. Jacobian Validation Is Mandatory

Because the entire project concerns Jacobian singularity, we must verify the Jacobian before trusting experiments.

Compare the analytical Jacobian with a centered finite-difference approximation:

[
J_{ij}^{FD}
\approx
\frac{F_i(x+h e_j)-F_i(x-h e_j)}{2h}.
]

Measure:

[
E_J=
\frac{
|J_{\text{analytic}}-J_{\text{FD}}|*F
}{
|J*{\text{FD}}|_F
}.
]

This should be a hard validation requirement before running the larger test feeders.

---

# 23. Diagnostics to Record at Every NR Iteration

For every iteration (k), log:

[
|F_k|_\infty
]

[
|\Delta x_k|_2
]

[
\kappa_2(J_k)
]

[
\sigma_{\max}(J_k)
]

[
\sigma_{\min}(J_k)
]

numerical rank,

[
|J\Delta x+F|_2
]

linear-solve runtime,

total iteration runtime,

voltage min/max,

convergence status.

For RRQR additionally record:

* pivot ordering,
* rank threshold,
* accepted diagonal magnitude of (R).

For SVD record:

* singular-value tolerance,
* number of truncated singular values.

For Tikhonov record:

* (\lambda),
* regularized residual,
* step norm.

---

# 24. Final-Solution Metrics

Compare every solver using:

* convergence success/failure,
* number of NR iterations,
* maximum voltage-magnitude error,
* mean voltage-magnitude error,
* voltage-angle error,
* line-to-ground voltage error,
* line-to-line voltage error,
* positive/negative/zero-sequence voltage error,
* total power balance,
* runtime.

Where feasible compare against OpenDSS reference results.

Do not evaluate only "converged/not converged."

---

# 25. IEEE 13-Bus Controlled Experiments

The main anomaly investigation should include the following.

## Load scaling

Suggested:

[
0.50,;0.75,;1.00,;1.25,;1.50
]

times nominal loading.

Investigate whether loading affects:

* singular-value spectrum,
* condition number,
* solver error,
* iteration count,
* convergence.

---

## Imbalance

Suggested:

* 0%
* 10%
* 20%
* 30%

Goal:

Determine whether imbalance itself explains the anomaly.

The base paper's IEEE-37 results already suggest imbalance alone is insufficient.

---

## Transformer configuration

Where physically meaningful compare relevant variants:

* Yg–Delta
* Delta–Delta
* grounded alternatives

Goal:

isolate whether floating transformer regions create the numerical rank deficiency.

---

## Zero-sequence/reference effects

Compare:

[
V_0,;V_1,;V_2
]

and

[
V_{ab},;V_{bc},;V_{ca}.
]

Goal:

Determine whether apparent voltage error is predominantly a common-mode reference discrepancy.

---

## Numerical tolerance sensitivity

Vary:

* SVD rank threshold,
* RRQR rank threshold,
* Tikhonov (\lambda),
* possibly NR stopping tolerance.

---

## Initial state

Compare at least:

* flat start,
* warm/near-reference start where appropriate.

---

## OpenDSS anti-float sensitivity

Compare:

* default anti-float admittance,
* anti-float disabled if feasible,
* relevant line-shunt settings.

---

# 26. Team Distribution

We have five members.

## Member A — Baseline / Core NR

Owns:

* network/state representation
* mismatch equations
* Jacobian
* Newton–Raphson loop
* direct solver
* IEEE 4-bus reproduction

No other member should independently rewrite the nonlinear model.

---

## Member B — Moore–Penrose / SVD

Owns:

* SVD pseudo-inverse
* numerical rank
* SVD threshold
* singular-value plots
* condition-number diagnostics
* reproduction of MP-PI results

---

## Member C — RRQR

Owns:

* pivoted QR / rank-revealing QR
* rank estimation
* least-squares solve
* QR-vs-SVD comparison
* runtime comparison

---

## Member D — Tikhonov + IEEE 13 Investigation

Owns:

* Tikhonov regularization
* (\lambda) study
* load scaling
* imbalance study
* transformer sensitivity
* zero-sequence analysis

---

## Member E — Validation / Scaling / Integration

Owns:

* OpenDSS pipeline
* feeder provenance
* reference CSV outputs
* IEEE-118 scaling
* plots/tables
* reproducibility
* environment/README

---

# 27. Six-Week Timeline

## Week 1 — Infrastructure

* create repository
* freeze Python environment
* acquire official feeder data
* implement common linear-solver API
* implement direct/SVD/RRQR/Tikhonov on synthetic matrices
* set up OpenDSSDirect
* create provenance documentation

Milestone:

all numerical linear solvers pass well-conditioned, ill-conditioned and rank-deficient synthetic tests.

---

## Week 2 — IEEE 4 + Jacobian

* implement 3-phase NR core
* reconstruct 4-bus experiment
* finite-difference Jacobian validation
* reproduce classical failure
* integrate SVD
* integrate RRQR
* initial Tikhonov test
* OpenDSS cross-check

Milestone:

complete end-to-end IEEE 4 experiment.

---

## Week 3 — IEEE 13 + 37

* reconstruct modified IEEE 13
* run direct/SVD/RRQR
* begin Tikhonov/anomaly study
* load IEEE 37
* generate OpenDSS reference

Milestone:

IEEE 4/13/37 pipelines operational.

---

## Week 4 — Main Experiments

Complete main comparisons on:

* IEEE 4
* IEEE 13
* IEEE 37

Run controlled IEEE-13 investigations.

Milestone:

core scientific results complete.

---

## Week 5 — Robustness + Scaling

* SVD threshold ablation
* RRQR threshold ablation
* Tikhonov lambda study
* IEEE-37 quasi-radial
* IEEE-69 only if reconstruction is reliable
* IEEE-118 scaling
* generate plots/tables

Milestone:

freeze results.

Do not add major methods after this point.

---

## Week 6 — Finalization

* rerun from clean environment
* verify results
* finalize plots/tables
* write methodology
* write numerical comparison
* write 13-bus analysis
* document limitations
* clean repository
* prepare presentation/demo

---

# 28. Repository Structure

Recommended:

```text
project/
│
├── data/
│   ├── raw/
│   │   ├── ieee4/
│   │   ├── ieee13/
│   │   ├── ieee37/
│   │   └── ieee69/
│   │
│   ├── reconstructed/
│   │   └── jang2023/
│   │       ├── ieee4/
│   │       ├── ieee13/
│   │       ├── ieee37/
│   │       ├── ieee37_quasiradial/
│   │       └── ieee69/
│   │
│   └── PROVENANCE.md
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

# 29. Provenance Requirements

For every reconstructed feeder record:

```text
Case name:
Original source:
Original filename:
Download date:
Original parameters retained:
Changes explicitly specified by Jang et al.:
Changes inferred by us:
Transformer modifications:
Balanced/unbalanced construction:
Known discrepancies:
Reference simulator:
```

Never overwrite raw feeder files.

---

# 30. Minimum Viable Scope

The project is already successful if we complete:

1. shared three-phase NR implementation,
2. finite-difference Jacobian validation,
3. IEEE 4 direct failure,
4. IEEE 4 SVD recovery,
5. IEEE 4 RRQR recovery,
6. IEEE 13 direct/SVD/RRQR study,
7. IEEE 37 direct/SVD/RRQR study,
8. OpenDSS cross-validation,
9. controlled IEEE-13 anomaly analysis.

Everything below this is secondary.

---

# 31. Stretch Goals

In order:

1. Tikhonov regularization
2. IEEE 37 quasi-radial
3. IEEE 69 reconstruction
4. IEEE 118 runtime scaling

---

# 32. Things to Drop If Time Is Limited

Do not let these endanger the core work:

* ML classifier
* IEEE 123-node feeder
* 8500-node feeder
* GPU implementation
* many additional numerical solvers
* unnecessary GUI work

The originally proposed lightweight ML pre-check should probably be omitted unless all numerical work is complete.

With only a few feeders, an ML classifier would likely learn the synthetic case-generation procedure rather than a useful general law.

---

# 33. Final Research Questions

## RQ1 — Robustness

How reliably do SVD-based Moore–Penrose pseudo-inverse, rank-revealing QR and Tikhonov regularization handle singular or severely ill-conditioned Newton–Raphson Jacobians?

## RQ2 — Conditioning

How are condition number, numerical rank and singular-value spectrum related to convergence and voltage error?

## RQ3 — IEEE 13 Anomaly

Which factors—loading, topology, transformer grounding, zero-sequence reference, numerical-rank threshold or regularization—best explain the comparatively elevated IEEE 13-node error?

## RQ4 — Computational Cost

What accuracy, convergence and runtime trade-offs exist among direct solving, SVD, RRQR and Tikhonov?

---

# 34. Current Conceptual Priority

The core sequence is:

```text
Direct NR baseline
        ↓
SVD / Moore–Penrose reproduction
        ↓
RRQR comparison
        ↓
IEEE 13 anomaly investigation
        ↓
Tikhonov if time allows
```

The project should remain primarily a **numerical analysis study**, not become a generic power-systems software project.

---

# 35. Expectations for Your Assistance

When helping from this point onward:

1. Do not automatically agree with our assumptions.
2. Flag numerical or power-system modelling errors immediately.
3. Check equations, dimensions, per-unit conversions and transformer conventions carefully.
4. Distinguish exact reproduction from reconstruction.
5. Prefer official IEEE, EPRI, MATPOWER, SciPy and primary literature sources.
6. Do not fabricate unavailable feeder values.
7. If information is missing from Jang et al., explicitly state that it is unspecified.
8. When proposing code, make it runnable and modular.
9. Validate Jacobians and matrix solvers numerically before using them for scientific conclusions.
10. Keep the project achievable for five undergraduate students in six weeks.
11. Do not suggest paid software as a required dependency.
12. Keep all experimental cases reproducible from source-controlled scripts.
13. Treat the IEEE-13 explanation as an open hypothesis-testing problem, not a predetermined result.
14. If a claim depends on current documentation or software behavior, verify it from the current authoritative source before relying on it.

---

# 36. Immediate Next-Step Assumption

Unless I explicitly ask for something else, assume the next implementation sequence is:

1. acquire and freeze the IEEE 4/13/37 raw feeder files,
2. create `PROVENANCE.md`,
3. define the normalized three-phase Python data model,
4. implement/test transformer Ybus stamping,
5. implement mismatch and analytical Jacobian,
6. verify Jacobian with finite differences,
7. get IEEE 4 classical NR running,
8. reproduce the singular Yg–Delta/no-secondary-load case,
9. integrate SVD MP-PI,
10. integrate RRQR,
11. only then move to IEEE 13.

When I ask follow-up questions, continue from this project state rather than restarting the planning process.
