# bridgecalc

[Español](README.md) · **English**

Traffic loads, envelopes and bridge checks in Python.

[![CI](https://github.com/jmurgass99/bridgecalc/actions/workflows/ci.yml/badge.svg)](https://github.com/jmurgass99/bridgecalc/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

## What it does

- AASHTO LRFD HL-93 envelopes for simple spans and for continuous girders by influence lines.
- EN 1991-2 load models LM1, LM2 and LM3, the Spanish IAP-11 and the Chilean 44 t truck.
- Distribution factors, AASHTO and EN 1990 combinations, and LRFR load rating.
- Seismic: AASHTO spectrum, Mononobe-Okabe thrust, EN 1998-2 ductility, pier pushover and fragility.
- Grillage for SAP2000 and export to Revit and AutoCAD.

## Install

```bash
pip install git+https://github.com/jmurgass99/bridgecalc.git
```

Optional extras: `api`, `dxf`, `memos`. Only base dependency: `numpy`.

## Example

HL-93 envelope for a 30 m simple span:

```python
from bridgecalc.loads.hl93 import hl93_envelope

r = hl93_envelope(30.0)
print(round(r["M_max_kNm"]), round(r["V_max_kN"], 1))   # 3787 531.6
```

More cases in [`examples/`](examples).

## What it does not do

- Bridge design: there is no finite element model of its own, construction stages, creep, shrinkage, prestress losses or fatigue.
- Codes it only approximates: the `multi_code` modules (AS 5100.2 and Colombia) and the `lm3_special` convoys are marked as not cross-checked.
- Seismic capacity of an existing pier: pushover uses a simplified moment-curvature, valid to compare alternatives, not to assess.
- Complex concrete sections: `design` uses an equivalent rectangular section with fixed β and θ.

Details are in [docs/LIMITACIONES.md](docs/LIMITACIONES.md) (in Spanish).

## Tests

```bash
pip install -e ".[test]"
pytest -q
```

## License

MIT. See [LICENSE](LICENSE). Author: [Jesús Murgas](https://github.com/jmurgass99).
