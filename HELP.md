# HELP.md — A from-scratch walkthrough of this project, no engineering background required

This document explains **every directory, every file, and every function**
in this repository, in an order that builds up understanding step by step.
It assumes you don't know electrical-engineering terms like "impedance" or
"three-phase power" — every such term is explained in plain language, with
an everyday analogy, the first time it's used.

If you just want the short version, read Part 1 and Part 2, then skim the
tables of contents in Part 3 and jump to whatever file you care about.

---

# Part 1 — The problem, explained with no assumed background

## 1.1 What is an electrical grid, in plain terms?

Think of an electrical grid like a **network of water pipes**. This
analogy will be used throughout, because the same math describes both:

| Electrical term | Water-pipe equivalent |
|---|---|
| Voltage | Water pressure |
| Current | Flow rate (how much water moves per second) |
| Power | Pressure × flow rate (the actual "useful work" delivered) |
| A "bus" (a node in the network) | A junction where pipes meet |
| A wire/line | A pipe |
| Impedance / resistance | How narrow or rough a pipe is — more resistance means you need more pressure to push the same flow through |
| A transformer | A pressure-changing pump station: it takes high pressure and converts it to low pressure (or vice versa), while conserving the total power delivered |
| A "load" | A tap somewhere drawing water out of the network |
| A "source" / "slack bus" | The water tower or pumping station feeding the whole network at a fixed, known pressure |

A power grid computes **power flow**: if you know how much water (power)
every tap (load) wants to draw, and how the pipes (lines) are connected,
what is the pressure (voltage) at every junction (bus), and how much flow
(current) moves through every pipe?

## 1.2 Why "three-phase"?

Real power grids don't send electricity down a single wire — they use
**three synchronized wires** (called phases **a**, **b**, and **c**) whose
pressure waves are offset from each other by exactly 1/3 of a cycle (120°),
like three pistons in an engine firing in a staggered rhythm so the engine
runs smoothly instead of jerking. This project represents every bus as
having up to three separate phase values (`a`, `b`, `c`), each with its own
voltage.

## 1.3 What is a "transformer connection," and why does it matter here?

A transformer is the pump station that changes pressure levels (e.g. from
a high-pressure trunk line down to the lower pressure that reaches your
house). In a three-phase system, a transformer's three windings can be
wired together in different patterns:

- **Grounded wye ("Yg")**: each of the three phases has its own private
  connection back to a shared reference point (like each of three parallel
  pipes having its own connection to the ground-level reservoir). This
  reference point makes the "average" or "common" water level of the three
  phases well-defined and fixed.
- **Delta ("Δ")** or **ungrounded wye**: the three phases are connected
  only to *each other* in a loop, with **no connection to any shared
  reference point**. Imagine three pipes connected in a triangle with no
  pipe going down to the reservoir at all — you can tell the *differences*
  in pressure between the three pipes (which is what actually matters for
  moving water between them), but there's no way to know their *absolute*
  pressure level relative to the ground. You could raise or lower all
  three pipes' pressure by the exact same amount and nothing about the
  flow between them would change.

**This is the entire subject of this project.** When a Delta-connected
transformer's low-pressure side has *no other* connection to a reference
point anywhere else in the network, that whole region of the network has
an undetermined "common" pressure level — mathematically, the equations
describing it have **more than one valid answer** (or, in the exactly
matched case, literally infinite valid answers along one direction).

## 1.4 How do you normally solve for the pressures/voltages in a network?

You can't solve the equations directly in one step, because the equations
relating voltage to power are **nonlinear** (power = voltage × current,
and current itself depends on voltage — so it's voltage multiplied by
something that depends on voltage, i.e. roughly "voltage squared" in
spirit). The standard method is called **Newton-Raphson (NR)**: start with
a rough guess, measure how wrong it is, use calculus to figure out the
*best small adjustment* to reduce the error, apply that adjustment, and
repeat until the error becomes tiny.

```
1. Guess a set of voltages.
2. Compute the "mismatch": how far off is calculated power vs. what
   consumers actually want (F(x), the error)?
3. If the error is small enough, stop — you're done.
4. Compute the "Jacobian" J: a table of "if I nudge this one voltage
   a tiny bit, how much does each error term change?" This tells you
   which direction to adjust.
5. Solve one system of linear equations, J · (adjustment) = −(error),
   to get the best adjustment.
6. Apply the adjustment to your guess, and go back to step 2.
```

This is a classic "successive approximation" technique — like tuning a
guitar string by ear: pluck it, hear how far off the pitch is, turn the
peg a calculated amount, pluck again, repeat until it's in tune.

## 1.5 Where does the singularity problem come in?

**Step 5 above — solving `J · (adjustment) = −(error)` — is where
everything in this project happens.** If part of the network has an
undetermined "common pressure level" (§1.3), then the Jacobian `J` becomes
what's called **singular**: informally, it's a system of equations where
one direction has been left completely unconstrained, so many different
"adjustments" all satisfy the equation equally well — there is no single
correct answer to pick out.

Even *without* being perfectly singular, a Jacobian can be
**ill-conditioned**: technically almost-but-not-quite singular, meaning
tiny rounding errors in the computer's arithmetic get wildly amplified
into huge, meaningless errors in the answer. A standard method for solving
`J · x = b` (called direct solving, or LU decomposition) only complains
when the matrix is *exactly* singular down to the last decimal digit —
which almost never happens in floating-point arithmetic. So it will
silently hand back a "solution" that looks fine (it even satisfies the
equation closely!) but is actually numerical garbage, without ever raising
an error. That's the trap this whole project studies.

## 1.6 The four fix strategies compared in this project

Since a classic direct solve can fail silently, this project implements
and compares four different ways to solve `J · Δx = −F` (step 5 above)
when `J` might be singular or nearly so:

1. **Direct** (`direct.py`) — the classic method, but with an explicit
   alarm bell: if the matrix looks dangerously close to singular, refuse
   to answer rather than silently returning garbage.
2. **SVD / "Moore-Penrose pseudo-inverse"** (`svd_pinv.py`) — decompose
   the matrix into its fundamental "directions of sensitivity," throw away
   the directions that are so close to zero they're meaningless, and
   answer using only the directions that are actually well-determined.
   This is the fix proposed by the original research paper this project
   reproduces.
3. **RRQR — "rank-revealing QR"** (`rrqr.py`) — a different (but related)
   mathematical technique for reaching almost the same kind of answer as
   SVD, sometimes faster, via a different factorization of the matrix.
4. **Tikhonov regularization** (`tikhonov.py`) — instead of throwing away
   the bad directions, gently "nudge" the whole problem to make it less
   singular in the first place (by adding a small penalty against large
   answers), then solve the nudged version.

**The project's central finding**: none of these four is uniformly best.
On one test network (IEEE-13, described below), SVD and RRQR fail to
converge at all at realistic load — only Tikhonov works. On a *different*
test network (IEEE-37), the exact opposite happens: SVD and RRQR work fine
and Tikhonov fails. Which fix works best depends on the specific shape of
the singularity, not just "is it singular or not."

## 1.7 What are the "IEEE test feeders"?

To test all this, you need example electrical networks. Rather than
invent fake ones, this project uses **standard, publicly published
example networks** that the power-systems research community has used for
decades — nicknamed by their number of buses (junctions): a small 4-bus
example, and the more realistic IEEE **13-bus**, **37-bus**, and **69-bus**
test feeders (a "feeder" is just a real-world term for a distribution
network branching out from one source, like the plumbing in a building
branching out from the water main). A 118-bus network is also used, but
only to measure *how fast* the four solvers run as the network gets
bigger — not to study singularity.

---

# Part 2 — The big-picture architecture

