# Vendored geochemical database

## llnl.dat
- **Source:** USGS PHREEQC v3 distribution — https://github.com/usgs-coupled/phreeqc3 (`database/llnl.dat`).
- **Origin:** LLNL `thermo.com.V8.R6.230` thermodynamic data, reformatted for PHREEQC by the USGS.
- **License:** Public domain (U.S. Geological Survey work).
- **Why vendored:** The `phreeqpython` wheel ships only `phreeqc.dat`, `pitzer.dat`,
  `vitens.dat`, and a `wateq4f_PWN.dat` that fails to register via this IPhreeqc
  build. None carry the full serpentinization mineral set + Fe(2)/Fe(3) redox + the
  H2/O2 aqueous couples needed for Module A (`PhreeqcSerpentinizationProcess`).
  `llnl.dat` has Forsterite, Fayalite, Chrysotile, Brucite, Magnetite, Quartz and
  the H2(g)/O2(g) phases — so dissolved H2 (reducing power) is a real speciation
  output, not a parameterized guess. Vendored so runs + CI are fully offline.
