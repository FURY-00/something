# Heat Transfer

Core question: how fast does heat move, by conduction, convection and radiation?

## Conduction
- Fourier's law: q = -k dT/dx (W/m²). Conductivity k: copper ≈ 400, aluminium ≈ 200, steel ≈ 50,
  stainless ≈ 15, glass ≈ 1, water ≈ 0.6, insulation ≈ 0.03-0.05, air ≈ 0.026 W/m·K.
- Plane wall, steady: Q = k A (T1 - T2) / L. Thermal resistance R = L / (k A); resistances in
  series add, in parallel combine like electrical resistors. Q = ΔT / ΣR.
- Cylinder wall: R = ln(r2/r1) / (2 π k L). Sphere: R = (1/r1 - 1/r2) / (4 π k).
- Critical insulation radius for a cylinder r_cr = k / h: adding insulation to a thin wire can
  increase heat loss.
- Heat generation in a plane wall: parabolic temperature profile, T_max - T_s = q̇ L² / (2 k)
  (half-thickness L).
- The heat equation: ∂T/∂t = α ∇²T + q̇/(ρ c), thermal diffusivity α = k / (ρ c_p).

## Convection
- Newton's law of cooling: Q = h A (T_s - T_∞). Convection resistance R = 1 / (h A).
- Typical h: free convection in air 5-25, forced air 25-250, forced water 100-20,000, boiling or
  condensing 2,500-100,000 W/m²·K.
- Nusselt number Nu = h L / k (dimensionless h). Prandtl Pr = ν / α (air ≈ 0.7, water ≈ 7).
  Grashof and Rayleigh numbers (Ra = Gr Pr) govern natural convection.
- Correlations: laminar flat plate Nu_x = 0.332 Re_x^0.5 Pr^(1/3); turbulent pipe flow
  (Dittus-Boelter) Nu = 0.023 Re^0.8 Pr^n (n = 0.4 heating, 0.3 cooling); laminar fully developed
  pipe Nu = 3.66 (constant wall temperature) or 4.36 (constant heat flux).
- Evaluate fluid properties at the film temperature (T_s + T_∞)/2 for external flow.

## Fins and extended surfaces
- Fin parameter m = sqrt(h P / (k A_c)). A long fin loses Q = sqrt(h P k A_c) θ_b.
- Fin efficiency η_f = Q_actual / Q_if-the-whole-fin-were-at-base-temperature; fins help most
  when h is small (gases) and k is high.
- Heat sinks: many thin, closely spaced fins; there is an optimum spacing for natural convection.

## Transient conduction
- Biot number Bi = h L_c / k (L_c = V / A_s). If Bi < 0.1, use the lumped model:
  (T - T_∞) / (T_i - T_∞) = exp(-t / τ), time constant τ = ρ c V / (h A).
- For Bi > 0.1, the interior lags the surface: use Heisler charts, one-term series solutions,
  or a numerical (FEA) transient analysis.
- Fourier number Fo = α t / L² is dimensionless time.

## Radiation
- Stefan-Boltzmann: blackbody E = σ T⁴, σ = 5.67e-8 W/m²·K⁴. Real surfaces: ε σ T⁴ with
  emissivity ε (polished metal 0.05, oxidised metal 0.6-0.8, paint and skin about 0.9).
- Small body in large surroundings: Q = ε σ A (T_s⁴ - T_surr⁴), temperatures in kelvin.
- View factors between surfaces; radiation shields reduce exchange dramatically.
- Linearised radiation coefficient h_r ≈ 4 ε σ T_m³ lets radiation combine with convection.

## Heat exchangers
- Overall coefficient: 1/(U A) = 1/(h_i A_i) + R_wall + R_fouling + 1/(h_o A_o).
- LMTD method: Q = U A ΔT_lm, ΔT_lm = (ΔT1 - ΔT2) / ln(ΔT1/ΔT2), with a correction factor F for
  cross-flow and multi-pass designs. Counterflow beats parallel flow.
- Effectiveness-NTU method: ε = Q / Q_max, Q_max = C_min (T_h,in - T_c,in), NTU = U A / C_min.
  Use it when outlet temperatures are unknown.

## Boiling and condensation
- Boiling curve: natural convection, nucleate boiling (very high h), critical heat flux (burnout
  risk), film boiling (Leidenfrost).
- Film condensation (Nusselt theory) versus dropwise condensation (much higher h).
