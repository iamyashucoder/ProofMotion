# Coverage audit and build plan

Measured against `.toolcoverage.md`, which lists roughly 450 topics across
mathematics, physics, computer science, and agent coordination.

---

## 1. The framing that makes this tractable

450 topics does not mean 450 tools. The spec mixes three different kinds of
thing, and they scale completely differently:

| Layer | Scaling | Size |
|---|---|---|
| **Compute** | A few primitives compose across whole subjects. `dsolve` covers most of the ODE section; matrix ops cover all of linear algebra. | ~20 tools |
| **Reasoning** | Verification kinds, not topics. Dimensional analysis serves every physics topic at once. | ~7 tools |
| **Visualization** | Genuinely per-pattern. This is where the real work is. | ~45 components |

So the target is roughly **27 tools and 45 components**, not 450 of anything.

**The libraries are already installed.** `sympy.physics.units`, `sympy.stats`,
`sympy.ntheory`, `sympy.vector`, `sympy.geometry`, `sympy.logic`, `scipy`, and
`networkx` all arrived with Manim. Most compute tools are thin, testable wrappers
over code that already works — which makes the compute layer cheap and the
visualization layer the honest bottleneck.

---

## 2. What exists today

**22 tools**

| Group | Tools |
|---|---|
| Symbolic (7) | differentiate, integrate, simplify, solve, limit, series, verify_equality |
| Numeric (4) | evaluate, sample, iterate, roots |
| Manim API (4) | search, signature, members, validate_code |
| Layout (3) | frame, measure, check |
| Quality (2) | typeset_check, inspect_scene |
| Components (2) | component_search, component_build |

**10 components**

`function_plot`, `tangent_secant`, `riemann_area`, `iteration_trace`,
`free_body_diagram`, `circular_motion`, `projectile_motion`, `inclined_plane`,
`energy_bars`, `wave_form`

**Honest coverage estimate:** the compute tools touch algebra and single-variable
calculus well. The components cover perhaps **12% of the visualization spec**.
Everything else currently falls through to hand-written Manim, which is where the
truncations, the 39-lookup runs, and the text-on-curve defects come from.

---

## 3. Compute gap

Each of these is a wrapper over an installed library, verifiable by golden test.
Ordered by how much of the spec it unlocks.

| Tool | Unlocks | Backed by |
|---|---|---|
| `units_check` | **All 17 physics-reasoning items**; dimensional analysis, unit verification, plausibility | `sympy.physics.units` |
| `symbolic_matrix` | All 17 linear-algebra items: det, inverse, rank, nullspace, rref, eigen, diagonalise, SVD | `sympy.matrices` |
| `symbolic_ode` | Most of the 15 differential-equation items | `sympy.solvers.ode` |
| `numeric_ode` | Numerical ODE, phase portraits, stability | `scipy.integrate` |
| `symbolic_vector_calculus` | grad, div, curl, Jacobian, Hessian, flux | `sympy.vector` |
| `probability` | pdf/cdf/mean/variance for named distributions | `sympy.stats` |
| `statistics` | regression, sampling, CLT, confidence intervals | `scipy.stats` |
| `number_theory` | gcd, factorint, modular inverse, CRT, primality | `sympy.ntheory` |
| `combinatorics` | permutations, combinations, binomial, generating functions | `sympy` |
| `symbolic_algebra` | factor, expand, apart, together, trig simplification | `sympy` |
| `numeric_optimize` | minimisation, root finding, constrained optimisation | `scipy.optimize` |
| `numeric_interpolate` | interpolation, approximation error | `scipy.interpolate` |
| `graph_algorithms` | shortest paths, flows, traversal, trees | `networkx` |
| `logic_tables` | truth tables, satisfiability, Boolean algebra | `sympy.logic` |
| `geometry_solver` | intersections, distances, loci, analytic geometry | `sympy.geometry` |

Fifteen tools. Most are half a day each including tests.

---

## 4. Reasoning gap

This is the smallest group and the highest value per line, because it is what
makes output *trustworthy* rather than merely produced. Nothing here exists yet.

| Tool | Purpose |
|---|---|
| `units_check` | Dimensional consistency of an equation. The physics verification tier `PLAN.md` deferred. |
| `counterexample_search` | Refute a claimed identity or inequality by sampling before trying to prove it |
| `limiting_case_check` | Does the result behave correctly as a parameter → 0, ∞, or a known special case |
| `plausibility_check` | Sign, magnitude, and monotonicity sanity on a physical result |
| `assumption_tracker` | Carry and surface the conditions a derivation depends on |
| `induction_check` | Verify base case and inductive step mechanically |
| `symmetry_check` | Invariance under the transformations a result claims to respect |

Today `verify_plan` only checks LaTeX compilation plus single-`=` equalities via
SymPy. On the sin-derivative run that meant **0 of 10 steps were actually
proved** — every step was a limit, so nothing was checkable. These tools close
that gap.

---

