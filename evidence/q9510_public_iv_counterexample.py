"""q9510: an exact counterexample using only the public IV graph and four margins.

Z=0 global company, Z=1 local company; X=1 clean water; Y=1 cholera.
H is binary with P(H=0)=P(H=1)=1/2 and independent of Z.
The CPTs can be implemented by independent Uniform noises U_X and U_Y.
Because P(X=1|Z=1,H) >= P(X=1|Z=0,H) in both H strata, shared
U_X thresholds additionally make the instrument monotone for every unit.
No source-gold or saved response is edited. No model/network call is made.
"""
from fractions import Fraction as F
import json

p_h = [F(1, 2), F(1, 2)]
# Each row indexes H=0,H=1.
p_x = {
    0: [F(9, 70), F(137, 350)],   # global company
    1: [F(7, 10), F(21, 50)],    # local company
}
p_y = {
    0: [F(26, 125), F(9, 10)],   # dirty water
    1: [F(177, 250), F(0)],      # clean water
}

assert all(F(0) <= v <= F(1) for table in (p_x, p_y)
           for row in table.values() for v in row)
assert all(p_x[1][h] >= p_x[0][h] for h in (0, 1))

def observational(z):
    px = sum(p_h[h] * p_x[z][h] for h in (0, 1))
    py = sum(p_h[h] * ((1-p_x[z][h])*p_y[0][h]
                      + p_x[z][h]*p_y[1][h]) for h in (0, 1))
    return px, py

global_px, global_py = observational(0)
local_px, local_py = observational(1)
ate = sum(p_h[h] * (p_y[1][h]-p_y[0][h]) for h in (0, 1))
wald = (local_py-global_py)/(local_px-global_px)

assert (global_px, local_px, global_py, local_py) == (
    F(26, 100), F(56, 100), F(41, 100), F(54, 100))
assert ate == F(-1, 5)
assert wald == F(13, 30)

values = {
    "P_clean_global": global_px, "P_clean_local": local_px,
    "P_cholera_global": global_py, "P_cholera_local": local_py,
    "ATE_clean_on_cholera": ate, "Wald_ratio": wald,
}
print(json.dumps({
    "exact": {k: str(v) for k, v in values.items()},
    "decimal": {k: float(v) for k, v in values.items()},
    "instrument_monotonicity_compatible": True,
    "all_assertions_passed": True,
}, indent=2))

