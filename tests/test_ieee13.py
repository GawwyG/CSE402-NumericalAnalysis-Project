"""Validation and regression tests for the modified IEEE 13-node reconstruction.

Per handoff.md section 22 ("Jacobian validation is mandatory... before
running the larger test feeders"), this is the hard gate for
experiments/exp02_13bus.py: no result from that module should be trusted
until test_jacobian_13bus_matches_finite_difference passes.
"""

from __future__ import annotations

import numpy as np

from experiments.exp02_13bus import build_13bus_system
from src.powerflow.jacobian import compute_jacobian
from src.powerflow.newton import newton_raphson
from tests.test_jacobian import compute_relative_frobenius_error, finite_difference_jacobian

E_J_TOLERANCE = 1e-6


def test_jacobian_13bus_matches_finite_difference():
    """Mandatory FD validation before trusting any IEEE-13 NR result."""
    state, Ybus = build_13bus_system()
    x0 = state.init_flat_start(v_mag=1.0)
    rng = np.random.default_rng(13)
    x_test = x0 + 0.01 * rng.standard_normal(x0.size)

    J_analytic = compute_jacobian(x_test, state, Ybus)
    J_fd = finite_difference_jacobian(x_test, state, Ybus, h=1e-6)
    E_J = compute_relative_frobenius_error(J_analytic, J_fd)

    assert E_J < E_J_TOLERANCE, (
        f"IEEE-13 analytical Jacobian disagrees with finite differences: "
        f"E_J={E_J:.3e} exceeds tolerance {E_J_TOLERANCE:.1e}."
    )


def test_13bus_system_has_expected_size_and_slack():
    """Sanity check on the reconstruction's topology before trusting solver results."""
    state, Ybus = build_13bus_system()

    # 13 physical buses (SourceBus + 12 downstream, after merging RG60->650
    # and 692->671) with the phase counts documented in exp02_13bus.py's
    # _active_bus_phases: SourceBus 3 + 650,632,670,671,680,633 (3 each) +
    # 645,646 (2 each) + 675 3 + 684 2 + 611,652 (1 each) + 634 3 = 35
    # bus-phases total, 3 of them (SourceBus) slack -> 32 non-slack.
    assert state.n_busphases == 35
    assert state.n_unknowns == 2 * 32  # 35 total - 3 slack phases
    assert Ybus.shape == (35, 35)

    slack_phases = [bp for bp in state.all_busphases() if bp.is_slack]
    assert len(slack_phases) == 3
    assert all(bp.bus_name == "SourceBus" for bp in slack_phases)


def test_direct_solver_fails_on_the_doubly_floating_reconstruction():
    """The direct solver must refuse this system: it is genuinely singular.

    Both T1 (Yg-Delta) and T2 (Delta-Delta) leave their secondary side with
    no ground reference and no other ground path is stamped anywhere in
    this reconstruction, so the flat-start Jacobian is singular to within
    machine precision (this is the paper's reproduction target, not a
    reconstruction defect -- see exp02_13bus.py's module docstring).
    """
    state, Ybus = build_13bus_system()
    x0 = state.init_flat_start(v_mag=1.0)

    J0 = compute_jacobian(x0, state, Ybus)
    sv0 = np.linalg.svd(J0, compute_uv=False)
    assert sv0[-1] < 1e-8 * sv0[0], "Expected the flat-start Jacobian to be (near-)singular."

    result = newton_raphson(
        state, Ybus, x0, method="direct", tol_F=1e-9, max_iter=10, compute_conditioning=False
    )
    assert result["converged"] is False


def test_svd_rrqr_and_tikhonov_all_converge_and_agree():
    """The three rank-revealing/regularized solvers should reach the same solution.

    Unlike the 4-bus floating case (where SVD and RRQR's minimum-norm
    choices diverged along the near-null direction by ~1e-5), this larger,
    genuinely-singular-by-construction 13-bus system was observed to have
    SVD and RRQR agree to ~1e-13 and Tikhonov (alpha=1e-8) agree to ~1e-8 --
    tight enough to assert as a regression, not just "did not crash".
    """
    state, Ybus = build_13bus_system()
    x0 = state.init_flat_start(v_mag=1.0)

    svd = newton_raphson(state, Ybus, x0, method="svd", tol_F=1e-9, max_iter=60, compute_conditioning=False)
    rrqr = newton_raphson(state, Ybus, x0, method="rrqr", tol_F=1e-9, max_iter=60, compute_conditioning=False)
    tikhonov = newton_raphson(
        state, Ybus, x0, method="tikhonov", solver_options={"alpha": 1e-8},
        tol_F=1e-9, max_iter=60, compute_conditioning=False,
    )

    assert svd["converged"] is True
    assert rrqr["converged"] is True
    assert tikhonov["converged"] is True
    np.testing.assert_allclose(svd["x"], rrqr["x"], rtol=1e-9, atol=1e-9)
    np.testing.assert_allclose(svd["x"], tikhonov["x"], rtol=1e-5, atol=1e-5)


def test_line_to_line_voltage_is_far_better_conditioned_than_phase_voltage():
    """Structural check for the floating common-mode phenomenon this system induces.

    The flat-start Jacobian's near-null direction should correspond mostly
    to a common-mode (equal shift on every phase) component: line-to-line
    voltage magnitudes should therefore vary far less across the converged
    solution than raw phase magnitudes do, matching the zero-sequence
    hypothesis in handoff.md section 7.
    """
    state, Ybus = build_13bus_system()
    x0 = state.init_flat_start(v_mag=1.0)
    result = newton_raphson(state, Ybus, x0, method="svd", tol_F=1e-9, max_iter=60, compute_conditioning=False)
    assert result["converged"] is True

    V = state.unpack(result["x"])
    phase_mags = [abs(v) for key, v in V.items() if key[0] != "SourceBus"]
    phase_spread = max(phase_mags) - min(phase_mags)

    line_line_mags = []
    for bus in {key[0] for key in V if key[0] != "SourceBus"}:
        for p1, p2 in (("a", "b"), ("b", "c"), ("c", "a")):
            if (bus, p1) in V and (bus, p2) in V:
                line_line_mags.append(abs(V[(bus, p1)] - V[(bus, p2)]))
    line_line_spread = max(line_line_mags) - min(line_line_mags)

    assert line_line_spread < 0.25 * phase_spread
