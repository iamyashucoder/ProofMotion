# Competitive-exam capability matrix

ProofMotion is being built to explain, verify, and render competitive-exam
questions. A topic is **not complete** merely because an LLM can name a
formula. It needs all four items below:

1. a restricted deterministic solver or vetted reference-data lookup;
2. a domain-specific verification rule;
3. a tested visual component capable of showing the setup; and
4. representative question and render tests.

`Implemented` means all currently required computational pieces exist. `Gap`
means the system must not claim reliable automatic coverage yet.

## Current machine-checked baseline

The registry now contains **107 individual PCM profiles** (50 Physics, 34
Chemistry, 23 Mathematics). Each profile is linked to the official JEE Main
2026 information bulletin and JEE Advanced 2026 syllabus, has installed solver
or reference requirements, executable verification tools, registered visual
components, and a known-answer representative case. `tests/test_tier2.py`
executes every case through the tool dispatcher.

This establishes testable curriculum infrastructure; it does **not** claim that
all 107 final animations have received a human visual review. A rendered video
still needs to satisfy the build gate below before it can be promoted as a
showcase solution.

## Physics

| Unit | Required solver tools | Required visuals | Status |
| --- | --- | --- | --- |
| Units, errors, vectors | units_check, numeric_evaluate, symbolic_vector_calculus | vector diagram, number line | Partial visual gap |
| 1D/2D kinematics | jee_mechanics, linear_drag_projectile | bus/road, projectile, drag trajectory | Implemented core |
| Newton laws/friction | symbolic_solve, units_check | free-body, inclined plane | Partial solver gap |
| Work, energy, power | symbolic_solve, plausibility_check | energy bars | Partial solver gap |
| COM, collisions | conservation solver, numeric_ode | collision, COM markers | Partial solver gap |
| Rotation | torque/inertia/angular-momentum solver | torque diagram, rolling body | Gap |
| Gravitation/orbits | inverse-square solver, numeric_ode | orbit | Partial |
| SHM/waves | oscillator/standing-wave solver | pendulum, spring, wave, standing wave | Partial |
| Fluids | hydrostatics/Bernoulli solver | fluid column/streamline | Gap |
| Thermal physics | thermodynamic_process, ideal_gas_state | PV diagram | Partial |
| Electrostatics | electrostatics_point_charges | field lines, charge geometry | Partial |
| Capacitors | capacitor_network | capacitor/field diagram | Partial visual gap |
| Current electricity | circuit_network, power_transmission | circuit, power line | Partial |
| Magnetism/EMI/AC | Lorentz/induction/phasor solver | field, coil, phasor | Gap |
| Ray/wave optics | lens/mirror/interference solver | ray diagram, wavefront | Partial visual gap |
| Modern/nuclear/semiconductor | hydrogen_transition, decay/diode/transistor solver | energy levels, band diagram | Partial visual gap |

## Chemistry

| Unit | Required solver/reference | Required visuals | Status |
| --- | --- | --- | --- |
| Mole concept/stoichiometry | stoichiometry_limit, formula parser, equation balancer | particle/mole diagram | Partial |
| Atomic structure | hydrogen_transition, quantum-number validator | orbital/energy-level diagram | Partial visual gap |
| Gases/liquids | ideal_gas_state, kinetic-theory solver | PV/particle diagram | Partial |
| Thermodynamics | thermodynamic_process, Hess-law solver | energy profile, PV diagram | Partial |
| Equilibrium/ionic equilibrium | chemical_equilibrium_direction, ICE solver, weak_acid_ph | concentration/ICE diagram | Partial |
| Electrochemistry/kinetics | Nernst/cell/Arrhenius solver | galvanic cell, reaction-coordinate plot | Gap |
| Chemical bonding | vetted periodic/bonding data | VSEPR/orbital/MO diagrams | Gap |
| Inorganic chemistry | curated periodic, coordination, reaction-condition database | orbital/coordination diagrams | Gap—reference data required |
| Organic chemistry | curated reaction, reagent, stereochemistry database | mechanisms and molecular structures | Gap—reference data required |
| Practical chemistry | curated observations/procedures database | apparatus diagrams | Gap—reference data required |

## Mathematics

| Unit | Required solver tools | Required visuals | Status |
| --- | --- | --- | --- |
| Sets, relations, functions | symbolic tools, logic_table | set/number-line mapping | Partial visual gap |
| Algebra, complex, quadratics | symbolic_algebra, symbolic_solve | Argand/roots visualization | Partial visual gap |
| Sequences/series/binomial | symbolic_series, combinatorics, induction_check | term/area visualization | Partial |
| Permutation, probability, statistics | combinatorics, probability, monte_carlo | distribution plot | Implemented core |
| Matrices/determinants | symbolic_matrix | matrix_transform | Implemented core |
| Coordinate geometry/conics | geometry_solve, conic_properties | geometry construction | Implemented core |
| Trigonometry | symbolic simplification, limits | unit circle | Partial |
| Differential calculus | differentiate/limit/verify | function/tangent | Implemented core |
| Integral calculus | integrate/verify | Riemann area | Implemented core |
| Differential equations | symbolic_ode, numeric_ode | slope field/phase portrait | Partial visual gap |
| Vectors/3D geometry | vector calculus, geometry solver | 3D vector/plane scene | Gap |

## Build gate

No domain may be promoted from `Gap` or `Partial` to `Implemented` until it has:

- a deterministic or vetted-data answer path;
- positive, negative, and edge-case unit tests;
- a visual component render test at multiple parameter values;
- a prompt-to-tool routing test; and
- a reviewed example video where the diagram, derivation, and final answer agree.