**There is exactly one Newton-Raphson loop in this whole codebase.**
Every comparison between direct/SVD/RRQR/Tikhonov runs through the *same*
outer loop — same starting guess, same error function, same Jacobian, same
stopping rule. Only **step 5** (the single linear solve per iteration)
changes. This is deliberate: if the loop itself were different for each
method, you could never tell whether a difference in outcome came from the
nonlinear algorithm or from the linear-solve choice. By holding everything
else fixed, any difference is attributable purely to which of the four
"calculators" was used for that one step.

```
                    official public feeder data (never modified)
                    src/model/ieee{13,37,69}_data.py
                                │
                                ▼   apply the paper's stated changes
                    experiments/expNN_*.py :: build_*_system()
                                │
                    ┌───────────┴────────────┐
                    ▼                        ▼
         NetworkState                    Ybus (a big grid
      (src/model/state.py)         of numbers describing
      "who are the unknown         how every bus connects
       voltages?"                  to every other bus)
                    │              (src/model/ybus.py)
                    └───────────┬────────────┘
                                ▼
              src/powerflow/newton.py :: newton_raphson()
              (the ONE shared iterative loop, described in §1.4)
                                │
                     each iteration computes:
                     F(x)  ← src/powerflow/mismatch.py   (the error)
                     J(x)  ← src/powerflow/jacobian.py   (the sensitivity table)
                                │
                     then solves J·Δx = −F by calling
                     EXACTLY ONE of these four interchangeable modules:
                                │
        ┌───────────┬───────────┼───────────┬────────────┐
        ▼           ▼           ▼            ▼
  direct.py     svd_pinv.py   rrqr.py    tikhonov.py
  (Part 3.3 explains each of these in detail)
                                │
                                ▼
                result = {converged, x, iterations, history, fail_reason}
                                │
              ┌─────────────────┼──────────────────┐
              ▼                 ▼                   ▼
   src/diagnostics/    results/*.csv (temp,    OpenDSS cross-check
   sequence_components  gitignored)            (independent double-
   .py — extra analysis                        check using a totally
                                                separate software tool)
```

---

# Part 3 — File-by-file, function-by-function walkthrough

Read this part in order — each section builds on the previous ones.

## 3.1 `src/model/` — "what does the network look like, as data?"

This is where the electrical network gets turned into numbers a computer
can work with.

### `src/model/state.py` — who are the unknowns?

Every voltage is stored as **two plain real numbers** instead of one
"complex" number with a magnitude and angle. Specifically, for a voltage
`V`, this project stores `e = the real part of V` and `f = the imaginary
part of V` (this is called "rectangular coordinates," as opposed to
"polar coordinates" which would store a magnitude and an angle instead).
The docstring explains why: it makes the sensitivity-table math (the
Jacobian, §3.2) come out as simple multiplication and addition, with no
trigonometry, and it avoids awkward "the angle wrapped around past 360°"
bugs.

- **`PHASES = ("a", "b", "c")`** — a constant tuple naming the three
  phases (§1.2).
- **`class BusPhase`** — describes ONE phase at ONE bus/junction: its
  name, which phase letter it is, whether it's "active" (physically
  present — some junctions only have 1 or 2 of the 3 phases wired to
  them), whether it's the fixed-voltage source ("slack" — the water
  tower in §1.1's analogy) or a normal consuming junction, and if it's
  a consumer, how much power (`P_spec`, `Q_spec`) it draws.
  - `P_spec`/`Q_spec` follow the "load convention": a **positive** number
    means power is being *consumed* (drawn out), like a household's
    metered usage.
- **`class NetworkState`** — the main bookkeeping object. It keeps two
  lookup tables:
  - `busphase_index`: maps every *active* bus-phase (including the fixed
    source) to a row number in the big grid of numbers (`Ybus`, described
    next).
  - `unknown_index`: maps every *non-source* bus-phase to a position in
    the list of unknowns we're actually solving for (the source's voltage
    is already known, so it's not an "unknown").
  - **`add_bus_phase(bp)`** — registers one `BusPhase` into the network.
    Raises an error if you try to add the exact same bus-phase twice.
  - **`finalize()`** — call this once after adding every bus-phase. It
    locks in the final list of unknowns and computes `n_unknowns` (how
    many numbers we're solving for — each active non-source phase
    contributes 2, for its `e` and `f`).
  - **`all_busphases()`** / **`non_slack_busphases()`** — return the list
    of all registered bus-phases, or just the ones we're solving for
    (excluding the fixed source).
  - **`get(bus_name, phase)`** — look up one specific `BusPhase` object by
    name.
  - **`is_active(bus_name, phase)`** — quick true/false check for whether
    a given bus-phase exists in this network at all.
  - **`init_flat_start(v_mag=1.0)`** — builds the very first guess to feed
    into Newton-Raphson: every consuming phase starts at the same voltage
    magnitude (default 1.0, in "per-unit" terms — meaning "1.0 = the
    normal, expected voltage," a common convention in power engineering so
    numbers stay near 1 regardless of whether the real-world voltage is
    120V or 115,000V), spread across the three phases at their expected
    120°-apart angles. This is called a "flat start" because every
    consuming bus starts flat/identical, with no information yet about
    how the actual network will pull each voltage away from that.
  - **`unpack(x)`** — takes the plain list of numbers (`e`, `f` pairs) and
    turns it back into a friendly dictionary of `{(bus, phase): complex
    voltage}`, filling in the known source voltage too.
  - **`pack(V)`** — the reverse: takes that friendly dictionary and
    flattens it back into the plain list of numbers.

### `src/model/ybus.py` — how is everything connected?

`Ybus` ("Y-bus," short for "admittance matrix" — "admittance" is the
mathematical opposite of resistance: how *easily* current flows, rather
than how much it's resisted) is a big grid of numbers where entry `(i, j)`
describes how strongly bus-phase `i` and bus-phase `j` are electrically
coupled. This file builds that grid up piece by piece.

- **`C_DELTA`**, **`C_WYE`** — two small 3×3 "connection pattern" grids of
  numbers representing the two transformer wiring styles from §1.3.
  `C_WYE` is simply "each phase stands alone" (the identity — no cross-
  coupling). `C_DELTA` represents the triangle-loop wiring, and — this is
  the mathematical heart of the whole project — **`C_DELTA`'s rows and
  columns both add up to zero**. That single fact is *why* a Delta
  connection creates the undetermined "common pressure level" from §1.3:
  it means "shift all three phases by the same amount" produces exactly
  zero effect when multiplied through this pattern. `C_DELTA` is scaled
  by `1/√3` — a correction found necessary during development, because
  without it a Delta-connected transformer came out with 3× too little
  resistance compared to an otherwise-identical Yg-connected one, which
  is physically impossible (the *type* of connection shouldn't change
  the transformer's normal, balanced behavior — only its handling of the
  "common" direction).
- **`stamp_line_series_admittance(Ybus, bus_i, bus_j, Yprim, phases_i,
  phases_j)`** — adds one wire/pipe connecting two junctions into the big
  grid. `Yprim` is the *inverse of the wire's resistance matrix* (matrix
  inverse, not just "1 divided by each number" — because real wires
  running side-by-side interact with each other a little, which the
  off-diagonal parts of the matrix capture, similar to how two adjacent
  water pipes can slightly affect each other through pressure/vibration).
  A comment in the file documents a bug that was caught and fixed here
  early on: an earlier version put this cross-wire interaction on the
  wrong diagonal entry, silently erasing it — this would have corrupted
  every result on any network with real multi-wire interaction (which is
  most of them).
- **`stamp_shunt_admittance(Ybus, bus, phase, y_shunt)`** — adds a direct
  connection from one single phase straight down to the shared ground
  reference (used, for example, to model a small always-on leak-to-ground
  admittance, or to experiment with deliberately "fixing" a floating
  transformer by grounding it).
