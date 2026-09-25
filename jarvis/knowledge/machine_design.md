# Machine Design

Core question: how do we size machine elements so they survive their loads for their whole life?

## Design process and factor of safety
- Define requirements, loads (including dynamic and shock loads), constraints; choose concept
  and material; size; check every failure mode (yield, fracture, fatigue, buckling, wear,
  deflection); iterate; document.
- Factor of safety n = strength / stress (or failure load / applied load). Typical: 1.25-1.5 for
  well-known loads and materials, 2-3 for average conditions, 3-4+ for uncertain loads,
  brittle materials or where failure endangers people.

## Static failure
- Ductile: von Mises (distortion energy) n = S_y / σ_vm, or Tresca n = S_y / (σ1 - σ3).
- Brittle: modified Mohr or Coulomb-Mohr, using both tensile and compressive strength.
- Apply stress concentration factors K_t for brittle materials; for ductile materials under
  static load, local yielding usually redistributes stress.

## Fatigue
- Parts fail under repeated loads well below the ultimate strength. Cracks start at stress
  raisers and grow each cycle.
- S-N curve. Steels have an endurance limit S_e' ≈ 0.5 S_ut (for S_ut ≤ 1400 MPa); aluminium has none.
- Marin factors: S_e = k_a k_b k_c k_d k_e k_f S_e' (surface finish, size, loading type,
  temperature, reliability, miscellaneous).
- Fatigue stress concentration K_f = 1 + q (K_t - 1), with notch sensitivity q.
- Fluctuating stress: σ_m = (σ_max + σ_min)/2, σ_a = (σ_max - σ_min)/2.
  Goodman: σ_a / S_e + σ_m / S_ut = 1/n. Gerber and ASME-elliptic are less conservative;
  Soderberg is more conservative. Check first-cycle yield too.
- Variable amplitude: Miner's rule Σ n_i / N_i = 1 at failure.
- Design for fatigue: generous fillets, smooth finishes, shot peening, avoid welds and holes at
  high-stress spots, compressive residual stress.

## Shafts, keys and couplings
- Shaft stresses: bending σ = 32 M / (π d³), torsion τ = 16 T / (π d³), combined through
  von Mises: σ' = sqrt(σ² + 3τ²). With fatigue, the DE-Goodman equation gives the diameter.
- Check deflection and slope at bearings and gears, and critical speed (keep away from the
  first bending natural frequency).
- Keys: size from the shaft diameter, check shear and crushing (bearing) stress.

## Bearings
- Rolling bearings: basic dynamic load rating C, life L10 = (C/P)^a million revolutions,
  a = 3 for ball and 10/3 for roller bearings. Equivalent load P = X F_r + Y F_a.
- Journal (plain) bearings: hydrodynamic lubrication, Sommerfeld number, Petroff's equation
  for friction.

## Gears
- Spur gear basics: module m = d / N (pitch diameter / teeth), circular pitch p = π m, speed
  ratio = N2 / N1. Pressure angle usually 20°.
- Tangential load W_t = 2 T / d (or power / pitch line speed).
- Bending stress by the Lewis equation σ = W_t / (b m Y) plus AGMA factors; contact (pitting)
  stress from Hertz theory. Helical gears run smoother and quieter but create axial thrust.
- Minimum teeth to avoid interference: about 17 for 20° full-depth teeth.

## Fasteners, welds and springs
- Bolts: tensile stress area A_t, preload F_i ≈ 0.75 A_t S_p for reusable joints. The joint
  stiffness constant C = k_b / (k_b + k_m) decides how much of an external load the bolt sees.
  Tightening torque T ≈ 0.2 F_i d.
- Welds: fillet weld throat t = 0.707 h; check shear on the throat area. Weld toe fatigue is often critical.
- Helical springs: k = G d⁴ / (8 D³ N_a); shear stress τ = K_B 8 F D / (π d³) with the Bergsträsser
  (or Wahl) factor. Check buckling and surge frequency.

## Tolerances, fits and GD&T
- ISO fits: hole basis, e.g. H7/g6 (sliding), H7/k6 (transition), H7/p6 (press fit).
- GD&T controls form (flatness, circularity), orientation (perpendicularity, parallelism),
  location (position) and runout, relative to datums. Tolerance stack-ups: worst case
  or statistical (root sum square).

## Materials selection
- Ashby approach: define the function, objective and constraints; derive a material index
  (for example a light, stiff beam maximises E^(1/2) / ρ; a light, strong tie maximises σ_f / ρ).
- Typical choices: structural steel (cheap, stiff, weldable), aluminium alloys (light, easy to
  machine), titanium (strong and light, expensive), cast iron (damping, compression, machine beds),
  polymers and composites (light, corrosion-resistant, lower stiffness), ceramics (hard, hot, brittle).
