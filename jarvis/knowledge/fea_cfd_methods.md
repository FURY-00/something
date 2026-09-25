# FEA, CFD and Engineering Problem Solving

Core question: how do we solve real engineering problems reliably, by hand and with simulation?

## A method for any engineering problem
1. Restate the problem: what is known, what is asked, units.
2. Sketch it: free-body diagram, control volume, circuit or flow path.
3. State assumptions (steady, incompressible, linear elastic, ideal gas, negligible losses...).
4. Pick the governing principles (equilibrium, conservation of mass, momentum and energy,
   constitutive laws) and write the equations.
5. Solve symbolically first, then put numbers in. Carry units the whole way.
6. Check: units, order of magnitude, limiting cases (what if L → 0?), signs, and comparison with
   a known result. Then state the answer with sensible significant figures.
- Dimensional analysis catches most algebra mistakes. Always convert to SI before calculating.

## How the finite element method works
- Split the domain into elements connected at nodes; approximate the field (displacement,
  temperature) inside each element with shape functions.
- Each element contributes a stiffness matrix; assembled they form K u = F. For a 1D bar element
  k = (A E / L) [[1, -1], [-1, 1]].
- Solve for nodal values, then compute derived quantities (strain, stress) from their derivatives.
  Stresses are less accurate than displacements and are smoothed ("averaged") for plots.
- Element choice: 1D (bars, beams, pipes) for frames and piping, 2D (plane stress, plane strain,
  axisymmetric), shells for thin structures, 3D solids for chunky parts. Quadratic elements
  (e.g. 10-node tetrahedra) are much more accurate than linear tetrahedra in bending.

## Doing FEA well
- Boundary conditions cause most errors. Constrain rigid-body motion without over-constraining.
  A fixed support is stiffer than reality; loads applied at single nodes cause infinite local stress
  (singularities) that are not real. Judge stress a little way from them.
- Mesh convergence: refine until the quantity you care about changes by less than a few percent.
  Refine where gradients are high (fillets, holes, contact).
- Sharp re-entrant corners are singularities: stress keeps rising as you refine. Model the real fillet.
- Symmetry: model half or a quarter with symmetry conditions to save time.
- Verify: reaction forces equal applied loads; deflection shape makes sense; compare with a hand
  calculation (beam formula, pressure vessel formula) before trusting a complex model.
- Linear static assumes small deflections, linear material and fixed contact. Big deflections,
  plasticity or contact need nonlinear analysis.
- Other analyses: modal (natural frequencies, needs density), buckling (eigenvalue gives a load
  factor; imperfections lower the real value), thermal (steady or transient), thermal stress
  (temperatures, then structure), harmonic (response to sinusoidal loads), fatigue (from stress history).

## How CFD works
- Solves the Navier-Stokes equations (mass, momentum, energy) on a mesh with the finite volume method.
- Pressure-based solvers for incompressible and mildly compressible flow; density-based for high-speed flow.
- Steps: geometry (the fluid region), mesh (inflation layers at walls; finer where gradients are
  high), models (laminar or a turbulence model, heat transfer, multiphase), materials, boundary
  conditions, initialise, iterate to convergence, post-process.
- Convergence: residuals falling by 3-4 orders of magnitude and, more importantly, monitored values
  (pressure drop, drag, outlet temperature) that stop changing.
- Mesh independence: repeat on a coarser and a finer mesh; the answer should change by only a
  few percent.
- Validate against theory or experiment: Hagen-Poiseuille for laminar pipe flow, Moody chart
  pressure drops, drag coefficients.

## 1D, 2D or 3D? Choosing the right model
- Use 1D when the physics varies mainly along one direction: pipe networks (1D pipe flow with
  friction factors), conduction through walls, beams and trusses, long fins. Fast and often all you need.
- 2D axisymmetric for round things with round loads: pipes, pressure vessels, nozzles, shafts in
  axisymmetric loading. 2D plane stress for thin plates, plane strain for long prismatic bodies.
- 3D when geometry or loads have no simplifying symmetry. Start simple, then add detail.

## Numerical methods behind the scenes
- Root finding (Newton-Raphson, bisection), linear systems (Gaussian elimination, iterative solvers),
  ODEs (Euler, Runge-Kutta 4; stiff solvers for fast and slow dynamics together),
  finite differences for PDEs (the explicit heat equation is stable only if α Δt / Δx² ≤ 1/2).
- Python tools: numpy (arrays), scipy (optimize.fsolve, integrate.solve_ivp, linalg), sympy
  (symbolic algebra, derivatives, exact solutions), matplotlib (plots).
