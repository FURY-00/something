# Statics and Mechanics of Materials

Core question: what forces act on a body, and how does the material inside respond?

## Equilibrium and free-body diagrams
- A body is in static equilibrium when ΣF = 0 and ΣM = 0 about any point. In 2D that is 3
  equations (ΣFx, ΣFy, ΣM), in 3D six.
- Free-body diagram (FBD): isolate the body, replace every support and contact by the force or
  moment it can exert. Pin: two force components. Roller: one force normal to the surface.
  Fixed support: two forces and a moment (2D).
- Statically determinate: unknowns = equations. More unknowns means statically indeterminate:
  you need deformation (compatibility) equations as well.
- Two-force members (pinned at both ends, no load in between) carry force only along their axis.
  This is the basis of truss analysis.
- Trusses: method of joints (ΣFx = ΣFy = 0 at each pin) or method of sections (cut through up to
  three members and take moments about where two unknown forces meet).
- Common mistakes: forgetting a reaction moment at a fixed support, and sign errors. Choose a
  direction, solve, and a negative answer just means the force points the other way.

## Stress and strain
- Normal stress σ = F/A (Pa = N/m², usually MPa = N/mm²). Shear stress τ = V/A.
- Normal strain ε = ΔL/L (dimensionless). Shear strain γ is the angle change in radians.
- Hooke's law: σ = E ε, τ = G γ, with G = E / (2(1 + ν)). Poisson's ratio ν (steel about 0.3).
- Axial deformation: δ = F L / (A E). Thermal strain: ε_T = α ΔT. If thermal growth is restrained,
  σ = E α ΔT.
- Typical values: steel E ≈ 200 GPa, yield 250-350 MPa (mild), aluminium E ≈ 69 GPa,
  titanium ≈ 110 GPa, concrete ≈ 30 GPa, wood ≈ 10 GPa.
- The stress-strain curve: elastic line (slope E), yield point, strain hardening, ultimate
  tensile strength, necking, fracture. Ductile metals yield a lot first; brittle materials don't.
- Stress concentration: σ_max = K_t σ_nominal near holes, notches and fillets (K_t ≈ 3 for a
  small hole in a wide plate in tension). This matters most for brittle materials and fatigue.

## Axial loading, torsion and pressure vessels
- Torsion of a circular shaft: τ = T r / J, twist φ = T L / (G J).
  Solid shaft J = π d⁴ / 32; hollow J = π (D⁴ - d⁴) / 32. Max shear is at the surface.
- Power transmitted: P = T ω (W, with ω in rad/s). ω = 2πN/60 for N in rpm.
- Thin-walled pressure vessel (t < r/10): hoop stress σ_h = p r / t, longitudinal σ_l = p r / (2t)
  for a cylinder; a sphere has σ = p r / (2t) in every direction. So cylinders split lengthwise.
- Thick-walled cylinders need the Lamé equations; stress is highest at the inner surface.

## Beams: shear force, bending moment and stress
- Shear force V and bending moment M diagrams: dV/dx = -w (distributed load), dM/dx = V.
  The maximum moment is where V crosses zero.
- Standard results: simply supported, central point load P: M_max = P L / 4. Uniform load w:
  M_max = w L² / 8. Cantilever, tip load P: M_max = P L at the wall. Uniform load: w L² / 2.
- Flexure formula: σ = M y / I. Maximum at the outer fibre: σ_max = M c / I = M / Z (section
  modulus Z = I / c).
- Second moment of area: rectangle b h³ / 12 (h in the bending direction), solid circle π d⁴ / 64,
  I-beams put material far from the neutral axis, which is why they are efficient.
  Parallel axis theorem: I = I_c + A d².
- Shear stress in beams: τ = V Q / (I b); for a rectangle τ_max = 1.5 V / A at the neutral axis.
- Intuition: bending stress is zero at the neutral axis and grows linearly outward; doubling
  depth h makes a rectangular beam 8 times stiffer and 4 times stronger.

## Beam deflection
- Governing equation: E I d²v/dx² = M(x). Integrate twice and apply boundary conditions.
- Standard results: cantilever, tip load: δ = P L³ / (3 E I). Cantilever, uniform load:
  δ = w L⁴ / (8 E I). Simply supported, central load: δ = P L³ / (48 E I). Simply supported,
  uniform load: δ = 5 w L⁴ / (384 E I).
- Superposition: in linear elastic problems deflections from separate loads add.
- Serviceability: deflection limits like L/250 or L/360 often govern design before strength does.

## Combined stress, Mohr's circle and failure theories
- 2D stress transformation: σ_avg = (σx + σy)/2, R = sqrt(((σx - σy)/2)² + τxy²).
  Principal stresses σ1,2 = σ_avg ± R; maximum in-plane shear = R.
- Mohr's circle: centre σ_avg, radius R. Rotating the element by θ rotates the circle point by 2θ.
- Ductile materials, von Mises: σ_vm = sqrt(σ1² - σ1σ2 + σ2²) (plane stress). General:
  σ_vm = sqrt(σx² + σy² - σxσy + 3τxy²). Yield when σ_vm = S_y. Factor of safety n = S_y / σ_vm.
- Tresca (maximum shear): yield when σ1 - σ3 = S_y. More conservative than von Mises.
- Brittle materials: maximum normal stress or Mohr-Coulomb, because they are weaker in tension.
- Combined loading: add stresses from axial load, bending and torsion at the critical point, then
  apply a failure theory. For a shaft with bending M and torque T:
  σ = 32 M / (π d³), τ = 16 T / (π d³).

## Buckling of columns
- Euler critical load: P_cr = π² E I / (K L)², with effective length factor K:
  pinned-pinned 1, fixed-free 2, fixed-pinned 0.7, fixed-fixed 0.5.
- Slenderness ratio L_e / r with r = sqrt(I / A). Euler applies to slender columns; short columns
  fail by yielding (use Johnson's parabola in between).
- Buckling happens about the axis with the smallest I. It is a stability failure, and can occur
  well below the yield stress.

## Energy methods and indeterminate problems
- Strain energy: axial U = F² L / (2 A E), bending U = ∫ M² / (2 E I) dx.
- Castigliano's theorem: deflection at a load = ∂U / ∂P. Handy for curved beams and frames.
- Indeterminate problems: combine equilibrium, compatibility (how deformations fit together)
  and material laws. Example: a bar fixed at both ends and heated has σ = -E α ΔT.