- **`_winding_connection_matrix(conn)`** — given a connection-type name
  string (`"yg"`, `"delta"`, or `"y"`), returns the matching pattern grid
  (`C_WYE` or `C_DELTA`). Ungrounded wye (`"y"`) deliberately isn't
  implemented — it `raise`s an error explaining that modeling a genuinely
  floating (not grounded, but also not delta-looped) neutral point
  correctly needs more machinery than this simplified model has, and it's
  safer to refuse than to silently give a wrong answer.
- **`stamp_transformer(Ybus, bus_p, conn_p, bus_s, conn_s, r_pu, x_pu,
  ground_primary_admittance=0.0, ground_secondary_admittance=0.0)`** — adds
  one transformer (pump station) connecting a "primary" (high-pressure)
  side to a "secondary" (low-pressure) side, using the connection-pattern
  grids above and the transformer's resistance (`r_pu`) and reactance
  (`x_pu` — a related electrical-resistance-like quantity that comes from
  effects specific to alternating current). This is the single function
  where the entire "floating Delta transformer" phenomenon studied by this
  project actually gets created in the model.
- **`build_dense_ybus(Ybus_dict, state)`** — the previous functions build
  up `Ybus` as a memory-efficient dictionary (only storing the
  connections that actually exist). This function converts that into an
  ordinary, complete grid of numbers (a "dense matrix") in the exact row/
  column order `NetworkState` expects, ready for the math in Part 3.2.

### `src/model/ieee13_data.py`, `ieee37_data.py`, `ieee69_data.py`

These three files contain **only real, official, published numbers** —
line resistances, load amounts, transformer specs — copied verbatim from
the official public sources (a widely-used industry reference and a
published research database — the exact web addresses and retrieval
dates are recorded in `data/provenance.yml`, §3.8). **No paper-specific
modifications live in these three files** — they are pure source data.
The actual modifications this project's research paper asks for (like
changing a transformer's connection style) are applied afterward, in the
matching `experiments/expNN_*.py` file. Keeping "real official data" and
"our modifications" strictly separate like this makes it possible to
trace every single number in the project back to either an official
public source or a documented, deliberate choice — never something
invented and forgotten about.

- `ieee13_data.py` — the 13-bus feeder's line resistance tables
  (`LINECODES`), the list of wire connections (`OFFICIAL_LINES`), the
  official list of loads (`OFFICIAL_LOADS`), and one helper function,
  **`line_impedance_ohm(line)`**, which looks up a line's resistance
  table and multiplies it by that specific wire's length to get its
  actual real-world resistance in ohms.
- `ieee37_data.py` — the same idea for the 37-bus feeder. Notably, every
  single load in this particular feeder is Delta-connected (§1.3) rather
  than the simpler "each phase stands alone" style.
- `ieee69_data.py` — the same idea for the 69-bus feeder, whose original
  source data (`BUS_LOADS_MW`, `BRANCHES_OHM`) came from a different kind
  of source (a general "balanced" single-number-per-phase network model,
  common in research on the transmission-level, not the distribution-
  level, grid) that had to be adapted to this project's three-phase
  representation. `TRANSFORMER_LOCATIONS` records which three of its
  wires get replaced by transformers, per this project's research paper.

## 3.2 `src/powerflow/` — the physics equations

### `src/powerflow/mismatch.py` — "how wrong is the current guess?"

- **`compute_mismatch(x, state, Ybus) → F`** — this is step 2 of the loop
  in §1.4. Given the current voltage guess `x`, it works out how much
  power is actually flowing at every junction (using basic
  power = voltage × current arithmetic) and subtracts what each consumer
  actually wants. The result, `F`, is a list of "error" numbers — one pair
  (real-power error, reactive-power error) per unknown bus-phase — that
  should shrink toward zero as the guess improves. ("Reactive power" is a
  quirk of alternating-current electricity — a second, related kind of
  power flow that has to balance separately from the "useful" real power;
  you don't need to understand it deeply to follow the rest of this
  document, just know that every bus-phase produces *two* error numbers,
  not one.)

### `src/powerflow/jacobian.py` — "which direction should I nudge my guess?"

- **`compute_jacobian(x, state, Ybus) → J`** — this is step 4 of the loop.
  It works out, by calculus, exactly how much each of the error numbers
  in `F` would change if you nudged any *one* unknown voltage component
  by a tiny amount — for every possible pairing of "which error" and
  "which unknown." The result is a big grid of these sensitivities. This
  grid, `J`, is exactly the matrix that becomes singular or
  ill-conditioned when part of the network is floating (§1.5) — because
  if nudging a whole floating region's common voltage level produces
  *zero* change in every error term, that's an entire row/column
  direction of `J` that's essentially zero, and singular matrices are
  matrices with a zero-effect direction like that.
  This file's docstring works through the exact calculus derivation
  and notes that the formula is checked against a totally independent,
  much simpler technique (numerically wiggling each unknown by a tiny
  amount and measuring the actual change directly, called a "finite
  difference check" — see §3.7's `test_jacobian.py`) before ever being
  trusted for a real result.

### `src/powerflow/newton.py` — the loop itself, and the "pick a calculator" dispatcher

- **`solve_linear_step(J, rhs, method="direct", options=None)`** — this
  is the one dispatcher function mentioned in Part 2. Given the
  sensitivity grid `J` and the target `rhs` (the negative of the current
  error), it calls exactly one of the four solver modules based on the
  `method` string (`"direct"`, `"svd"`, `"rrqr"`, or `"tikhonov"`) and
  returns whatever that solver computes. This is the *only* place in the
  whole codebase where the choice of solver actually branches.
- **`_numerical_rank(J, singular_values)`** — a small internal helper used
  only for the loop's own optional diagnostic logging (not the actual
  solve): estimates how many of `J`'s "directions of sensitivity" are
  meaningfully nonzero, using a standard textbook threshold rule.
