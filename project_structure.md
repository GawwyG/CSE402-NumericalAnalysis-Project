> **Note:** this file is Member A's early-stage planning checklist and no
> longer reflects the repository's actual state (it substantially
> undersells what's done, and doesn't cover the IEEE-13/37 reconstructions,
> `src/diagnostics/`, or the RRQR/Tikhonov solvers). Kept for historical
> context. See [`README.md`](README.md) for the current, accurate map and
> status.

project/
│
├── src/
│   ├── model/
│   │   ├── __init__.py
│   │   ├── state.py            ⏳ done (Part 1) — bus/phase indexing, 
│   │   │                          NetworkState, rectangular (e,f) state vector
│   │   └── ybus.py             ⏳ done (Part 1) — line stamping, 
│   │                              Yg/Delta transformer stamping, dense Ybus builder
│   │
│   ├── powerflow/
│   │   ├── __init__.py
│   │   ├── mismatch.py         ⏳ Part 2 — F(x): ΔP, ΔQ per active bus-phase
│   │   ├── jacobian.py         ⏳ Part 2 — analytical J(x) = ∂F/∂(e,f)
│   │   └── newton.py           ⏳ Part 3 — shared NR loop, calls 
│   │                              solve_linear_step(J, rhs, method=...),
│   │                              convergence criteria, iteration logging
│   │
│   └── solvers/
│       ├── __init__.py
│       └── direct.py           ⏳ Part 3 — method="direct" via 
│                                   numpy.linalg.solve (never .inv())
│                                   (svd_pinv.py / rrqr.py / tikhonov.py
│                                    are Members B/C/D — not mine)
│
├── tests/
│   ├── __init__.py
│   └── test_jacobian.py        ⏳ Part 4 — finite-difference validation,
│                                   E_J = ||J_analytic - J_FD||_F / ||J_FD||_F
│
└── experiments/
    └── exp01_4bus.py           ⏳ Part 5 — IEEE 4-bus baseline:
                                    (a) normal case → should converge
                                    (b) Yg–Δ, no secondary load → should 
                                        reproduce the reported singularity



project/
├── data/                       ← Member E (raw feeders, provenance)
├── src/
│   ├── model/                  ← ME
│   ├── powerflow/               ← ME
│   ├── solvers/
│   │   ├── direct.py            ← ME
│   │   ├── svd_pinv.py          ← Member B
│   │   ├── rrqr.py              ← Member C
│   │   └── tikhonov.py          ← Member D
│   ├── validation/               ← Member E (OpenDSS)
│   └── diagnostics/               ← shared/Member E, consumes my logged metrics
├── experiments/
│   └── exp01_4bus.py            ← ME (others own exp02–exp05)
├── tests/
│   └── test_jacobian.py         ← ME
├── results/, figures/            ← Member E
└── README.md, requirements.txt   ← Member E