"""
Constants of the PSE core — every value traces to the master architecture
(`PSE_MASTER_ARCHITECTURE_v4`) or to the agreement `docs/DOGOVOR-PSE-AGENTI.md`
(rule numbers in brackets). INITIAL = an initial declaration for calibration;
it changes only by a new declaration, never by a unit.
"""
from __future__ import annotations

# §0 default profile
SELF_WEIGHT = 0.70
OTHER_WEIGHT_MAX = 0.30
ORGANELLE_BUDGET_TOTAL = 0.30
ORGANELLE_MAX_SINGLE = 0.20
INHERITED_FACTOR = 0.70
FIRST_CONTACT_WO = 0.15
FIRST_CONTACT_WF = 0.15
F_MIN, F_MAX = 1 / 6, 5 / 6

# θ in points [rule 2, 8, 24]
THETA_NOM = 30.0            # every class, every agent starts here
THETA_BAND = 5.0            # 30 ± 5 is room to move, not a fault
K_C = 30.0                  # INITIAL [rule 2]
K_N = 30.0                  # INITIAL [rule 2]

# swing [rule 5, 5a, 23]
PAC_POINTS = 5.0            # |Δθ| ≥ 5 = acute change
AMPLITUDE = 10.0            # INITIAL
WIN_SWING = 30              # moves
WIN_LONG = 10_000           # moves
SCHIZOID_MIN_MOVES = 300    # below: "nedovoljno istorije"
HEALTHY_SIGMA = (1.5, 3.0)
SCHIZOID_SIGMA = 1.0
BORDERLINE_SIGMA = 5.0
BORDERLINE_ACF1 = 0.5
CODEP_MEAN, CODEP_SUSTAINED = 33.0, 35.0
NARC_MEAN, NARC_SUSTAINED = 27.0, 25.0
LEVEL_SIGMA = 2.0
# where a swing is heading [rules 50–52, live test rc5]
MIN_TURNS = 2               # borderline needs a real back-and-forth: ≥ 2 turning points
MIN_SWING_MOVES = 10        # … and at least this many moves in the window
TEND_HORIZON = 30           # "teži ka X" when X is reached within this many moves
TEND_K = (3, 6)             # the last 3–6 sweeps make the envelope
DOCTOR_RULES_VERSION = 2    # bump when the Doctor's reading rules change (re-review)

# absorption §2
ABSORB_RESIDENCY = 1000
ABSORB_ALPHA = 0.10
ABSORB_STABLE_STEPS = 100
BOUNDARY_INITIAL_ALPHA = 0.10

# reader [rule 15]
READER_GAP = 10.0           # reader–rules gap > 10 points = suspicion

# lifespan [rule 21, 22]
N_MAX_DEFAULT = 1000        # INITIAL
EXTEND_FACTOR = 1.5
MAX_EXTENSIONS_RUNNING = 3

# fusion §4
FUSION_RANGE = (25.0, 35.0)
COMPOSITE_RANGE = (28.0, 32.0)

# suspicion [rule 20]
BURST_MOVES, BURST_SECONDS = 20, 10.0
SAME_ERROR_RUN = 3

# vote weights [rule 17]
WEIGHTS_MIN_CASES = 200
WEIGHTS_MAX_STEP = 0.10     # ±10 % per proposal
WEIGHTS_PERIOD_S = 7 * 24 * 3600

# attractor labels (H = healthy; N/B/C/S as in §7)
HEALTHY, NARCISSISTIC, BORDERLINE, CODEPENDENT, SCHIZOID = "H", "N", "B", "C", "S"
NOT_ENOUGH = "?"            # not enough history for a verdict