- **`newton_raphson(state, Ybus, x0, method="direct", solver_options=None,
  tol_F=1e-8, max_iter=30, compute_conditioning=True)`** — the complete
  loop from §1.4, spelled out:
  1. Compute the error `F` (`compute_mismatch`).
  2. If the error is small enough (below `tol_F`), stop successfully.
  3. Compute the sensitivity grid `J` (`compute_jacobian`).
  4. (Optional, if `compute_conditioning=True`) do some extra diagnostic
     math purely for reporting — how close to singular is `J` right now?
     This costs real computer time, so it's turned off when timing how
     fast a solver runs.
  5. Call `solve_linear_step` to get the adjustment.
  6. If the solver failed or the adjustment contains a nonsensical value
     (like "infinity"), stop and report failure.
  7. Apply the adjustment to the guess, log everything about this
     iteration into a running `history` list, and go back to step 1
     (unless we've also blown up to an absurdly large voltage, or hit
     `max_iter`, in which case stop and report failure).
  Returns a dictionary: `converged` (true/false), `x` (the final voltage
  guess), `iterations` (how many loops it took), `history` (the full
  per-iteration log — extremely useful for later plotting/analysis), and
  `fail_reason` (a human-readable explanation if it didn't converge).

## 3.3 `src/solvers/` — the four interchangeable "calculators" for step 5

Every one of these four files defines exactly one function with the same
overall shape: take in the sensitivity grid and target, hand back
`(adjustment_or_None, diagnostics_dictionary)`.

### `src/solvers/direct.py` — the classic method, with an alarm bell added

- **`COND_NUMBER_FAIL_THRESHOLD = 1e12`** — a chosen cutoff number (a
  "condition number" over one trillion is treated as "too risky to
  trust," explained below).
- **`solve_direct(J, rhs, cond_fail_threshold=COND_NUMBER_FAIL_THRESHOLD)`**
  — uses the standard, classic linear-solve routine (`numpy.linalg.solve`,
  which internally does something called LU decomposition — a systematic
  elimination method, similar to how you'd manually solve simultaneous
  equations by substitution, just done efficiently and in the right
  order). *Before* trusting the answer, it separately computes the
  matrix's **condition number** (a single number summarizing "how close
  to singular is this, on a scale where 1 is perfectly well-behaved and
  bigger numbers mean progressively more dangerous"). If that number
  exceeds the threshold, the function throws the answer away and reports
  failure — **even though the classic solve routine itself didn't
  complain**. This distinguishes two different failure situations that
  must never be confused with each other: `"exact_singular"` (the classic
  routine itself detected a hard zero and refused outright) versus
  `"ill_conditioned"` (the routine happily computed *something*, but this
  project's own added safety check judged the answer untrustworthy).

### `src/solvers/svd_pinv.py` — Singular Value Decomposition / "Moore-Penrose pseudo-inverse"

- **`_failure_diagnostics(start_time, message)`** — a small internal
  helper that builds a consistent "here's why it failed" report, reused
  by every early-exit path in the main function below.
- **`solve_svd_pinv(J, rhs, *, rtol=None, atol=0.0)`** — the star of the
  base research paper. **SVD** (Singular Value Decomposition) is a way of
  taking any grid of numbers and re-expressing it as a combination of
  independent "directions," each with its own "strength" number (called a
  singular value). A **large** strength means that direction is
  well-determined and trustworthy; a strength near **zero** means that
  direction is the undetermined "floating" one from §1.3/§1.5. This
  function:
  1. Computes the SVD (all the directions and their strengths).
  2. Picks a cutoff threshold `τ` (either supplied, or a sensible
     automatic default based on the size of the numbers involved).
  3. **Keeps** every direction whose strength is above `τ`, and
     **completely ignores** ("truncates") every direction below it — as
     if that undetermined direction simply didn't exist.
  4. Builds the answer using only the kept directions. In every ignored
     direction, this specific method always picks the smallest possible
     adjustment (mathematically, the "minimum-norm" answer) — a
     principled, if arbitrary, way of resolving "many answers are
     equally valid here, so just pick the smallest one."
  This function deliberately does the SVD math out in the open (rather
  than calling a single built-in "just give me the answer" library
  function) specifically so every one of these choices is visible and
  gets reported back in the `diagnostics` dictionary — how many
  directions got kept vs. thrown away, what the cutoff was, etc.

### `src/solvers/rrqr.py` — Rank-Revealing QR

- **`_failure_diagnostics(start_time, message)`** — same idea as above,
  a shared "why did this fail" report builder.
- **`solve_rrqr(J, rhs, *, rtol=None, atol=0.0)`** — a different
  mathematical technique (QR factorization with column reordering, plus a
  more advanced follow-up step) that reaches a very similar *kind* of
  answer to SVD — separate out the well-determined directions from the
  undetermined ones — via a different, sometimes cheaper, route. The
  function explicitly does two things:
  1. Runs a "pivoted" version of QR factorization purely to figure out
     *how many* directions are well-determined (the "rank") and in what
     order the original columns mattered most, entirely for reporting —
     this step doesn't produce the actual answer.
  2. Uses a specific, more sophisticated LAPACK routine (`GELSY` — LAPACK
     is a long-standing, industry-standard library of exactly this kind
     of numerical-linear-algebra routine) to actually compute the answer.
     The file's docstring is explicit that a *naive* QR-based solve (plain
     substitution, without this extra sophistication) would fail outright
     on a genuinely singular matrix, the same way the classic direct
     solve does — so this extra step is not optional polish, it's
     required for RRQR to work at all here.
  Reports rank, pivot order, and the smallest-kept internal value, mostly
  mirroring what `svd_pinv.py` reports, so the two can be directly
  compared side by side in the experiments.

### `src/solvers/tikhonov.py` — regularization (nudge the problem, don't ignore any of it)

- **`_failure_diagnostics(start_time, message)`** — same shared-report
  pattern again.
- **`solve_tikhonov(J, rhs, *, alpha=None, lam=None, sigma_max=None)`** —
  instead of throwing away the undetermined direction(s) like SVD/RRQR
  do, this method adds a small artificial "penalty for large answers" to
  the whole problem before solving it, which has the effect of gently
  pulling the undetermined direction toward zero instead of leaving it
  truly unconstrained (rather than "ignore this direction entirely," it's
  more like "prefer the smallest possible answer in every direction,
  a little bit, everywhere" — which happens to resolve the ambiguous
  direction too, as a side effect). The penalty strength is called
  `lambda` (`λ`), and it's calculated from a simpler dial called `alpha`
  (`α`) scaled by the size of the biggest well-determined direction in
  `J`, so the same `alpha` value has comparable "gentleness" regardless
  of how large or small the specific network's numbers happen to be.
  **Crucially, this function does not take the mathematically "obvious"
  shortcut** of directly multiplying `J` by itself to build the penalized
  problem — the docstring explains that shortcut would *square* the
  original ill-conditioning, making a bad situation catastrophically
  worse. Instead it solves a cleverly restructured ("augmented") version
  of the problem that reaches the same answer without ever creating that
  dangerous intermediate.

## 3.4 `src/diagnostics/sequence_components.py` — extra analysis tools

- **`abc_to_seq(Va, Vb, Vc)`** — a standard, century-old technique
  (called the "symmetrical components" or "Fortescue" transform) for
  re-expressing three phase voltages as three different numbers that are
  often more insightful:
  - `V0` ("zero-sequence") — exactly the **common/average** level shared
    by all three phases. This is precisely the quantity that becomes
    undetermined by a floating Delta connection (§1.3) — so this number
    is the key diagnostic tool for studying that phenomenon directly,
    rather than just noticing indirectly that the math misbehaves.
  - `V1` ("positive-sequence") — the "normal," balanced, properly-rotating
    part of the three voltages (what you'd see in a perfectly healthy,
    evenly-loaded system).
  - `V2` ("negative-sequence") — a measure of how *unevenly* the three
    phases are loaded relative to each other (imbalance).
- **`seq_to_abc(V0, V1, V2)`** — the exact reverse conversion, included
  mainly so the round-trip can be tested for correctness.
- **`bus_sequence_components(V, bus)`** — looks up one specific bus's
  three phase voltages from a voltage dictionary and runs `abc_to_seq` on
  them; returns `None` if that bus doesn't have all three phases present
  (a lopsided 1- or 2-phase junction has no meaningful "sequence"
  breakdown).
- **`sequence_components_by_bus(V)`** — runs the above for every
  bus in a voltage dictionary that has all three phases, returning a
  dictionary of results (silently skipping any bus that doesn't
  qualify).
- **`line_to_line_magnitudes(V, bus)`** — computes the *difference* in
  voltage between each pair of phases at one bus (a→b, b→c, c→a). This
  matters a lot in this project: even when the "common" level (`V0`) is
  undetermined and different solvers disagree wildly about its exact
  value, the *differences between phases* often stay well-determined and
  physically meaningful regardless — so this function is used throughout
  the cross-validation work (§3.5) as a fairer way to compare two
  different solvers' answers.

## 3.5 `src/validation/` — double-checking against a completely independent tool

Everything above is this project's own, from-scratch implementation. To
make sure it's actually correct (not just internally consistent with its
own possible bugs), results are cross-checked against **OpenDSS**, a
well-established, independently-written power-flow simulation tool used
throughout the power-systems industry.

### `src/validation/opendss.py`

- **`class OpenDSSRunResult`** — a small container: did OpenDSS's solve
  converge, how many iterations did it take, and what voltages did it
  find.
- **`compile_and_solve(dss_file, extra_commands=None, antifloat=None)`**
  — loads a specific network-description file (written in OpenDSS's own
  scripting language, ending in `.dss`), optionally tweaks something
  about it first (`extra_commands`, e.g. "turn a specific load's power to
  zero" — used to reproduce this project's own "Case A vs Case B"
  variants inside OpenDSS too), solves it, and reads back the resulting
  voltages. A code comment explains a subtle real bug this uncovered:
  OpenDSS's `compile` command has the side effect of silently changing
  the *entire Python process's* working directory to wherever that file
  lives — so this function carefully remembers the original directory at
  import time and always resets it back afterward, to avoid one call's
  side effect corrupting the next call.
- **`_export_bus_phase_voltages()`** — reads every bus's solved voltage
  out of OpenDSS's internal state and reformats it into this project's
  own shared `{bus, phase, V_real, V_imag, V_mag, V_angle}` table format,
  so it can be directly compared against this project's own results.
- **`export_csv(result, out_path)`** — writes an `OpenDSSRunResult`'s
  voltage table out to a spreadsheet-style `.csv` file on disk.
- The bottom `if __name__ == "__main__":` block, when this file is run
  directly, solves the 4-bus network's two cases (loaded/floating
  secondary) through OpenDSS and saves the results.

