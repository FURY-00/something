# Engineering calculator guide

Write a complete Python script that solves the problem and prints the results. The user hears
a summary of what you print, so print clearly labelled values with units, in the order of the
solution. Each script runs fresh.

## How to write a good solution script
- Put every given value in a variable with its SI unit in a comment: `L = 2.0  # m`.
- Convert to SI first (mm to m, kN to N, MPa to Pa, degC to K where thermodynamics needs it).
- Follow the physics step by step and print the intermediate results that a teacher would want
  to see: `print(f"Moment of inertia I = {I:.3e} m^4")`.
- Print the final answer last, with sensible significant figures and units.
- Add a sanity check where possible: compare with a limiting case, a known formula, or check units
  and orders of magnitude, and print it ("Check: reactions sum to the applied load").
- Symbolic work (derivations, exact forms, solving equations): use `sp` (sympy). Numerical work:
  `np`, `optimize.fsolve` / `optimize.brentq` for nonlinear equations, `integrate.solve_ivp` for ODEs,
  `integrate.quad` for integrals, `np.linalg.solve` for linear systems.
- Plots: `import matplotlib.pyplot as plt`, draw, label axes with units, add a grid and a title, then
  `save_plot("descriptive_name")`. Only plot when it helps (diagrams, curves vs time or position).
- Don't read or write the user's files unless the problem gives a file path.

## Recipe: beam bending, deflection and stress
```python
L, P, E = 2.0, 5e3, 200e9          # m, N, Pa
b, h = 0.05, 0.10                  # m (h in the bending direction)
I = b * h**3 / 12
M_max = P * L / 4                  # simply supported, central point load
sigma = M_max * (h / 2) / I
delta = P * L**3 / (48 * E * I)
print(f"I = {I:.3e} m^4")
print(f"Max moment = {M_max:.0f} N m, max bending stress = {sigma/1e6:.1f} MPa")
print(f"Mid-span deflection = {delta*1000:.3f} mm (L/{L/delta:.0f})")
```

## Recipe: pipe flow pressure drop (Colebrook equation)
```python
rho, mu = 1000.0, 1.0e-3           # water, kg/m^3, Pa s
D, L, eps, Q = 0.05, 100.0, 0.045e-3, 0.004   # m, m, m, m^3/s
V = Q / (math.pi * D**2 / 4)
Re = rho * V * D / mu
if Re < 2300:
    f = 64 / Re
else:
    colebrook = lambda f: 1/math.sqrt(f) + 2*math.log10(eps/(3.7*D) + 2.51/(Re*math.sqrt(f)))
    f = optimize.brentq(colebrook, 1e-4, 0.2)
dp = f * (L / D) * rho * V**2 / 2
print(f"Velocity {V:.2f} m/s, Re = {Re:.3g} ({'laminar' if Re < 2300 else 'turbulent'})")
print(f"Friction factor f = {f:.4f}")
print(f"Pressure drop = {dp/1000:.1f} kPa, pumping power = {dp*Q:.0f} W")
```

## Recipe: vibration of a damped spring-mass system (ODE)
```python
import matplotlib.pyplot as plt
m, k, c = 2.0, 800.0, 8.0          # kg, N/m, N s/m
wn = math.sqrt(k / m); zeta = c / (2 * math.sqrt(k * m))
sol = integrate.solve_ivp(lambda t, y: [y[1], -(c*y[1] + k*y[0]) / m], (0, 3), [0.01, 0.0],
                          max_step=0.001)
print(f"Natural frequency {wn:.2f} rad/s = {wn/(2*math.pi):.2f} Hz, damping ratio {zeta:.3f}")
plt.plot(sol.t, sol.y[0] * 1000); plt.xlabel("time (s)"); plt.ylabel("displacement (mm)")
plt.title("Free vibration"); plt.grid(True)
save_plot("free_vibration")
```

## Recipe: symbolic derivation with sympy
```python
x, L, w, E, I = sp.symbols("x L w E I", positive=True)
v = sp.Function("v")
# Simply supported beam with a uniform load: E I v'''' = -w
sol = sp.dsolve(E*I*v(x).diff(x, 4) + w, v(x),
                ics={v(0): 0, v(L): 0, v(x).diff(x, 2).subs(x, 0): 0, v(x).diff(x, 2).subs(x, L): 0})
mid = sp.simplify(sol.rhs.subs(x, L/2))
print("Deflection v(x) =", sp.simplify(sol.rhs))
print("Mid-span deflection =", mid, " (the textbook result is -5 w L^4 / (384 E I))")
```

## Recipe: 2D truss by the stiffness method
```python
nodes = np.array([[0, 0], [4, 0], [2, 3]], float)         # m
members = [(0, 1), (0, 2), (1, 2)]
E, A = 200e9, 5e-4                                         # Pa, m^2
K = np.zeros((6, 6))
for i, j in members:
    d = nodes[j] - nodes[i]; Lm = np.hypot(*d); c, s = d / Lm
    k = E * A / Lm * np.outer([-c, -s, c, s], [-c, -s, c, s])
    idx = [2*i, 2*i+1, 2*j, 2*j+1]
    K[np.ix_(idx, idx)] += k
F = np.zeros(6); F[5] = -10e3                              # 10 kN down at node 2
free = [2, 4, 5]                                           # node 0 pinned, node 1 roller in y
u = np.zeros(6); u[free] = np.linalg.solve(K[np.ix_(free, free)], F[free])
for i, j in members:
    d = nodes[j] - nodes[i]; Lm = np.hypot(*d); c, s = d / Lm
    force = E * A / Lm * np.dot([-c, -s, c, s], u[[2*i, 2*i+1, 2*j, 2*j+1]])
    print(f"Member {i}-{j}: {force/1e3:+.2f} kN ({'tension' if force > 0 else 'compression'})")
R = K @ u - F
print(f"Check: vertical reactions sum to {R[1::2].sum()/1e3:.2f} kN (should be 10)")
```

## Recipe: thermodynamic cycle with an ideal gas
```python
k, cp, T1, rp = 1.4, 1.005, 300.0, 10.0      # -, kJ/kg K, K, pressure ratio
T3 = 1400.0                                    # K turbine inlet
T2 = T1 * rp**((k - 1) / k); T4 = T3 / rp**((k - 1) / k)
w_net = cp * ((T3 - T4) - (T2 - T1)); q_in = cp * (T3 - T2)
print(f"T2 = {T2:.0f} K, T4 = {T4:.0f} K")
print(f"Net work = {w_net:.0f} kJ/kg, thermal efficiency = {w_net/q_in*100:.1f} % "
      f"(ideal Brayton formula: {(1 - rp**(-(k-1)/k))*100:.1f} %)")
```
