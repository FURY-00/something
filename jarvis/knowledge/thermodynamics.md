# Thermodynamics

Core question: how is energy converted between heat and work, and what limits it?

## Systems, properties and the zeroth law
- Closed system (control mass): no mass crosses the boundary. Open system (control volume): mass flows.
- State properties: p, T, v (specific volume), u, h = u + p v, s. Two independent intensive
  properties fix the state of a simple pure substance.
- Always use absolute temperature (K) in thermodynamic equations. Gauge vs absolute pressure:
  p_abs = p_gauge + p_atm (101.325 kPa).
- Zeroth law: two bodies in thermal equilibrium with a third are in equilibrium with each other.

## Pure substances and property tables
- Phases: compressed liquid, saturated mixture, superheated vapour. Quality x = m_vapour / m_total;
  in the dome v = v_f + x v_fg, same for u, h and s.
- Steam tables: look up saturation first (T_sat at the given p). Compare to decide the phase.
- Ideal gas: p v = R T (R = 0.287 kJ/kg·K for air), p V = m R T. Valid at low pressure and high
  temperature relative to the critical point. Δu = c_v ΔT, Δh = c_p ΔT, c_p - c_v = R, k = c_p/c_v
  (1.4 for air).

## First law
- Closed system: Q - W = ΔU (+ ΔKE + ΔPE). Sign convention here: Q in and W out are positive.
- Boundary work W = ∫ p dV. Constant pressure: p ΔV. Isothermal ideal gas: m R T ln(V2/V1).
  Polytropic p V^n = const: W = (p2 V2 - p1 V1) / (1 - n).
- Steady-flow energy equation: Q̇ - Ẇ = ṁ [(h2 - h1) + (V2² - V1²)/2 + g (z2 - z1)].
- Devices: turbines and compressors (usually adiabatic, Ẇ = ṁ Δh), nozzles (convert h to speed),
  throttling valves (h1 = h2), heat exchangers (energy balance between two streams), mixing chambers.
- Common mistakes: mixing kJ and J, forgetting that V²/2 in m²/s² is J/kg (divide by 1000 for kJ/kg).

## Second law and entropy
- Kelvin-Planck: no cycle can turn all of the heat into work. Clausius: heat doesn't flow from
  cold to hot on its own.
- Carnot efficiency (the upper limit): η = 1 - T_L / T_H. Carnot COP: refrigerator T_L / (T_H - T_L),
  heat pump T_H / (T_H - T_L).
- Entropy: ds = δq_rev / T. For an isolated system ΔS ≥ 0; entropy generation measures
  irreversibility (friction, heat transfer across finite ΔT, mixing, unrestrained expansion).
- Ideal gas: Δs = c_p ln(T2/T1) - R ln(p2/p1). Isentropic: T2/T1 = (p2/p1)^((k-1)/k).
- Isentropic efficiency: turbine η = actual work / isentropic work; compressor η = isentropic / actual.
- Exergy: the maximum useful work relative to the surroundings.

## Power cycles
- Rankine (steam power plants): pump, boiler, turbine, condenser. η = (W_turbine - W_pump) / Q_in.
  Raised by higher boiler pressure and temperature, superheat, reheat, regeneration, lower
  condenser pressure. Watch the turbine exit quality (keep it above about 0.88).
- Brayton (gas turbines): compressor, combustor, turbine. Ideal η = 1 - 1 / r_p^((k-1)/k).
  Back work ratio is large (about 40-60 percent). Improved by regeneration, intercooling, reheat.
- Otto (petrol engines): η = 1 - 1 / r^(k-1) with compression ratio r. Diesel adds the cutoff
  ratio and is less efficient at the same r but runs at higher r.
- Combined cycle: Brayton exhaust drives a Rankine cycle, reaching about 60 percent.

## Refrigeration, heat pumps and psychrometrics
- Vapour-compression cycle: compressor, condenser, expansion valve (h constant), evaporator.
  COP_R = Q_L / W_in. Refrigerants are read from tables or p-h charts.
- Psychrometrics: humidity ratio ω = 0.622 p_v / (p - p_v); relative humidity φ = p_v / p_sat.
  Dew point, wet bulb, cooling with dehumidification, heating, evaporative cooling, all on the
  psychrometric chart.

## Combustion basics
- Stoichiometric air-fuel ratio from balancing the reaction; excess air lowers the flame temperature.
- Heating value: higher (water condensed) and lower (water as vapour).
- Adiabatic flame temperature: products' enthalpy = reactants' enthalpy.