### `src/validation/crosscheck.py`

- **`run_nr_case(load_on_secondary)`** — runs this project's *own*
  4-bus solver (using the classic direct method) and returns whether it
  converged, the worst condition number seen along the way, and the
  resulting voltages if it succeeded. Deliberately does **not** treat a
  failure-to-converge as an error — for the deliberately-singular case,
  failing to converge with the direct method is the *expected, correct*
  outcome being studied, not a bug.
- **`compare_case(label, load_on_secondary, dss_extra_commands=None)`** —
  runs both this project's own solver and OpenDSS on the same network,
  and either prints a bus-by-bus voltage comparison table with pass/fail
  tolerances (for the case that's supposed to succeed), or — for the
  deliberately-singular case where this project's own solver is expected
  to fail — prints a qualitative note about what OpenDSS did instead
  (interestingly, OpenDSS often *does* manage to converge on the same
  singular network, because OpenDSS has its own small built-in
  "anti-float" safety admittance that quietly regularizes away exactly
  the kind of floating reference this project studies — see the next
  file). Returns `True`/`False`/`None` depending on whether a real
  pass/fail comparison was even possible.
- The bottom `if __name__ == "__main__":` block runs both the healthy and
  singular 4-bus cases when this file is executed directly.

### `src/validation/antifloat_study.py`

OpenDSS has a built-in per-transformer setting called `PPM_Antifloat`: a
tiny, automatic "leak to ground" admittance it quietly adds to every
transformer winding, specifically to prevent its own solver from choking
on exactly the kind of floating-reference situation this project studies.
This file investigates that setting directly.

- **`SETTINGS_TO_TEST`** — three specific values to try: OpenDSS's normal
  default, explicitly disabled (`=0`), and deliberately increased
  (`=100`), to see how much this hidden safety net is actually doing.
- **`run_sweep()`** — runs the deliberately-singular 4-bus case through
  OpenDSS three times, once per setting above, printing whether it
  converged each time and saving each run's voltages to its own `.csv`
  file. If OpenDSS only converges with the anti-float admittance enabled,
  that's strong evidence it's quietly regularizing away the very
  singularity this project studies (rather than "really" solving the
  singular problem the way this project's own SVD/RRQR/Tikhonov methods
  do) — an important nuance for interpreting any OpenDSS comparison.

## 3.6 `experiments/` — the runnable scripts that tie everything together

Every file here is meant to be run directly (`python experiments/whatever.py`)
and prints a readable report to the screen. This is where a specific test
network gets built (using `src/model/`), solved (using `src/powerflow/`
and `src/solvers/`), and reported on.

### `exp01_4bus.py` — the small 4-bus starter network

- **`build_4bus_system(load_on_secondary)`** — builds a small,
  hand-designed 4-bus network: a fixed source, one ordinary wire, one
  Yg-to-Delta transformer (the paper-specified singularity-inducing
  connection style, §1.3), and another ordinary wire. The
  `load_on_secondary` flag switches between:
  - **Case A** (`True`): the Delta side has real consumers drawing power
    → the network behaves normally.
  - **Case B** (`False`): the Delta side has *zero* load → reproduces
    the exact "floating reference, no ground anywhere" failure case the
    base research paper studies.
- **`SINGULARITY_KAPPA_THRESHOLD = 1e10`** — a project-chosen cutoff:
  above this condition number, the run is flagged as "severe
  ill-conditioning observed" in the printed report, independent of
  whether Newton-Raphson technically reported "converged."
- **`run_case(label, load_on_secondary)`** — builds the network, runs the
  classic direct solver on it, and prints a detailed per-iteration table
  (error size, condition number, adjustment size, etc.), plus the final
  voltages if it converged. This is the main "show me what's actually
  happening, iteration by iteration" report for the 4-bus network.
- The bottom block runs both Case A and Case B and prints a final summary
  comparing them.

### `exp02_13bus.py` — the 13-bus feeder

- A long list of module-level constants (`S_BASE_MVA`, `T1_R_PU`,
  `T2_X_PU`, `IMBALANCE_PHASE_MULTIPLIER`, etc.) recording every specific
  number this reconstruction uses, each with a comment explaining whether
  it's an official published value or a documented project choice.
- **`_accumulate_loads()`** — converts the official published loads
  (§3.1) into the "per-phase, per-unit" numbers this project's math
  actually uses. This is the exact function where a real, serious bug
  was found and fixed during development (see §4 below) — it's worth
  reading closely if you're ever adding a new network.
- **`_active_bus_phases()`** — figures out, from the list of wires,
  exactly which of the three phases physically exist at each junction
  (some junctions in this feeder only have 1 or 2 phases wired to them).
- **`build_13bus_system(load_scale=1.0, imbalance=0.0, *,
  t1_secondary_conn="delta", t2_primary_conn="delta",
  t2_secondary_conn="delta")`** — assembles the complete 13-bus network:
  registers every bus-phase, stamps every wire and both transformers into
  `Ybus`. The optional parameters let later experiments (§ below) dial the
  overall load level up/down, introduce a controlled amount of imbalance
  between the three phases, or swap either transformer's connection style
  (e.g. to see what happens if you "fix" the floating reference by
  grounding it) — all without touching or duplicating this core function.
- **`run_case(label, method, *, load_scale=1.0, solver_options=None)`** —
  the same style of "build it, solve it, print a detailed report" runner
  as the 4-bus version, generalized to work with any of the four solvers.
- The bottom block runs all four solvers once on the standard (nominal)
  13-bus network and prints each one's report.

### `exp02b_13bus_opendss_crosscheck.py` — checking the 13-bus result against OpenDSS

- **`solve_opendss()`** — compiles and solves a matching OpenDSS
  description of the same (paper-modified) 13-bus network, returning its
  voltages in this project's own shared dictionary format.
- **`solve_python()`** — runs this project's own 13-bus solver (using
  Tikhonov, since that's the one that reliably converges on this
  particular network — see §4) and returns its voltages the same way.
- **`compare()`** — runs both, then for a chosen list of buses compares
  their **line-to-line** voltage differences (not raw phase voltages —
  see §3.4's explanation of why that's the fairer comparison here),
  prints a table of relative errors, and returns `(median_error,
  max_error)` as plain numbers so other scripts (like the figure
  generator in `report/`) can use them directly.

### `exp03_37bus.py` — the 37-bus feeder

Very similar shape to the 13-bus file, with these notable differences:

- **`QUASI_RADIAL_EXTRA_CONNECTIONS`**, **`QUASI_RADIAL_Z_OHM_PER_KM`**,
  **`QUASI_RADIAL_ASSUMED_LENGTH_KM`** — constants supporting an optional
  "quasi-radial" variant of this network (the base research paper's own
  stretch-goal extension), which adds three extra wires forming closed
  loops in what's normally a simple, tree-shaped (non-looping) network.