## 5. Visualization gap — the real work

~45 components. Grouped by what each unlocks.

### Mathematics (20)

`geometry_construction` · `unit_circle` · `vector_field` · `slope_field` ·
`contour_plot` · `surface_3d` · `region_shading` · `sequence_convergence` ·
`matrix_transform` · `complex_plane` · `distribution_plot` ·
`probability_simulation` · `algorithm_trace` · `graph_network` ·
`phase_portrait` · `equation_chain` · `number_line` · `conic_section` ·
`polar_plot` · `taylor_approximation`

`equation_chain` deserves highlighting: it is the `TransformMatchingTex` pattern
that animates one expression becoming another, and it serves *every* subject —
"step-by-step symbolic transformation" appears in the spec and is currently
hand-written every time.

### Physics (17)

`pendulum` · `spring_mass` · `collision` · `orbit` · `torque_diagram` ·
`rolling_motion` · `ray_diagram` · `circuit_diagram` · `field_lines` ·
`charged_particle` · `pv_diagram` · `heat_flow` · `standing_wave` ·
`interference` · `spacetime_diagram` · `wavefunction` · `fluid_streamlines`

### Computer science (7)

`array_cells` · `linked_structure` · `tree_diagram` · `graph_traversal` ·
`recursion_tree` · `dp_table` · `complexity_plot`

### Cross-cutting infrastructure (already partly built)

`camera framing`, `collision prevention`, `automatic label placement`,
`responsive text sizing` — **done** (T1–T3). `parameter sliders` and
`narration timing` are the T8 interactive-HTML work.

---

## 6. Build order

Ordered by coverage unlocked per unit of effort, not by section order.

### Tier 1 — Verification foundation
`units_check`, `counterexample_search`, `limiting_case_check`,
`plausibility_check`, `assumption_tracker`

Small, no rendering, immediately raises trust in everything already produced.
`units_check` alone serves all 17 physics-reasoning items.

### Tier 2 — Compute breadth
`symbolic_matrix`, `symbolic_ode`, `numeric_ode`, `symbolic_vector_calculus`,
`symbolic_algebra`, `probability`, `statistics`, `number_theory`,
`combinatorics`, `numeric_optimize`, `numeric_interpolate`, `graph_algorithms`,
`logic_tables`, `geometry_solver`

Thin wrappers over installed libraries. Unlocks linear algebra, differential
equations, probability, discrete mathematics, and number theory as *subjects*,
even before their visuals exist.

### Tier 3 — Highest-leverage visuals
`equation_chain`, `geometry_construction`, `vector_field`, `unit_circle`,
`number_line`, `matrix_transform`, `distribution_plot`, `array_cells`

Eight components covering the most frequently requested patterns across every
subject.

### Tier 4 — Physics visuals
`pendulum`, `spring_mass`, `collision`, `orbit`, `circuit_diagram`,
`ray_diagram`, `field_lines`, `pv_diagram`, `standing_wave`, `torque_diagram`

### Tier 5 — Advanced visuals
`phase_portrait`, `slope_field`, `contour_plot`, `surface_3d`,
`taylor_approximation`, `sequence_convergence`, `region_shading`,
`complex_plane`, `conic_section`, `polar_plot`, `probability_simulation`

### Tier 6 — Computer science
`tree_diagram`, `graph_traversal`, `recursion_tree`, `dp_table`,
`linked_structure`, `complexity_plot`

### Tier 7 — Remaining physics
`wavefunction`, `spacetime_diagram`, `interference`, `fluid_streamlines`,
`charged_particle`, `heat_flow`, `rolling_motion`

---

## 7. Honest estimate

| Tier | Items | Rough effort |
|---|---|---|
| 1 | 5 tools | 1 day |
| 2 | 14 tools | 3–4 days |
| 3 | 8 components | 3 days |
| 4 | 10 components | 4 days |
| 5 | 11 components | 4–5 days |
| 6 | 6 components | 2 days |
| 7 | 7 components | 3 days |

Roughly **three weeks of focused work** for 27 tools and 45 components, every one
with golden tests sweeping its parameter extremes — which is what makes the
count meaningful rather than a list of things that exist but do not work.

Tiers 1 and 2 are the cheapest and unlock the most, so they come first even
though the visualization gap is what is most visible.

---

## 8. Two things this plan will not fix

**Composition is not automatic.** More components raise the ceiling but do not
guarantee the model reaches for them. `gpt-5.6-terra` consulted components and
then wrote its own code anyway; `deepseek-v4-pro` composed. Tracking
`state.composed` per run is how we tell whether the library is actually being
used, and it should be watched as the library grows.

**Subject coverage is not proof coverage.** A `symbolic_ode` tool lets the system
*solve* a differential equation. Verifying a claimed solution is a separate act,
and that is Tier 1 plus the `ProofDAG` work in `PLAN.md`. Solving is not the same
as being right, and the spec's reasoning section is really asking for the latter.
