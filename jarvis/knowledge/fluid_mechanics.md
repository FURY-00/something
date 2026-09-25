# Fluid Mechanics

Core question: how do liquids and gases flow, and what forces and pressure losses result?

## Fluid properties and statics
- Density ρ (water 1000 kg/m³, air about 1.2 kg/m³ at 20 °C), dynamic viscosity μ (water
  1.0e-3 Pa·s at 20 °C, air 1.8e-5), kinematic viscosity ν = μ / ρ.
- Newtonian fluids: τ = μ du/dy. Non-Newtonian: blood, paint, polymer melts.
- Hydrostatics: p = p0 + ρ g h. Manometers: walk through the tube adding ρ g h going down,
  subtracting going up.
- Force on a submerged plane surface: F = p_centroid A, acting at the centre of pressure
  (below the centroid): y_cp = y_c + I_xc / (y_c A).
- Buoyancy (Archimedes): F_B = ρ_fluid g V_displaced. Stability depends on the metacentric height.

## Conservation laws
- Continuity: ṁ = ρ A V is constant along a pipe. Incompressible: A1 V1 = A2 V2.
- Bernoulli (steady, incompressible, inviscid, along a streamline):
  p + ρ V²/2 + ρ g z = constant. It doesn't hold across pumps or turbines, or with friction.
- Energy equation with losses: p1/(ρg) + V1²/(2g) + z1 + h_pump = p2/(ρg) + V2²/(2g) + z2
  + h_turbine + h_L (heads in metres).
- Momentum: ΣF = ṁ (V_out - V_in) (vector). Gives forces on bends, nozzles, jets and vanes.
- Applications: Pitot tube V = sqrt(2 Δp / ρ); Venturi and orifice flow meters (with a discharge
  coefficient); Torricelli V = sqrt(2 g h).

## Dimensional analysis and similarity
- Buckingham Pi: n variables and k dimensions give n - k dimensionless groups.
- Reynolds number Re = ρ V D / μ = V D / ν (inertia vs viscosity). Froude Fr = V / sqrt(g L)
  (free surfaces). Mach Ma = V / c (compressibility matters above about 0.3). Also Weber
  (surface tension) and Strouhal (vortex shedding, St ≈ 0.2 for cylinders).
- Model testing: match the governing dimensionless numbers between model and prototype.

## Internal flow: pipes and 1D pipe networks
- Laminar for Re < about 2300, turbulent above about 4000 in pipes.
- Laminar fully developed (Hagen-Poiseuille): u(r) = u_max (1 - r²/R²), u_max = 2 V_avg,
  Δp = 32 μ L V / D², volume flow Q = π D⁴ Δp / (128 μ L), friction factor f = 64 / Re.
- Darcy-Weisbach (any regime): h_f = f (L/D) V²/(2g), Δp = f (L/D) ρ V²/2.
- Turbulent f from the Moody chart or Colebrook: 1/sqrt(f) = -2 log10(ε/(3.7 D) + 2.51/(Re sqrt(f))).
  Explicit Haaland or Swamee-Jain approximations work to within a few percent.
- Minor losses: h_m = K V²/(2g) for valves, bends, entrances (sharp entrance K ≈ 0.5) and exits (K = 1).
- Pipe networks (1D flow): at each junction flow in = flow out; around each loop the head losses sum
  to zero (Hardy Cross method, or solve the nonlinear system numerically). Series pipes: same Q,
  losses add. Parallel pipes: same head loss, flows add.
- Pumps: operating point = where the pump curve meets the system curve (static head + k Q²).
  Power = ρ g Q H / η. Avoid cavitation: available NPSH must exceed the required NPSH.
- Entrance length: laminar L_e ≈ 0.05 Re D; turbulent ≈ 10 to 60 D.

## External flow, boundary layers, drag and lift
- Boundary layer: a thin layer where viscosity matters. Laminar flat plate thickness
  δ ≈ 5 x / sqrt(Re_x); transition near Re_x ≈ 5e5.
- Drag F_D = C_D ρ V² A / 2; lift F_L = C_L ρ V² A / 2. Sphere C_D ≈ 0.47 (subcritical), cylinder
  about 1.2, streamlined bodies about 0.04.
- Flow separation under adverse pressure gradients causes pressure (form) drag and stall.
- Stokes flow around a sphere (Re < 1): F_D = 3 π μ V D.

## Turbulence and CFD
- Turbulence: chaotic, 3D, with eddies of many sizes. RANS models (k-ε, k-ω SST) solve for the
  averaged flow; LES resolves the large eddies. k-ω SST is a good default for separation and
  wall-bounded flows.
- Near-wall mesh: y+ ≈ 1 when resolving the viscous sublayer (k-ω SST), 30-300 with wall functions.
- CFD workflow: geometry, mesh (with inflation layers on walls), physics and boundary conditions
  (velocity inlet, pressure outlet, walls, symmetry), solve until residuals are low and monitored
  quantities stop changing, then check mesh independence and compare with hand calculations
  (e.g. Hagen-Poiseuille or Moody).

## Compressible flow and open channels
- Speed of sound c = sqrt(k R T). Isentropic nozzle: flow chokes at the throat when Ma = 1;
  converging-diverging nozzles reach supersonic speeds. Normal shocks raise pressure and entropy.
- Open channels: Manning V = (1/n) R_h^(2/3) S^(1/2) (SI). Hydraulic jumps, critical depth at Fr = 1.