- **`build_37bus_system(load_scale=1.0, *, xfm1_xhl_percent=...,
  quasi_radial=False)`** — the equivalent of `build_13bus_system`, with
  an added `quasi_radial` flag that, when true, adds those three extra
  wires **programmatically** (computed on the fly, from the same source
  data) rather than maintaining an entire second, separately-typed copy
  of the network — a deliberate design choice to avoid two copies quietly
  drifting out of sync with each other over time.
- **`run_case(...)`** — same idea as the 13-bus version's function of the
  same name.

### `exp03b_37bus_opendss_crosscheck.py` / `exp03c_37bus_quasiradial_opendss_crosscheck.py`

Same three-function shape (`solve_opendss`, `solve_python`, `compare`) as
the 13-bus crosscheck, applied to the plain 37-bus network and to its
quasi-radial variant respectively.

### `exp04_69bus.py` — the 69-bus feeder

- **`_bus_name(i)`** — a tiny helper converting a plain bus number (this
  feeder's original source data numbers its buses 1 through 69) into this
  project's standard `"BUSn"` naming style.
- **`_regular_branches()`** — returns every wire from the official source
  data **except** the three that this project's research paper says
  should be replaced by transformers instead.
- **`build_69bus_system(load_scale=1.0)`** — assembles the 69-bus
  network: registers all 69 buses (this feeder's original source data
  represents it as a simpler, single-signal-per-phase style network,
  so this project treats it as perfectly balanced across all three
  phases — every phase gets an identical copy of the same number), stamps
  every ordinary wire, then stamps the three research-paper-specified
  transformers in place of the three wires they replace.
- **`run_case(...)`** — same "build, solve, report" pattern as before.

### `exp04b_69bus_opendss_crosscheck.py`

Same `solve_opendss` / `solve_python` / `compare` shape as the other
cross-check scripts, for the 69-bus network.

### `exp_e_ieee118_scaling.py` — **not** about singularity; purely a speed test

This script has a completely different purpose from every other file in
`experiments/`: the 118-bus network here is an ordinary, healthy,
well-behaved network (borrowed from a widely-used third-party power-
systems modeling tool called *pandapower*) used **only** to measure how
each of the four solvers' *running time* scales up as the network gets
bigger — nothing here is about singularity or ill-conditioning at all.

- **`load_case118_ybus()`** — asks the pandapower library to build and
  solve its standard 118-bus example network, then extracts its `Ybus`
  grid of numbers for this project's own solvers to time themselves
  against (rather than inventing a fake, random grid of numbers, which
  would behave differently from a real network's characteristic
  structure).
- **`block_diagonal_replicate(Y, factor)`** — takes that one real 118-bus
  grid and duplicates it side by side `factor` times (as several
  completely separate, non-interacting copies bolted together) to
  synthetically produce a *larger* grid of numbers that still has
  realistic internal structure, for testing how solve time grows with
  size.
- **`to_real_jacobian_form(Y)`** — converts the complex-number grid into
  the same all-real-numbers, doubled-size format this project's actual
  Jacobian uses (§3.1's rectangular-coordinates choice), so the timing
  test is measuring the same *shape* of problem the rest of the project
  actually solves.
- **`median_runtime_sec(solve_fn, J, rhs, repeats)`** — calls a given
  solver function several times on the same input and returns the
  *median* time taken (median, rather than average, to avoid one
  freak-slow run — e.g. from the computer briefly doing something else —
  from skewing the result).
- **`run_scaling_benchmark()`** — runs the whole experiment: builds the
  real 118-bus grid, replicates it at several different sizes, times all
  four solvers at each size, prints a table, estimates each solver's
  empirical "grows like size to the power of ___" exponent, and saves a
  `.csv` file of all the raw numbers.

### `exp_b_svd_4bus.py`, `exp_c_rrqr_4bus.py`, `exp_d_tikhonov_4bus.py`

Three near-identical files (originally each written by a different team
member, hence the `_b`/`_c`/`_d` naming, matching the four solver
"owners"), each comparing the classic direct solver against **one**
specific alternative solver on the 4-bus network:

- **`run_4bus_case(...)`** — build the 4-bus network and solve it with a
  chosen method (identical in spirit to `exp01_4bus.py`'s helper, just
  reused here through the shared architecture).
- **`print_run(label, result)`** — prints a detailed per-iteration report,
  customized to show that specific solver's own diagnostic numbers (rank,
  pivot order, regularization strength, etc. — whichever apply).
- **`run_all_cases()`** — runs both the healthy and floating 4-bus cases
  through both the classic method and the one alternative method being
  showcased, and prints how far apart their final answers land (when both
  converge) as a basic sanity check that they agree where they're
  supposed to.

### `exp_c_rrqr_vs_svd_4bus.py` — the two "throw away bad directions" methods, head to head

- **`run_case(*, load_on_secondary, method)`** — runs the 4-bus network
  through one chosen solver, without the extra diagnostic overhead (see
  next function).
- **`median_solver_runtime_sec(...)`** — times just the *very last*
  iteration's solve repeatedly (that iteration is closest to the actual
  singularity, making it the most demanding/interesting one to time) and
  reports the median.
- **`compare_case(label, *, load_on_secondary)`** — runs SVD and RRQR on
  the same case, reports whether they agree on how many directions were
  well-determined ("rank"), how far apart their final answers land, and
  compares all three solvers' typical solve time on this small network.
- **`run_all_cases()`** — runs the comparison on both the healthy and
  floating 4-bus cases.

### `exp_b_svd_tolerance_4bus.py` — how sensitive is SVD's cutoff choice?

- **`RTOL_GRID`** — a deliberately chosen list of different cutoff
  ("how small a direction counts as basically zero") values to try,
  including the solver's own automatic default.
- **`run_case(*, load_on_secondary, rtol)`** — runs the floating or
  healthy 4-bus case with one specific cutoff value.
- **`summarise_run(...)`** — flattens one run's results into a single
  summary row (for a spreadsheet) plus a detailed per-iteration trace row
  list.
- **`_write_csv(path, rows)`** — a tiny, dependency-free helper for
  writing a list of dictionaries out as a `.csv` spreadsheet file.
- **`_plot_diagnostics(summary_rows, trace_rows)`** — draws three
  specific charts using `matplotlib` (a standard Python charting
  library): the final "spectrum" of direction-strengths on a log scale
  with the cutoff marked, how many directions get kept as the cutoff
  changes, and how the final error changes as the cutoff changes.
- **`run_sweep()`** — runs every cutoff value in `RTOL_GRID` on both the
  healthy and floating cases, saves the resulting spreadsheets and
  charts, and prints a summary table.

### `exp_d_tikhonov_lambda_sweep_4bus.py` — how sensitive is Tikhonov's penalty strength?

The exact same five-function shape as the SVD tolerance sweep above
(`run_case`, `summarise_run`, `_write_csv`, `_plot_diagnostics`,
`run_sweep`), except sweeping Tikhonov's `alpha` penalty-strength dial
instead of SVD's cutoff, over a specific list of values ranging from
"basically no penalty" up to "very strong penalty."

### `exp_d_ieee13_investigation.py` — the project's main, novel investigation

This is the centerpiece experiment script — where the project goes beyond
"does the base research paper's proposed method work" and actually digs
into *why* the 13-bus network behaves the way it does.

- **`_flat_start_conditioning(state, Ybus)`** — computes how close to
  singular the very first (flat-start) guess's Jacobian is, before any
  iterating happens.
- **`_voltage_spread_metrics(state, x)`** — given a converged (or
  partially converged) result, computes a bundle of summary numbers: the
  spread between the largest and smallest phase voltage, the spread
  between line-to-line voltages, and the average zero-/positive-/
  negative-sequence magnitudes (§3.4) across every fully-three-phase bus.
