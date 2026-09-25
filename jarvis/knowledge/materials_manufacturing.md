# Materials and Manufacturing

Core question: why do materials behave the way they do, and how are parts made?

## Structure and properties
- Metals: crystal structures BCC (iron at room temperature, strong, ductile-to-brittle transition),
  FCC (aluminium, copper, austenite: ductile even when cold), HCP (titanium, magnesium: less ductile).
- Strengthening: work hardening (dislocations tangle), grain refinement (Hall-Petch: smaller grains
  are stronger), solid solution strengthening, precipitation hardening (aluminium 2xxx/6xxx/7xxx),
  martensitic transformation (quenched steel).
- Properties to know: yield and ultimate strength, ductility (elongation), hardness (Brinell,
  Rockwell, Vickers), toughness (Charpy energy, fracture toughness K_IC), creep, fatigue strength.
- Fracture mechanics: a crack grows unstably when K = Y σ sqrt(π a) ≥ K_IC. Tough materials
  tolerate bigger cracks.

## Steels and heat treatment
- The iron-carbon diagram: ferrite, austenite, cementite, pearlite; eutectoid at 0.76 percent carbon
  and 727 °C.
- Annealing (soft, stress-free), normalising (refined grain), quenching (hard, brittle martensite),
  tempering (trade hardness for toughness), case hardening (carburising, nitriding, induction:
  hard surface, tough core).
- Carbon content: low (<0.3 percent, weldable, formable), medium (0.3-0.6, shafts and gears),
  high (>0.6, springs and tools). Alloying: Cr and Ni (stainless, hardenability), Mo (creep),
  V (grain size).
- Stainless steels: austenitic 304/316 (non-magnetic, corrosion-resistant), martensitic 410/420
  (hardenable), ferritic 430, duplex.

## Polymers, ceramics and composites
- Thermoplastics (remeltable: PE, PP, ABS, nylon, PC, PEEK) versus thermosets (cured: epoxy,
  phenolic). The glass transition temperature T_g decides stiffness at service temperature.
  Polymers creep and are temperature-sensitive.
- Ceramics: very hard, heat and wear resistant, brittle, strong in compression.
- Composites: fibres (glass, carbon, aramid) in a matrix. Anisotropic: strong along the fibres.
  Rule of mixtures E_c = V_f E_f + V_m E_m along the fibres.

## Corrosion and wear
- Galvanic corrosion when dissimilar metals touch in an electrolyte; the more anodic metal corrodes.
- Protection: coatings, galvanising (sacrificial zinc), cathodic protection, material choice, design
  that drains water and avoids crevices.
- Wear types: adhesive, abrasive, fatigue (pitting), corrosive. Archard: wear volume ∝ load x sliding
  distance / hardness.

## Manufacturing processes
- Casting (sand, die, investment): complex shapes, porosity risk, needs draft angles and uniform walls.
- Forming: forging (strong grain flow), rolling, extrusion, sheet metal (bending with a minimum
  bend radius, springback, deep drawing).
- Machining: turning, milling, drilling, grinding. Cutting speed V = π D N; Taylor tool life
  V T^n = C. Surface finish and tolerances depend on the process (grinding best).
- Joining: welding (MIG, TIG, stick, spot, laser: heat-affected zone and distortion), brazing,
  adhesives, fasteners.
- Additive manufacturing: FDM (plastics), SLA (resin), SLS and DMLS (powders): design freedom,
  anisotropy, supports, surface finish.
- Injection moulding: uniform wall thickness, draft angles, ribs instead of thick sections, gate
  location, avoiding sink marks.

## Design for manufacture and assembly (DFMA)
- Fewer parts, standard parts, generous tolerances where function allows, self-locating features,
  top-down assembly, avoid deep narrow pockets and sharp internal corners in machined parts
  (end mills are round).
