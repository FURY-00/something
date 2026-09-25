# Dynamics, Vibrations and Control

Core question: how do forces make things move, and how do systems oscillate and respond?

## Kinematics
- Particle: v = dr/dt, a = dv/dt. Constant acceleration: v = v0 + a t, s = v0 t + a t²/2,
  v² = v0² + 2 a s.
- Normal-tangential: a_t = dv/dt, a_n = v² / ρ (towards the centre of curvature).
- Rigid body in plane motion: v_B = v_A + ω × r_B/A; a_B = a_A + α × r_B/A - ω² r_B/A.
- Instantaneous centre of zero velocity: the point the body rotates about at that instant.
  Rolling without slipping: v = ω r, a = α r.

## Kinetics: Newton, work-energy, impulse-momentum
- Newton: ΣF = m a for particles; for rigid bodies also ΣM_G = I_G α (about the centre of mass).
- Mass moment of inertia: solid cylinder about its axis m r²/2, thin rod about its centre
  m L²/12 (about an end m L²/3), solid sphere 2 m r²/5. Parallel axis: I = I_G + m d².
- Work-energy: T1 + ΣU = T2, with T = m v²/2 + I_G ω²/2. Best when forces and positions are
  known and time isn't needed. Conservative forces: T + V is constant (V = m g h + k x²/2).
- Impulse-momentum: ∫F dt = Δ(m v); angular ∫M dt = Δ(I ω). Best for impacts and time.
- Impacts: coefficient of restitution e = (separation speed)/(approach speed); e = 1 elastic,
  e = 0 perfectly plastic. Momentum is conserved during a short impact.
- Choosing the method: need accelerations? Newton. Speeds at positions? Energy. Collisions or
  time? Momentum.

## Free vibration
- Single degree of freedom: m ẍ + c ẋ + k x = F(t).
- Natural frequency ω_n = sqrt(k / m) (rad/s); f_n = ω_n / 2π (Hz); period T = 1 / f_n.
  Static deflection shortcut: ω_n = sqrt(g / δ_st).
- Damping ratio ζ = c / (2 sqrt(k m)). ζ < 1 underdamped (oscillates), ζ = 1 critically damped
  (fastest return without overshoot), ζ > 1 overdamped. Damped frequency ω_d = ω_n sqrt(1 - ζ²).
- Logarithmic decrement δ = ln(x_n / x_{n+1}) ≈ 2π ζ for small damping. That's how damping is
  measured from a test.
- Springs in parallel add (k = k1 + k2); in series add reciprocals (1/k = 1/k1 + 1/k2).
  Beam stiffness: cantilever tip k = 3 E I / L³; simply supported centre k = 48 E I / L³.

## Forced vibration and resonance
- Harmonic force F0 sin ωt: steady amplitude X = (F0/k) / sqrt((1 - r²)² + (2 ζ r)²), r = ω / ω_n.
- Resonance at r ≈ 1: the amplitude is limited only by damping (peak ≈ (F0/k) / (2ζ)).
- Phase lag goes from 0 (r << 1) through 90° (r = 1) to 180° (r >> 1).
- Vibration isolation: transmissibility < 1 only when r > sqrt(2). Soft mounts isolate by
  pushing ω_n well below the forcing frequency.
- Rotating unbalance: forcing m e ω². Base excitation: same transmissibility curve.

## Multi-degree-of-freedom systems and modes
- M ẍ + K x = 0 leads to the eigenvalue problem (K - ω² M) φ = 0: natural frequencies ω_i and
  mode shapes φ_i. An n-DOF system has n modes.
- Continuous systems (beams, plates) have infinitely many modes. For a cantilever the first
  frequency is ω1 = 1.875² sqrt(E I / (ρ A L⁴)).
- Modal analysis in FEA gives exactly these. Keep operating frequencies away from them
  (a common rule is at least 20 percent separation).
- Tuned mass dampers: a small absorber tuned to the troublesome frequency.

## Mechanisms and machines
- Four-bar linkages: Grashof condition s + l ≤ p + q allows a fully rotating link.
- Gear trains: speed ratio = product of driver teeth / product of driven teeth; torque scales
  inversely (minus losses). Power in = power out + losses.
- Cams, flywheels (energy E = I ω²/2, coefficient of fluctuation), balancing of rotating masses.

## Control systems basics
- Transfer function G(s) = output / input in the Laplace domain. First-order system
  K / (τ s + 1): time constant τ, reaches 63 percent in τ, about 98 percent in 4τ.
- Second-order: ω_n² / (s² + 2 ζ ω_n s + ω_n²). Overshoot = exp(-π ζ / sqrt(1 - ζ²)).
- Feedback: closed loop G / (1 + G H). Stability: all poles in the left half-plane.
- PID: P reduces error, I removes steady-state error, D adds damping. Tuning: Ziegler-Nichols
  as a start, then adjust.
- Frequency response: Bode plots, gain and phase margins (aim for a phase margin of about 45°+).