- **`_run_and_summarise(label, state, Ybus)`** — runs the shared solver
  (Tikhonov, by default for this network — see §4) on a given, already-
  built network and packages everything above into one summary
  dictionary, also printing a one-line progress report.
- **`solver_robustness_study()`** — the key experiment behind the
  project's headline finding: runs **all four** solvers at **five**
  different overall load levels (50% through 150% of normal) and records
  which ones converge and how many iterations they take at each level.
  This is exactly where "SVD and RRQR stop converging above roughly 75%
  of normal load, but Tikhonov keeps working until 125%" was discovered.
- **`load_scaling_study()`** — runs the network at each of five load
  levels and records the full summary bundle from `_voltage_spread_metrics`
  at each level (used to check, among other things, that the flat-start
  condition number never depends on load level — since the flat start is
  always the same regardless of how much power anyone's asking for).
- **`imbalance_study()`** — runs the network at four different amounts of
  artificial phase imbalance (0%, 10%, 20%, 30% — a project-defined rule,
  since neither the base paper nor the official data specify an exact
  imbalance recipe, and this is explicitly documented as such rather than
  silently invented) and records the summary bundle at each level. This
  is the experiment behind the "imbalance loads almost entirely onto the
  undetermined zero-sequence component" finding (§1.6's closing point).
- **`transformer_configuration_study()`** — runs the network four ways:
  as the research paper specifies (both transformers floating), with just
  one grounded, with just the other grounded, and with both grounded —
  directly demonstrating that grounding either transformer meaningfully
  improves the conditioning, and grounding both essentially fixes it.
- **`_write_csv(path, rows)`** — the same small spreadsheet-writing helper
  seen elsewhere.
- **`run_all()`** — runs every study above in sequence and saves each
  one's results to its own spreadsheet file.

### `exp_d_ieee13_tikhonov_alpha_sweep.py` — pinning down the specific `alpha` value used elsewhere

- **`ALPHA_GRID`** — a specific list of penalty-strength values to try
  (matching the same style of grid used in the 4-bus Tikhonov sweep),
  including `0.0` as an "unregularized" reference point.
- **`run_alpha(alpha)`** — runs the standard (nominal-load) 13-bus network
  once with one specific `alpha` value.
- **`summarise_run(label, alpha, result)`** — packages one run's outcome
  (converged or not, iteration count, final penalty strength actually
  used, final adjustment size, etc.) into one spreadsheet-ready row.
- **`_write_csv(path, rows)`** — the same small helper again.
- **`run_sweep(*, write_csv=True, verbose=True)`** — runs every `alpha`
  value in the grid and reports which ones actually let Newton-Raphson
  converge. This is what makes the specific choice of `alpha=1e-8` (used
  everywhere else in the 13-bus results) a reproducible, checked decision
  rather than an arbitrary unexplained number — the file's docstring
  notes explicitly that convergence isn't guaranteed to improve smoothly
  as the penalty gets stronger; there's a real "sweet spot," not just "more
  is better."

### `member_b_utils.py`, `member_c_utils.py`, `member_d_utils.py`

Three files that are **intentionally almost identical** to each other —
each defines exactly one function, **`summarise_nr_history(result)`**,
which digs through a solver run's `history` log and pulls out a handful
of commonly-needed summary numbers (how many iterations actually involved
a real linear solve, how many of those succeeded, and what the final
error was). The reason there are three separate copies of essentially the
same seven lines of code, instead of one shared version, is explained in
each file's own docstring: this project's team-based file-ownership
convention deliberately avoids one team member's experiment scripts
depending on a file "owned" by a different member, even for something
this small and inarguably harmless to duplicate.

## 3.7 `tests/` — making sure all of the above is actually correct

Every file here uses `pytest` (a standard Python testing tool: you write
short functions starting with `test_`, and running `pytest` automatically
finds and runs every one, reporting pass/fail for each). Several of these
files' functions have unusually long docstrings — that's deliberate: they
don't just assert "this number should equal that number," they explain
*why* that should be true, so a future reader who's confused about some
behavior can often find the actual reasoning by reading the relevant test
rather than having to re-derive it.

- **`test_jacobian.py`** — the single most important test file in the
  project. Independently recomputes the Jacobian by "wiggle each unknown
  a tiny bit and measure the actual change" (a **finite-difference**
  check, entirely independent of the calculus-derived formula in
  `jacobian.py`) and confirms the two methods agree to within a tiny
  tolerance. Every other feeder-specific test file below repeats this
  exact check for its own network — **nothing downstream is trusted
  until this passes.**
- **`test_svd_pinv.py`, `test_rrqr.py`, `test_tikhonov.py`** — feed each
  solver small, deliberately hand-picked example grids of numbers (some
  perfectly normal, some rank-deficient, some containing invalid values
  like "not-a-number") and check that each solver behaves exactly as
  documented in every case.
- **`test_linear_solvers.py`** — feeds the *same* deliberately-tricky
  example grids to more than one solver at once and checks that they
  agree with each other (and with a known correct textbook answer) on
  the well-determined cases, and behave sensibly, differently but
  correctly, on the rank-deficient ones.
- **`test_svd_integration_4bus.py`, `test_rrqr_integration_4bus.py`,
  `test_tikhonov_integration_4bus.py`** — confirm that each solver, when
  actually plugged into the full Newton-Raphson loop on the real 4-bus
  network (not just a small hand-picked example grid), produces sensible,
  matching results.
- **`test_ieee13.py`, `test_ieee37.py`, `test_ieee69.py`** — the
  finite-difference Jacobian check for each specific network, plus a
  battery of "structural" checks confirming this project's specific
  claims about each network (e.g. "the 13-bus network's flat-start
  Jacobian has *exactly* 2 near-zero directions, not 1 or 3" — with a
  long docstring explaining exactly why that specific number is expected).
- **`test_ieee13_investigation.py`** — checks the specific numeric
  findings from `exp_d_ieee13_investigation.py` and
  `exp_d_ieee13_tikhonov_alpha_sweep.py` stay true (e.g. "grounding both
  transformers really does drastically shrink the condition number," "the
  imbalance sweep really does load almost entirely onto the zero-sequence
  component," "the reported `alpha=1e-8` really is the only value in the
  sweep grid that converges").
- **`test_sequence_components.py`** — checks the symmetrical-components
  math (§3.4) against known textbook special cases (e.g. "a perfectly
  balanced set of three voltages should have exactly zero zero-sequence
  and negative-sequence content").
- **`test_ieee118_scaling.py`** — a handful of lightweight checks that the
  118-bus scaling benchmark's helper functions behave correctly, without
  running the full expensive benchmark.
- **`test_opendss.py`** — a small, direct sanity check that the OpenDSS
  cross-validation pipeline itself works.

## 3.8 `data/` — the source data and its full history

- **`data/provenance.yml`** — **the single most important reference file
  for trustworthiness** in this whole project. For every network, it
  records: exactly where the official data came from (with a web
  address and the date it was fetched), exactly which numbers the
  research paper specifies, every assumption this project had to make
  where the paper or the official data left something unclear, and —
  importantly — every place where a genuine discrepancy or open question
  was found and **deliberately left open and documented** rather than
  silently "fixed" in one direction or another. Read this file before
  trusting any specific number quoted from this project.
- **`data/raw/ieee4/`, `ieee13/`, `ieee37/`, `ieee69/`** — the actual
  official source files (in OpenDSS's own `.dss` scripting format, or the
  original research-community format they were published in), plus this
  project's own OpenDSS-language rewrite of each network (used
  specifically for the cross-validation work in §3.5). The 69-bus
  network's OpenDSS rewrite is **generated automatically** by
  `data/raw/ieee69/gen_ieee69_dss.py` (rather than hand-typed) — that
  script reads the exact same official data `src/model/ieee69_data.py`
  uses and mechanically writes out the matching OpenDSS-language file,
  so the two can never accidentally drift out of sync with each other.

## 3.9 `report/` — the written-up paper

- **`report/paper.tex`** — the full written research paper (in LaTeX, a
  widely-used academic typesetting format), covering the problem, the
  method, the results, and an honest discussion of every open
  discrepancy — following the standard structure for this kind of
  research paper (introduction, background, methods, results, discussion,
  limitations, conclusion).
- **`report/refs.bib`** — the paper's bibliography (a small, separate
  file listing every outside source cited, in a standard format LaTeX
  reads automatically).
- **`report/make_figures.py`** — regenerates every chart used in the
  paper by **actually re-running the real experiments live**, rather than
  reusing old, possibly-stale numbers from a previous run. Its functions
  (`fig_4bus_conditioning`, `fig_ieee13_solver_robustness`,
  `fig_ieee13_zero_sequence`, `fig_ieee13_transformer_grounding`,
  `fig_ieee118_scaling`, `fig_crossvalidation_summary`, plus a shared
  `save(fig, name)` helper) each correspond to exactly one chart in the
  final paper.
- **`report/figures/`** — the actual chart image files produced by the
  script above (saved both as `.pdf`, for inserting into the paper, and
  `.png`, for quickly eyeballing on screen).
- **`report/paper.pdf`** — the fully typeset, ready-to-read final paper.

## 3.10 Files in the project root

- **`README.md`** — the public-facing overview: what this project is,
  its current status, and how to run things, written for an outside
  reader browsing the project (e.g. on GitHub) rather than as a deep
  teaching document like this one.
- **`STRUCTURE.md`** — a more compact "resume working on this project"
  reference, covering the same ground as this file but assuming you
  already know the electrical-engineering vocabulary and just need a
  quick, precise map plus the current project status and open items.
- **`requirements.txt`** — the exact list of third-party Python
  libraries this project depends on (numerical computing, plotting,
  spreadsheet reading/writing, the OpenDSS connector, testing, etc.),
  installed all at once with `pip install -r requirements.txt`.
- **`.gitignore`** — tells the version-control system (`git`) which
  files/folders should *never* be tracked or shared — mainly
  temporarily-generated output (`results/`, `figures/`, Python's own
  cache folders) and some internal working notes not meant for outside
  readers.
- **The base research paper's `.pdf`** (the long filename starting
  `Singularity_Handling_for_Unbalanced_Three-Phase_Transformers_...`) —
  the original published paper this whole project reproduces and
  extends, kept in the repository for easy reference.
- **`HELP.md`** — this file.

---

# Part 4 — The one lesson worth remembering above all others

While building the 13-bus and 69-bus networks, **two separate, real,
independent bugs** were found in exactly the same *category* of mistake:
converting a published "how much power does this junction use" number
into this project's internal per-phase, normalized units. Both bugs made
every load in that network exactly **3× wrong** (one 3× too small, one 3×
too large — opposite directions, unrelated mistakes, just the same class
of error).

**Both were caught the same way**, and it's the single most important
working habit in this whole codebase: rather than immediately comparing
the entire, already-borderline-singular network against OpenDSS (where a
genuine 3× scaling bug and the *expected*, legitimate disagreement from an
undetermined direction can look confusingly similar), first build a tiny,
deliberately well-behaved, definitely-not-singular piece of the same
network (e.g. just one transformer, or just one wire, with one simple
load) and compare *that* small piece against OpenDSS first. On a
well-behaved small piece, there's no ambiguity at all — either the numbers
match or they don't — so a real bug has nowhere to hide. Only once that
small piece checks out is it safe to trust a comparison on the full,
singular network.

If you ever add a new network to this project, or touch any load-scaling
code, **do this same check first**, every time — not just when a number
already looks suspicious.

---

# Part 5 — Provenance: what was designed here vs. copied from outside sources

It's worth being explicit about which files in this repository are
original engineering work (done in this project, by the AI assistant
working with the repository owner) versus which files are data copied
directly from an official public source, versus which files were added
by other student team members. This distinction matters for a course
project: it's the difference between "we wrote this" and "we correctly
transcribed/used this."

## 5.1 Copied verbatim from official/public sources (pure data, not designed here)

- **`src/model/ieee13_data.py`** — line-code impedance matrices, the line
  list, and the load list, copied directly from the official IEEE
  `IEEE13Nodeckt.dss` distribution test feeder files.
- **`src/model/ieee37_data.py`** — same idea, from the official
  `ieee37.dss` + `IEEELineCodes.DSS`.
- **`src/model/ieee69_data.py`** — bus loads and branch data adapted from
  the published Baran & Wu (1989) 69-bus system / its MATPOWER
  `case69.m` encoding.
- **`data/raw/ieee13/*.dss`, `data/raw/ieee37/*.dss`** (the original,
  non-generated ones) — official OpenDSS files fetched as-is.
- **The base research paper's PDF**
  (`Singularity_Handling_for_Unbalanced_Three-Phase_Transformers_...pdf`)
  — the published paper this project reproduces and extends; kept in the
  repository for reference, not authored here.
- **IEEE-118 admittance data** used in `exp_e_ieee118_scaling.py` — pulled
  from the third-party `pandapower` library's built-in `case118` network,
  not independently fetched or transcribed.
- The **IEEEtran LaTeX document class** that `report/paper.tex` is built
  on is a standard external academic template — only the paper's actual
  written content is original to this project.

## 5.2 Designed and written from scratch for this project

Everything implementing the actual numerical method, all four solvers,
all network-assembly/experiment/test/validation code, and all
documentation described in Parts 3 and 4 of this file:

- `src/model/state.py`, `src/model/ybus.py`
- `src/powerflow/mismatch.py`, `jacobian.py`, `newton.py`
- `src/solvers/direct.py`, `svd_pinv.py`, `rrqr.py`, `tikhonov.py`
- `src/diagnostics/sequence_components.py`
- `src/validation/opendss.py`, `crosscheck.py`, `antifloat_study.py`
- All of `experiments/exp01`–`exp04*`, `exp_b/c/d/e*`,
  `member_b_utils.py`
- All of `tests/*.py`
- `report/paper.tex` (the written content), `report/refs.bib`,
  `report/make_figures.py`
- `STRUCTURE.md`, `HELP.md`, `CLAUDE_HANDOFF.md`
- `data/raw/ieee69/gen_ieee69_dss.py` (an original generator script, not
  a fetched file)

These files *implement* the base paper's described method (SVD/
Moore-Penrose pseudo-inverse, RRQR, Tikhonov, the rectangular-coordinate
Newton-Raphson formulation) — but every line of code carrying out that
method is original engineering, not copied from anywhere.

## 5.3 Added by other team members (not part of the above)

- **`experiments/exp_d_ieee13_tikhonov_alpha_sweep.py`**,
  **`experiments/member_d_utils.py`**, **`experiments/member_c_utils.py`**
  — added directly by other members of the team through their own
  commits (for example the "2105116(Member D)" commit). These were read
  and relied on for the analysis in this document, but are teammates'
  own authorship, not the AI assistant's.
- Any commits made on the other student-ID branches/history
  (`2105104`, `2105116`, `2105117`) that predate this document's own
  involvement in the project are likewise teammates' own work.

## 5.4 Third-party tools and libraries used as-is (never reimplemented)

`numpy`, `scipy` (specifically its `qr`, `lstsq`, and the `gelsy` LAPACK
driver used inside `rrqr.py`), `opendssdirect`, `pandapower`,
`matplotlib`, and `pytest`. This project calls these libraries; it does
not reimplement anything they already provide.
