#!/usr/bin/env python3
"""
NorteIII_MC.py (version 2) -- Monte Carlo methane-balance and techno-economic decision model for landfill-gas recovery and use at a very large
landfill (CEAMSE Norte III, Buenos Aires, as case study).

    python NorteIII_MC.py --test            # automated tests (mass, carbon and energy closure, units, limiting and benchmark cases)
    python NorteIII_MC.py --run             # full run: results.json, CSV tables, figures

Changes from version 1 (October 2026 review):
  * Calibration in two periods. The satellite estimates (2019-2022) are compared with the gas balance AT THE OBSERVATION DATE (historical
    period: capture as reported around 2022); the decision is made for the contemporary period (2025-2026 capture) with generation carried forward
    by an uncertain growth factor. Three observation-error models replace the fixed acceptance window as the only option: a uniform window
    (18-38 t/h), a Gaussian likelihood (28 +/- 6 t/h) and a lognormal likelihood (median 28 t/h, sigma_ln 0.35, the base case); posterior samples
    are drawn by importance resampling. The generation prior is wider.
  * Explicit methane, carbon and energy balances for every scenario, with closure tests; climate benefits are computed from the balances and
    cross-checked against the incremental formulas. Corrections found in the audit: plant fugitive methane is now removed from the product stream;
    biomethane not sold on the GNC-only route is flared (it was previously unaccounted); compression electricity is route-specific (it was the
    GNC value for every route); the power alternative now has a climate account (grid displacement) as well as an NPV.
  * Argentine economic inputs anchored to dated benchmarks (tag B): PIST gas price (Res. SE 487/2025), delivered gas cost and retail GNC price
    (2025), wholesale electricity cost (CAMMESA-based, 2024-2025), RenovAr landfill-gas awards (contracted tariff), capital-goods import duties
    (Decree 513/2025, Mercosur CET), country risk (EMBI 2025), landfill-gas credit prices (2025). The capital premium is built from the imported
    share, the duty and logistics; tax, financing structure and credit eligibility are explicit robustness variants.
  * Robustness: correlated inputs (Iman-Conover), alternative marginals, widened priors, alternative cover structures, contracted vs merchant
    electricity, after-tax and WACC discounting, expected credit revenue, and a time-resolved first-order-decay gas trajectory.

Tags: R operator-reported or published programme value; L literature or standard value; B dated market or regulatory benchmark;
A assumed by the author. Nothing here is a site measurement; outputs are conditional on the stated priors.
"""
import argparse
import json
import os
import sys

import numpy as np
from scipy import stats
from scipy.stats import qmc

# ------------------------------------------------------------------ constants
LHV = 9.94          # kWh per Nm3 CH4 (lower heating value) [L]
RHO = 0.717         # kg CH4 per Nm3 [L]
GWP100 = 27.0       # AR6, non-fossil CH4 [L]
GWP20 = 79.7        # AR6, non-fossil CH4 [L]
H = 8760.0          # h/yr
T = 20              # project horizon, yr
X_PROD = 0.97       # CH4 fraction of upgraded biomethane
EF_NG = 0.202       # tCO2 per MWh_th natural gas combustion [L]
C_PER_NM3 = 12.011 / 22.414 / 1000.0   # t C per Nm3 CH4 (0.536 kg C/Nm3)
TAX = 0.35          # corporate income tax, top bracket (Law 27,630) [B]
DEP_YR = 10         # straight-line depreciation period, yr [A]
E_COMP = {"gnc": 0.25, "pipe": 0.10}   # kWh per Nm3 product, compression for GNC dispensing / pipeline injection [L]
ETA_MAX = 0.95      # physical consistency cap on collection efficiency
SAT_LO, SAT_HI = 18.0, 38.0            # t CH4/h, GHGSat September 2022 range
SAT_MED, SAT_SD, SAT_SLN = 28.0, 6.0, 0.35   # central estimate (Maasakkers et al. 2022 / SRON), Gaussian sd, lognormal sigma
LIKELIHOODS = ("lognormal", "gauss", "window")

# ------------------------------------------------------------------ parameters (name, dist, args, tag, description)
P = [
 # gas supply, historical (observation) period
 ("Qcoll22", "tri", (12000, 13100, 14000), "A", "collected biogas around 2022 (satellite period), Nm3/h; 13,100 peak in 2013, 13,800 in 2025"),
 ("Awaste",  "tri", (14000, 16500, 19000), "R", "waste to Norte III, t/day (~18,000 reported)"),
 ("L0",      "tri", (50, 100, 170),        "L", "CH4 generation potential, Nm3 CH4 per t waste (inventory 100, CAA 170)"),
 ("fss",     "tri", (0.30, 0.60, 0.95),    "A", "fraction of steady-state generation reached (age/decay/lag)"),
 ("xCH4",    "tri", (0.42, 0.50, 0.57),    "A", "CH4 fraction of landfill gas"),
 ("ox",      "tri", (0.05, 0.15, 0.35),    "L", "cover methane oxidation fraction"),
 # contemporary (decision) period
 ("g_t",     "tri", (0.95, 1.05, 1.15),    "A", "generation 2025-26 relative to 2022"),
 ("Qcoll",   "tri", (13000, 14800, 16500), "R", "collected biogas 2025-26, Nm3/h (13,800 in 2025; 16,000 Apr 2026)"),
 ("P_el",    "tri", (23, 28, 33),          "R", "installed biogas power, MW (23 in 2020; 33 planned 2026)"),
 ("CF_el",   "tri", (0.70, 0.85, 0.93),    "A", "engine capacity factor"),
 ("eta_el",  "tri", (0.36, 0.40, 0.43),    "L", "engine electrical efficiency"),
 ("d_f",     "tri", (0.95, 0.98, 0.995),   "L", "flare/engine CH4 destruction efficiency"),
 # S1 wellfield optimisation
 ("dEta1",   "tri", (0.0, 0.02, 0.06),     "A", "S1 absolute gain in collection efficiency (of generation)"),
 ("capex_s1", "tri", (0.5, 1.5, 4.0),      "A", "S1 capex, MUSD"),
 ("opex_s1", "tri", (0.15, 0.4, 1.0),      "A", "S1 opex, MUSD/yr"),
 # cover
 ("f_hot",   "tri", (0.10, 0.25, 0.50),    "A", "flux fraction passing covered area"),
 ("h_e",     "tri", (1.5, 3.0, 6.0),       "A", "hot-spot flux enrichment over mean"),
 ("A_act",   "tri", (100, 200, 400),       "A", "actively emitting area, ha"),
 ("eps_conv", "tri", (0.30, 0.60, 0.85),   "A", "conventional cover: fraction of arriving CH4 blocked"),
 ("eps_coat", "tri", (0.10, 0.45, 0.85),   "A", "experimental coating: fraction blocked"),
 ("s_c",     "tri", (0.05, 0.35, 0.75),    "A", "share of blocked CH4 captured by extraction"),
 ("delta_ox", "tri", (0.2, 0.6, 1.0),      "A", "fractional loss of oxidation under cover"),
 ("rho_r",   "uni", (0.0, 1.0),            "A", "oxidation of redirected gas relative to ox"),
 ("c_conv",  "tri", (80, 150, 300),        "A", "conventional cover cost, kUSD/ha"),
 ("c_coat",  "tri", (100, 250, 700),       "A", "experimental coating cost, kUSD/ha"),
 ("om_cov",  "tri", (0.015, 0.03, 0.05),   "A", "cover O&M, fraction of capex per yr"),
 ("life_conv", "tri", (15, 25, 30),        "A", "conventional cover life, yr"),
 ("life_coat", "tri", (4, 8, 15),          "A", "coating life, yr"),
 # economy-wide (Argentina)
 ("r",       "tri", (0.08, 0.12, 0.18),    "B", "real USD discount rate (EMBI 2025: 561 to >1,200 bps; 569 bps Dec 2025)"),
 ("f_imp",   "tri", (0.5, 0.7, 0.9),       "A", "imported share of equipment capex"),
 ("duty",    "tri", (0.0, 0.126, 0.20),    "B", "import duty on capital goods (0% BK regime; 12.6% Decree 513/2025; 20% Mercosur CET)"),
 ("logist",  "tri", (0.03, 0.08, 0.15),    "A", "freight, logistics and FX cost on imports, fraction"),
 ("m_p",     "logn", (0.25,),              "A", "realised-price multiplier (tariff/FX risk), mean 1"),
 # upgrading
 ("avail_firm", "tri", (0.6, 0.85, 1.0),   "A", "fraction of surplus gas contractually firm"),
 ("uptime",  "tri", (0.80, 0.90, 0.95),    "A", "plant availability"),
 ("rec",     "tri", (0.90, 0.95, 0.985),   "L", "CH4 recovery in upgrading"),
 ("tail_ox", "uni", (0.0, 0.95),           "A", "fraction of tail-gas CH4 slip oxidised"),
 ("fug_plant", "tri", (0.002, 0.006, 0.012), "L", "plant fugitive CH4, fraction of CH4 in"),
 ("capex_up", "tri", (1800, 3000, 5000),   "A", "upgrader capex, USD per Nm3/h raw capacity"),
 ("e_up",    "tri", (0.20, 0.28, 0.40),    "L", "upgrading electricity, kWh/Nm3 raw"),
 ("c_el",    "tri", (70, 95, 130),         "B", "electricity purchase cost, USD/MWh (wholesale monomic ~87-91 USD/MWh 2024-25 plus network)"),
 ("om_up",   "tri", (0.03, 0.04, 0.06),    "A", "upgrader O&M, fraction of capex per yr"),
 ("lab_up",  "tri", (0.15, 0.25, 0.45),    "A", "labour/other, MUSD/yr"),
 ("capex_gv", "tri", (400, 800, 1500),     "A", "GNC compression capex, USD per Nm3/h product"),
 ("capex_gf", "tri", (0.3, 0.8, 2.0),      "A", "GNC fixed capex, MUSD"),
 ("p_gnc",   "tri", (0.13, 0.19, 0.40),    "B", "bio-GNC net plant-gate price, USD/Nm3 (delivered station gas ~0.15, retail ~0.40-0.45, 2025)"),
 ("p_pipe",  "tri", (0.07, 0.10, 0.16),    "B", "pipeline net plant-gate price, USD/Nm3 (PIST 2.94-2.98 USD/MMBtu, Dec 2025)"),
 ("D_gnc",   "tri", (300, 1000, 3000),     "A", "bio-GNC anchor demand, Nm3/h"),
 ("dist_km", "tri", (2, 8, 20),            "A", "distance to injection point, km"),
 ("c_km",    "tri", (0.3, 0.6, 1.2),       "A", "pipeline spur cost, MUSD/km"),
 ("c_inj",   "tri", (0.5, 1.0, 2.0),       "A", "injection/metering station, MUSD"),
 # power alternative
 ("capex_pw", "tri", (1100, 1300, 1700),   "R", "gas-engine power capex, USD/kW (RenovAr landfill-gas ref 1.3 MUSD/MW)"),
 ("p_el",    "tri", (60, 75, 95),          "B", "electricity sale price, merchant/MAT, USD/MWh (marginal cost 69, monomic ~87-91, 2024-25)"),
 ("p_el_k",  "tri", (110, 125, 135),       "B", "electricity sale price, RenovAr-type contract, USD/MWh (landfill-gas awards 128-130, 2017)"),
 ("cf_pw",   "tri", (0.80, 0.88, 0.93),    "A", "new engines capacity factor"),
 ("eta_pw",  "tri", (0.36, 0.40, 0.43),    "L", "new engines electrical efficiency"),
 ("om_pw",   "tri", (0.03, 0.045, 0.07),   "A", "engine O&M, fraction of capex per yr"),
 # buffer
 ("var_loss", "uni", (0.05, 0.25),         "A", "flow-variability loss without buffer"),
 ("zeta",    "uni", (0.5, 0.9),            "A", "fraction of variability loss removed by buffer"),
 ("capex_buf", "tri", (0.3, 0.8, 2.0),     "A", "buffer capex, MUSD"),
 ("leak_buf", "tri", (0.002, 0.005, 0.01), "A", "buffer CH4 leakage, fraction of throughput"),
 # S7
 ("f_pv",    "uni", (0.1, 0.5),            "A", "share of upgrader electricity from on-site PV"),
 ("dEta_ad", "tri", (0.0, 0.01, 0.03),     "A", "adaptive-control gain in collection efficiency"),
 ("capex_ad", "tri", (0.2, 0.5, 1.2),      "A", "adaptive control capex, MUSD"),
 ("opex_ad", "tri", (0.05, 0.1, 0.25),     "A", "adaptive control opex, MUSD/yr"),
 # PV and paint
 ("kwp_ha",  "tri", (500, 700, 900),       "A", "conventional PV, kWp per ha"),
 ("capex_pv", "tri", (550, 750, 1100),     "R", "PV capex, USD/kW (RenovAr ref 850)"),
 ("prem_pv", "tri", (1.1, 1.3, 1.6),       "A", "landfill foundation premium for PV"),
 ("yield_pv", "tri", (1350, 1500, 1650),   "A", "PV yield, kWh/kWp/yr"),
 ("om_pv",   "tri", (0.01, 0.015, 0.025),  "A", "PV O&M, fraction of capex per yr"),
 ("life_pv", "tri", (20, 25, 30),          "A", "PV life, yr"),
 ("p_pv",    "tri", (55, 70, 90),          "B", "PV electricity value, merchant, USD/MWh (2024-25 wholesale cost)"),
 ("eta_pt",  "tri", (0.02, 0.05, 0.10),    "A", "PV-paint module efficiency (unvalidated)"),
 ("c_pt",    "tri", (5, 30, 150),          "A", "PV-paint installed cost, USD/m2 (unvalidated; wide on purpose)"),
 ("life_pt", "tri", (2, 6, 20),            "A", "PV-paint life, yr (unvalidated; wide on purpose)"),
 ("pr_pt",   "tri", (0.65, 0.78, 0.85),    "A", "PV-paint performance ratio"),
 ("om_pt",   "tri", (0.01, 0.02, 0.04),    "A", "PV-paint O&M, fraction of capex per yr"),
 ("H_poa",   "tri", (1550, 1650, 1750),    "A", "plane-of-array irradiation, kWh/m2/yr"),
 ("ef_grid", "tri", (0.28, 0.31, 0.36),    "A", "grid emission factor, tCO2/MWh"),
 # robustness-only inputs (do not enter the base case)
 ("cp",      "tri", (2.0, 6.0, 12.0),      "B", "carbon-credit price if eligible, USD/tCO2e (VCM ~5.5, landfill gas ~9.5 USD, 2025)"),
 ("p_elig",  "uni", (0.2, 0.8),            "A", "probability that added capture is eligible for credits"),
 ("dv",      "tri", (0.0, 0.4, 0.6),       "A", "debt share of financing"),
 ("r_e",     "tri", (0.12, 0.16, 0.22),    "A", "real cost of equity"),
 ("r_d",     "tri", (0.07, 0.09, 0.12),    "A", "real cost of debt"),
 ("k_dec",   "tri", (0.05, 0.09, 0.15),    "L", "first-order decay rate, 1/yr (IPCC 2006, temperate wet MSW)"),
 ("age",     "tri", (20, 28, 32),          "A", "years of deposition before 2026"),
 ("t_close", "tri", (3, 8, 15),            "A", "years until deposition stops, from 2026"),
]
NAMES = [p[0] for p in P]
IDX = {n: i for i, n in enumerate(NAMES)}
ROBUST_ONLY = {"cp", "p_elig", "dv", "r_e", "r_d", "k_dec", "age", "t_close", "p_el_k"}


def _ppf(u, dist, args, widen=0.0, uniform=False):
    if dist == "tri":
        a, c, b = args
        if widen:
            span = b - a
            a2, b2 = a - widen * span / 2, b + widen * span / 2
            if a >= 0:
                a2 = max(a2, 0.0 if a == 0 else a * 0.5)
            a, b = a2, b2
            c = min(max(c, a), b)
        if uniform:
            return a + (b - a) * u
        return stats.triang.ppf(u, c=(c - a) / (b - a), loc=a, scale=b - a)
    if dist == "uni":
        a, b = args
        if widen:
            span = b - a
            a, b = a - widen * span / 2, b + widen * span / 2
            a = max(a, 0.0)
            if b > 1 and args[1] <= 1:
                b = 1.0
        return a + (b - a) * u
    if dist == "logn":
        s = args[0] * (1 + widen)
        return stats.lognorm.ppf(u, s=s, scale=np.exp(-0.5 * s * s))
    raise ValueError(dist)


# rank correlations for the correlated-inputs variant (Iman and Conover 1982)
CORR = [("p_gnc", "p_pipe", 0.7), ("p_el", "c_el", 0.6), ("p_el", "p_pv", 0.8), ("capex_up", "capex_gv", 0.5),
        ("m_p", "logist", -0.5), ("r", "logist", 0.3), ("f_hot", "h_e", 0.5), ("eps_conv", "s_c", 0.3), ("L0", "fss", -0.3)]


def _iman_conover(u, seed):
    n, d = u.shape
    Cm = np.eye(d)
    for a, b, rho in CORR:
        i, j = IDX[a], IDX[b]
        Cm[i, j] = Cm[j, i] = rho
    # nearest positive-definite
    w, V = np.linalg.eigh(Cm)
    Cm = V @ np.diag(np.maximum(w, 1e-6)) @ V.T
    Dg = np.sqrt(np.diag(Cm)); Cm = Cm / np.outer(Dg, Dg)
    rng = np.random.default_rng(seed + 99)
    scores = stats.norm.ppf((np.arange(1, n + 1)) / (n + 1))
    Z = np.column_stack([rng.permutation(scores) for _ in range(d)])
    E = np.corrcoef(Z, rowvar=False)
    Q = np.linalg.cholesky(Cm); Pm = np.linalg.cholesky(E)
    Zs = Z @ np.linalg.inv(Pm).T @ Q.T
    out = np.empty_like(u)
    for k in range(d):
        order = np.argsort(np.argsort(Zs[:, k]))
        out[:, k] = np.sort(u[:, k])[order]
    return out


def sample(n, seed=20261017, correlated=False, widen=0.0, uniform=False):
    """Latin-hypercube sample; returns dict name -> array(n)."""
    u = qmc.LatinHypercube(d=len(P), seed=seed).random(n)
    if correlated:
        u = _iman_conover(u, seed)
    p = {name: _ppf(u[:, i], dist, args, widen, uniform) for i, (name, dist, args, _, _) in enumerate(P)}
    p["cap_prem"] = 1.0 + p["f_imp"] * (p["duty"] + p["logist"])
    return p


def af(r, n=T):
    return (1 - (1 + r) ** (-n)) / r


def crf(r, n):
    return r / (1 - (1 + r) ** (-n))


def replacement_factor(r, life, horizon=T, kmax=6):
    f = np.ones_like(life)
    for k in range(1, kmax + 1):
        f = f + np.where(k * life < horizon - 1e-9, (1 + r) ** (-k * life), 0.0)
    return f


def tpy(nm3h):
    """Nm3 CH4/h -> t CH4/yr"""
    return nm3h * RHO * H / 1000.0


# ------------------------------------------------------------------ gas balance and calibration
def gas_balance(p):
    g = {}
    g["G22"] = p["Awaste"] * 365.0 * p["L0"] * p["fss"] / H                  # Nm3 CH4/h generated around 2022
    g["C22"] = p["Qcoll22"] * p["xCH4"]
    g["eta22"] = g["C22"] / g["G22"]
    g["E22_th"] = np.maximum(0.0, g["G22"] - g["C22"]) * (1 - p["ox"]) * RHO / 1000.0   # t CH4/h at the observation date
    g["G"] = g["G22"] * p["g_t"]                                               # contemporary generation
    g["C"] = p["Qcoll"] * p["xCH4"]
    g["eng"] = p["P_el"] * p["CF_el"] * 1000.0 / (p["eta_el"] * LHV)           # Nm3 CH4/h demanded by existing engines
    g["eng_used"] = np.minimum(g["eng"], g["C"])
    g["S_exist"] = np.maximum(0.0, g["C"] - g["eng"])                          # surplus (flared)
    g["eta_c"] = g["C"] / g["G"]
    g["E_atm0"] = np.maximum(0.0, g["G"] - g["C"]) * (1 - p["ox"])
    g["E_atm0_th"] = g["E_atm0"] * RHO / 1000.0
    g["consistent"] = (g["eta22"] <= ETA_MAX) & (g["eta_c"] <= ETA_MAX)
    return g


def likelihood(E, kind):
    if kind == "window":
        return ((E >= SAT_LO) & (E <= SAT_HI)).astype(float)
    if kind == "gauss":
        return np.exp(-0.5 * ((E - SAT_MED) / SAT_SD) ** 2)
    if kind == "lognormal":
        with np.errstate(divide="ignore"):
            z = (np.log(np.maximum(E, 1e-9)) - np.log(SAT_MED)) / SAT_SLN
        return np.exp(-0.5 * z * z)
    raise ValueError(kind)


def posterior_index(g, kind="lognormal", n_post=60000, seed=5):
    """Importance resampling of the consistent prior draws with the satellite likelihood applied to the HISTORICAL emission (observation date).
    Returns (index array, effective sample size, acceptance-equivalent fraction)."""
    w = likelihood(g["E22_th"], kind) * g["consistent"]
    ess = float(w.sum() ** 2 / max((w * w).sum(), 1e-300))
    rng = np.random.default_rng(seed)
    idx = rng.choice(w.size, size=n_post, replace=True, p=w / w.sum())
    return idx, ess, float(w.sum() / g["consistent"].sum())


# ------------------------------------------------------------------ cover
def cover(p, g, kind="conv", dEta_eff=None, structure="base"):
    """Methane mass balance of a selective cover after S1 (Nm3 CH4/h). structure: 'base', 'no_redirect_ox' (redirected gas leaves unoxidised),
    'full_ox_loss' (no oxidation at all under the cover)."""
    eps = p["eps_conv"] if kind == "conv" else p["eps_coat"]
    rho = p["rho_r"] if structure != "no_redirect_ox" else 0.0 * p["rho_r"]
    dox = p["delta_ox"] if structure != "full_ox_loss" else np.ones_like(p["delta_ox"])
    E_surf1 = np.maximum(0.0, g["G"] * (1 - g["eta_c"] - dEta_eff))
    M_c = E_surf1 * p["f_hot"]
    b = eps * M_c
    cap = p["s_c"] * b
    Rd = (1 - p["s_c"]) * b
    ox, ox_cov, ox_r = p["ox"], p["ox"] * (1 - dox * eps), p["ox"] * rho
    E0 = E_surf1 * (1 - ox)
    E1 = (E_surf1 - M_c) * (1 - ox) + (M_c - b) * (1 - ox_cov) + Rd * (1 - ox_r)
    oxidised = (E_surf1 - M_c) * ox + (M_c - b) * ox_cov + Rd * ox_r
    avoided = E0 - E1 - cap * (1 - p["d_f"])
    resid = E_surf1 - (E1 + oxidised + cap)
    A0 = M_c * (1 - ox) - (M_c - b) * (1 - ox_cov) - b * (1 - ox_r)
    A1 = b * (1 - ox_r) - b * (1 - p["d_f"])
    with np.errstate(divide="ignore", invalid="ignore"):
        sc_star = np.where(A1 > 0, -A0 / A1, np.inf)
    return dict(E_surf1=E_surf1, M_c=M_c, b=b, cap=cap, R=Rd, avoided=avoided, resid=resid, E0=E0, E1=E1, oxidised=oxidised,
                A0=A0, A1=A1, sc_star=sc_star)


def cover_cost(p, kind="conv"):
    A_cov = p["f_hot"] * p["A_act"] / p["h_e"]
    c = p["c_conv"] if kind == "conv" else p["c_coat"]
    life = p["life_conv"] if kind == "conv" else p["life_coat"]
    capex = A_cov * c * 1e3 * p["cap_prem"]
    npv_cost = capex * replacement_factor(p["r"], life) + p["om_cov"] * capex * af(p["r"])
    return A_cov, -npv_cost, capex


# ------------------------------------------------------------------ upgrading, power alternative
def upgrading(p, CH4_avail, Q_des=2000.0, buffer=True, p_el=None):
    """Best biomethane route versus flaring the same gas, with a complete methane, energy and fossil-CO2 account.
    CH4_avail: Nm3 CH4/h of surplus/incremental gas. All flows below are per year."""
    x = p["xCH4"]
    raw_avail = CH4_avail / x * p["avail_firm"]
    vl = p["var_loss"] * (1 - p["zeta"]) if buffer else p["var_loss"]
    usable = raw_avail * (1 - vl)
    Qin = np.minimum(Q_des, usable)                                      # raw Nm3/h to the upgrader
    gas_total = CH4_avail * H                                            # Nm3 CH4/yr offered
    ch4_in = Qin * H * p["uptime"] * x                                   # Nm3 CH4/yr into the plant
    leak_b = p["leak_buf"] * ch4_in if buffer else 0.0 * ch4_in
    fug = p["fug_plant"] * ch4_in
    feed = ch4_in - leak_b - fug                                         # CH4 reaching the separation stage
    ch4_prod = feed * p["rec"]                                           # CH4 in product
    tail = feed * (1 - p["rec"])
    prod = ch4_prod / X_PROD                                             # Nm3 product/yr
    Vraw = Qin * H * p["uptime"]
    elec_up = p["e_up"] * Vraw / 1000.0                                  # MWh/yr
    capex_up = p["capex_up"] * Q_des * p["cap_prem"]
    capex_b = p["capex_buf"] * 1e6 * p["cap_prem"] if buffer else 0.0
    base_op = p["c_el"] * elec_up + p["om_up"] * capex_up + p["lab_up"] * 1e6
    afr = af(p["r"])
    prod_rate_design = Q_des * x * p["rec"] / X_PROD
    # R1 GNC only: unsold product is flared
    sold_g = np.minimum(prod, p["D_gnc"] * H * p["uptime"])
    capex_g = (p["capex_gv"] * prod_rate_design + p["capex_gf"] * 1e6) * p["cap_prem"]
    rev_g = sold_g * p["p_gnc"] * p["m_p"]
    op_g = p["c_el"] * E_COMP["gnc"] * sold_g / 1000.0 + 0.04 * capex_g
    npv1 = -(capex_up + capex_b + capex_g) + afr * (rev_g - base_op - op_g)
    # R2 pipeline
    capex_p = (p["dist_km"] * p["c_km"] + p["c_inj"]) * 1e6 * p["cap_prem"]
    rev_p = prod * p["p_pipe"] * p["m_p"]
    op_p = p["c_el"] * E_COMP["pipe"] * prod / 1000.0 + 0.03 * capex_p
    npv2 = -(capex_up + capex_b + capex_p) + afr * (rev_p - base_op - op_p)
    # R3 hybrid: GNC first, remainder pipeline
    rem = np.maximum(0.0, prod - sold_g)
    rev_h = rev_g + rem * p["p_pipe"] * p["m_p"]
    op_h = op_g + p["c_el"] * E_COMP["pipe"] * rem / 1000.0 + 0.03 * capex_p
    npv3 = -(capex_up + capex_b + capex_g + capex_p) + afr * (rev_h - base_op - op_h)
    routes = np.vstack([npv1, npv2, npv3])
    best = routes.max(axis=0)
    which = routes.argmax(axis=0)
    sold_gnc = np.where(which == 1, 0.0, sold_g)
    sold_pipe = np.where(which == 0, 0.0, np.where(which == 1, prod, rem))
    sold = sold_gnc + sold_pipe
    flared_prod = prod - sold                                            # GNC-only route: product beyond demand is flared
    capex_route = np.where(which == 0, capex_g, np.where(which == 1, capex_p, capex_g + capex_p))
    elec_comp = (E_COMP["gnc"] * sold_gnc + E_COMP["pipe"] * sold_pipe) / 1000.0
    elec_tot = elec_up + elec_comp                                       # MWh/yr, route-specific
    # break-even realised prices
    k1 = (capex_up + capex_b + capex_g) / afr + base_op + op_g
    k2 = (capex_up + capex_b + capex_p) / afr + base_op + op_p
    with np.errstate(divide="ignore", invalid="ignore"):
        pstar_gnc = k1 / (sold_g * p["m_p"]); pstar_pipe = k2 / (prod * p["m_p"])
    # power alternative on the same gas
    pel = p["p_el"] if p_el is None else p_el
    ch4_pw = Qin * H * p["cf_pw"] * x
    kw = Qin * x * LHV * p["eta_pw"]
    capex_pw = p["capex_pw"] * kw * p["cap_prem"]
    mwh = ch4_pw * LHV * p["eta_pw"] / 1000.0
    npv_pw = -capex_pw + afr * (mwh * pel * p["m_p"] - p["om_pw"] * capex_pw)
    k1pw = k1 + npv_pw / afr; k2pw = k2 + npv_pw / afr
    with np.errstate(divide="ignore", invalid="ignore"):
        pstar_gnc_pw = k1pw / (sold_g * p["m_p"]); pstar_pipe_pw = k2pw / (prod * p["m_p"])
    # ---- methane account (Nm3 CH4/yr): all offered gas is upgraded, flared or (power case) burnt in engines
    flared_gas = gas_total - ch4_in                                      # not taken by the plant: flared as before
    slip_tail = tail * (1 - p["tail_ox"])
    destroyed_up = tail * p["tail_ox"] + flared_prod * X_PROD * p["d_f"] + flared_gas * p["d_f"]
    emitted_up = leak_b + fug + slip_tail + flared_prod * X_PROD * (1 - p["d_f"]) + flared_gas * (1 - p["d_f"])
    exported = sold * X_PROD
    resid_up = gas_total - (destroyed_up + emitted_up + exported)
    emitted_flare = gas_total * (1 - p["d_f"])                          # counterfactual: all of it flared
    emitted_pw = (gas_total - ch4_pw) * (1 - p["d_f"]) + ch4_pw * (1 - p["d_f"])
    # ---- climate versus flaring (tCO2e/yr, + = avoided)
    d_ch4_t = (emitted_up - emitted_flare) * RHO / 1000.0
    disp = exported * LHV / 1000.0 * EF_NG                               # natural gas displaced (tCO2)
    co2_el = elec_tot * p["ef_grid"]
    ne100 = disp - d_ch4_t * GWP100 - co2_el
    ne20 = disp - d_ch4_t * GWP20 - co2_el
    ne_pw = mwh * p["ef_grid"] - (emitted_pw - emitted_flare) * RHO / 1000.0 * GWP100
    # ---- energy account (MWh/yr, LHV)
    e_in = gas_total * LHV / 1000.0
    energy = dict(e_in=e_in, e_product=exported * LHV / 1000.0, e_flared=(flared_gas + flared_prod * X_PROD) * LHV / 1000.0,
                  e_losses=(leak_b + fug + tail) * LHV / 1000.0, e_elec_in=elec_tot)
    energy["resid"] = e_in - (energy["e_product"] + energy["e_flared"] + energy["e_losses"])
    return dict(pstar_gnc=pstar_gnc, pstar_pipe=pstar_pipe, pstar_gnc_pw=pstar_gnc_pw, pstar_pipe_pw=pstar_pipe_pw,
                npv=best, route=which, npv_routes=routes, npv_pw=npv_pw, prod=prod, sold=sold, exported=exported, flared_prod=flared_prod,
                ch4_in=ch4_in, ne100=ne100, ne20=ne20, ne_pw=ne_pw, elec=elec_tot, Qin=Qin, mwh_pw=mwh,
                capex_total=capex_up + capex_b + capex_route, capex_pw=capex_pw,
                rev=np.choose(which, [rev_g, rev_p, rev_h]), op=base_op + np.choose(which, [op_g, op_p, op_h]),
                ch4=dict(offered=gas_total, destroyed=destroyed_up, emitted=emitted_up, exported=exported, resid=resid_up,
                         emitted_flare=emitted_flare), energy=energy)


def pv_conv(p, A_cov):
    kwp = p["kwp_ha"] * A_cov
    capex = kwp * p["capex_pv"] * p["prem_pv"] * p["cap_prem"]
    E = kwp * p["yield_pv"] / 1000.0
    npv = -capex + af(p["r"]) * (E * p["p_pv"] * p["m_p"] - p["om_pv"] * capex)
    lcoe = (capex * crf(p["r"], p["life_pv"]) + p["om_pv"] * capex) / (E * 1000.0)
    return dict(npv=npv, E=E, lcoe=lcoe, capex=capex)


def pv_paint(p, A_cov):
    m2 = A_cov * 1e4
    capex = m2 * p["c_pt"] * p["cap_prem"]
    E = m2 * p["eta_pt"] * p["H_poa"] * p["pr_pt"] / 1000.0
    npv = -capex * replacement_factor(p["r"], p["life_pt"]) + af(p["r"]) * (E * p["p_pv"] * p["m_p"] - p["om_pt"] * capex)
    lcoe = (capex * crf(p["r"], p["life_pt"]) + p["om_pt"] * capex) / (E * 1000.0)
    return dict(npv=npv, E=E, lcoe=lcoe, capex=capex)


def paint_breakeven_eta(p, lcoe_conv, c_pt=None, life=None):
    c = p["c_pt"] if c_pt is None else c_pt
    L = p["life_pt"] if life is None else life
    ann = c * p["cap_prem"] * (crf(p["r"], L) + p["om_pt"])
    return ann / (lcoe_conv * p["H_poa"] * p["pr_pt"])


# ------------------------------------------------------------------ full model
def run_model(n=300000, seed=20261017, Q_des=2000.0, correlated=False, widen=0.0, uniform=False, cover_structure="base",
              p_override=None):
    p = sample(n, seed, correlated, widen, uniform)
    if p_override:
        for k, v in p_override.items():
            p[k] = np.full(n, v, dtype=float) if np.isscalar(v) else v
        p["cap_prem"] = 1.0 + p["f_imp"] * (p["duty"] + p["logist"])
    g = gas_balance(p)
    out = dict(p=p, g=g, n=n)
    afr = af(p["r"])
    dE1 = np.clip(np.minimum(p["dEta1"], ETA_MAX - g["eta_c"]), 0.0, None)
    dC1 = g["G"] * dE1
    out["dC1"] = dC1
    av1 = dC1 * (1 - p["ox"]) - dC1 * (1 - p["d_f"])
    capex1 = p["capex_s1"] * 1e6 * p["cap_prem"]
    cost1 = -(capex1 + p["opex_s1"] * 1e6 * afr)
    out["S1_ch4"] = tpy(av1); out["S1_npv"] = cost1
    cc = cover(p, g, "conv", dE1, cover_structure); ck = cover(p, g, "coat", dE1, cover_structure)
    A_cov, npv_cc, capex_cc = cover_cost(p, "conv"); _, npv_ck, capex_ck = cover_cost(p, "coat")
    out["cov_conv"], out["cov_coat"], out["A_cov"] = cc, ck, A_cov
    out["S2_ch4"] = tpy(av1 + cc["avoided"]); out["S3_ch4"] = tpy(av1 + ck["avoided"])
    out["S2_cover_only_ch4"] = tpy(cc["avoided"]); out["S3_cover_only_ch4"] = tpy(ck["avoided"])
    out["S2_npv"] = cost1 + npv_cc; out["S3_npv"] = cost1 + npv_ck
    pvc, pvp = pv_conv(p, A_cov), pv_paint(p, A_cov)
    out["pvc"], out["pvp"] = pvc, pvp
    out["S4_npv"] = out["S2_npv"] + pvc["npv"]; out["S5_npv"] = out["S2_npv"] + pvp["npv"]
    out["pv_co2_conv"] = pvc["E"] * p["ef_grid"]; out["pv_co2_paint"] = pvp["E"] * p["ef_grid"]
    out["eta_star"] = paint_breakeven_eta(p, pvc["lcoe"])
    gas_cov = g["S_exist"] + dC1 + cc["cap"]
    u6 = upgrading(p, gas_cov, Q_des, buffer=True); u6nb = upgrading(p, gas_cov, Q_des, buffer=False)
    out["u6"], out["u6nb"] = u6, u6nb
    out["S6_npv"] = out["S2_npv"] + u6["npv"]
    gas_nc = g["S_exist"] + dC1
    u6b = upgrading(p, gas_nc, Q_des, buffer=True)
    out["u6b"] = u6b
    out["S6b_npv"] = cost1 + u6b["npv"]
    u0 = upgrading(p, g["S_exist"], Q_des, buffer=True)
    u0k = upgrading(p, g["S_exist"], Q_des, buffer=True, p_el=p["p_el_k"])
    out["u0"], out["u0k"] = u0, u0k
    dEad = np.clip(np.minimum(p["dEta_ad"], ETA_MAX - g["eta_c"] - dE1), 0.0, None)
    dCad = g["G"] * dEad
    u7 = upgrading(p, gas_cov + dCad, Q_des, buffer=True)
    pv_mwh = p["f_pv"] * u7["elec"]
    kwp = pv_mwh * 1000.0 / p["yield_pv"]
    capex_pva = kwp * p["capex_pv"] * p["prem_pv"] * p["cap_prem"]
    npv_pva = -capex_pva + afr * (pv_mwh * p["c_el"] - p["om_pv"] * capex_pva)
    capex_ad = p["capex_ad"] * 1e6 * p["cap_prem"]
    npv_ad = -(capex_ad + p["opex_ad"] * 1e6 * afr)
    out["u7"] = u7
    out["S7_npv"] = out["S2_npv"] + u7["npv"] + npv_pva + npv_ad
    out["dCad"] = dCad
    # ---- climate per scenario from the incremental formulas (tCO2e/yr)
    for tag, ch4 in (("S1", out["S1_ch4"]), ("S2", out["S2_ch4"]), ("S3", out["S3_ch4"])):
        out[tag + "_co2_100"] = ch4 * GWP100; out[tag + "_co2_20"] = ch4 * GWP20
    av_ad = tpy(dCad * (1 - p["ox"]) - dCad * (1 - p["d_f"]))
    out["S4_co2_100"] = out["S2_co2_100"] + out["pv_co2_conv"]; out["S4_co2_20"] = out["S2_co2_20"] + out["pv_co2_conv"]
    out["S5_co2_100"] = out["S2_co2_100"] + out["pv_co2_paint"]; out["S5_co2_20"] = out["S2_co2_20"] + out["pv_co2_paint"]
    out["S6_co2_100"] = out["S2_co2_100"] + u6["ne100"]; out["S6_co2_20"] = out["S2_co2_20"] + u6["ne20"]
    out["S6b_co2_100"] = out["S1_co2_100"] + u6b["ne100"]; out["S6b_co2_20"] = out["S1_co2_20"] + u6b["ne20"]
    out["S7_co2_100"] = out["S2_co2_100"] + u7["ne100"] + av_ad * GWP100 + pv_mwh * p["ef_grid"]
    out["S7_co2_20"] = out["S2_co2_20"] + u7["ne20"] + av_ad * GWP20 + pv_mwh * p["ef_grid"]
    out["PW_npv"] = u0["npv_pw"]; out["PW_co2_100"] = u0["ne_pw"]                # stand-alone power alternative on existing surplus
    out["H3_up_minus_pw"] = u0["npv"] - u0["npv_pw"]
    out["H4_buf"] = u6["npv"] - u6nb["npv"]
    E_tot0 = tpy(g["E_atm0"] + g["C"] * (1 - p["d_f"]))
    out["E_tot0"] = E_tot0
    out["base_co2_t100"] = E_tot0 * GWP100 / (p["Awaste"] * 365.0)
    out["S7_co2_t100"] = (E_tot0 * GWP100 - out["S7_co2_100"]) / (p["Awaste"] * 365.0)
    out["gross_inc_S2"] = tpy(dC1 + cc["cap"])
    out["afr"] = afr
    # capex per scenario (for the after-tax variant)
    out["capex"] = dict(S1=capex1, S2=capex1 + capex_cc, S3=capex1 + capex_ck, S4=capex1 + capex_cc + pvc["capex"],
                        S5=capex1 + capex_cc + pvp["capex"], S6=capex1 + capex_cc + u6["capex_total"], S6b=capex1 + u6b["capex_total"],
                        S7=capex1 + capex_cc + u7["capex_total"] + capex_pva + capex_ad, PW=u0["capex_pw"])
    # ---- explicit balances
    out["bal"] = balances(p, g, dC1, cc, u6, u6b, u7, dCad, pv_mwh, pvc, pvp)
    return out


def balances(p, g, dC1, cc, u6, u6b, u7, dCad, pv_mwh, pvc, pvp):
    """Methane (Nm3 CH4/yr), carbon (t C/yr), energy (MWh/yr) and climate (tCO2e/yr) balance of every scenario.
    Atmospheric CH4 = surface emission after oxidation + slip from engines/flares/upgrader; oxidised CH4 -> biogenic CO2; destroyed CH4 ->
    biogenic CO2; exported biomethane leaves the site (its end-use combustion is biogenic). Fossil terms: grid electricity imported (+),
    grid electricity displaced by new engines/PV (-), natural gas displaced by biomethane (-)."""
    G = g["G"] * H; C = g["C"] * H; dC = dC1 * H; cap = cc["cap"] * H; dCa = dCad * H
    ox, d_f = p["ox"], p["d_f"]
    res = {}

    def scen(surface, surf_ox, collected_flared_or_engine, extra_emit=0.0, extra_destroy=0.0, exported=0.0, fossil=0.0, elec_out=0.0,
             elec_in=0.0, e_prod=0.0):
        emit = surface + collected_flared_or_engine * (1 - d_f) + extra_emit
        destroy = collected_flared_or_engine * d_f + extra_destroy
        closure = G - (emit + surf_ox + destroy + exported)
        co2e = emit * RHO / 1000.0 * GWP100 + fossil
        return dict(ch4_emit=emit, ch4_ox=surf_ox, ch4_destroy=destroy, ch4_export=exported, resid=closure,
                    c_ch4=emit * C_PER_NM3, c_co2_bio=(surf_ox + destroy) * C_PER_NM3, c_export=exported * C_PER_NM3,
                    co2e=co2e, fossil=fossil, elec_out=elec_out, elec_in=elec_in, e_product=e_prod)
    # S0 / S1
    res["S0"] = scen((G - C) * (1 - ox), (G - C) * ox, C)
    res["S1"] = scen((G - C - dC) * (1 - ox), (G - C - dC) * ox, C + dC)
    # S2 / S3 (cover): surface stream from the cover account
    E1 = cc["E1"] * H; oxs = cc["oxidised"] * H
    res["S2"] = scen(E1, oxs, C + dC + cap)
    res["S3"] = None  # coating has the same structure; not repeated
    # S4: S2 + PV (displaced grid electricity)
    res["S4"] = scen(E1, oxs, C + dC + cap, fossil=-pvc["E"] * p["ef_grid"], elec_out=pvc["E"])
    # S6: S2 with surplus+S1+cover gas routed to the upgrader (u6 account replaces flaring of that gas)
    offered = u6["ch4"]["offered"]
    rest = C + dC + cap - offered                                         # collected gas not offered (engines)
    res["S6"] = scen(E1, oxs, rest, extra_emit=u6["ch4"]["emitted"], extra_destroy=u6["ch4"]["destroyed"], exported=u6["ch4"]["exported"],
                     fossil=u6["elec"] * p["ef_grid"] - u6["exported"] * LHV / 1000.0 * EF_NG, elec_in=u6["elec"],
                     e_prod=u6["exported"] * LHV / 1000.0)
    offered_b = u6b["ch4"]["offered"]
    res["S6b"] = scen((G - C - dC) * (1 - ox), (G - C - dC) * ox, C + dC - offered_b, extra_emit=u6b["ch4"]["emitted"],
                      extra_destroy=u6b["ch4"]["destroyed"], exported=u6b["ch4"]["exported"],
                      fossil=u6b["elec"] * p["ef_grid"] - u6b["exported"] * LHV / 1000.0 * EF_NG, elec_in=u6b["elec"],
                      e_prod=u6b["exported"] * LHV / 1000.0)
    # S7: S6 + adaptive control (extra capture dCad from the uncovered surface) + PV supplying part of the upgrader electricity
    surf7 = E1 - dCa * (1 - ox); oxs7 = oxs - dCa * ox
    offered7 = u7["ch4"]["offered"]
    res["S7"] = scen(surf7, oxs7, C + dC + cap + dCa - offered7, extra_emit=u7["ch4"]["emitted"], extra_destroy=u7["ch4"]["destroyed"],
                     exported=u7["ch4"]["exported"],
                     fossil=(u7["elec"] - pv_mwh) * p["ef_grid"] - u7["exported"] * LHV / 1000.0 * EF_NG, elec_in=u7["elec"] - pv_mwh,
                     e_prod=u7["exported"] * LHV / 1000.0)
    for k in ("S1", "S2", "S4", "S6", "S6b", "S7"):
        res[k]["avoided_co2e"] = res["S0"]["co2e"] - res[k]["co2e"]
    return res


SCEN = ["S1", "S2", "S3", "S4", "S5", "S6", "S6b", "S7"]
SCEN_LABEL = {"S1": "S1 wellfield + leak control", "S2": "S2 S1 + conventional cover", "S3": "S3 S1 + experimental coating",
              "S4": "S4 S2 + conventional PV", "S5": "S5 S2 + PV paint", "S6": "S6 S2 + buffer + biomethane",
              "S6b": "S6b S1 + biomethane (no cover)", "S7": "S7 S6 + solar + adaptive"}


def qtl(x, q=(5, 50, 95)):
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    return [float(np.percentile(x, k)) for k in q] if x.size else [None, None, None]


def spearman_to_inputs(out, y, idx, top=12):
    p = out["p"]
    names = [n for n in NAMES if n not in ROBUST_ONLY and np.std(p[n][idx]) > 0]
    X = np.column_stack([p[n][idx] for n in names])
    ry = stats.rankdata(y[idx]); rX = stats.rankdata(X, axis=0)
    ry = (ry - ry.mean()) / ry.std(); rX = (rX - rX.mean(0)) / rX.std(0)
    rho = (rX * ry[:, None]).mean(0)
    order = np.argsort(-np.abs(rho))[:top]
    return [(names[i], float(rho[i])) for i in order]


def after_tax_npv(npv_pre, capex, r):
    """Approximate after-tax NPV: operating cash flow taxed at TAX, straight-line depreciation shield, full loss offset against other income."""
    afr = af(r)
    ocf_pre = (npv_pre + capex) / afr
    return -capex + afr * ocf_pre * (1 - TAX) + TAX * capex / DEP_YR * af(r, DEP_YR)


def summarize(out, idx, label):
    g, p = out["g"], out["p"]
    res = dict(regime=label, n_used=int(idx.size))
    gb = {}
    for k, v in (("G22_Nm3h", g["G22"]), ("eta22", g["eta22"]), ("E22_th", g["E22_th"]), ("G_Nm3h", g["G"]), ("C_Nm3h", g["C"]),
                 ("eng_Nm3h", g["eng"]), ("S_exist_Nm3h", g["S_exist"]), ("eta_c", g["eta_c"]), ("E_atm_th", g["E_atm0_th"])):
        gb[k] = qtl(v[idx])
    gb["P_surplus_gt0"] = float((g["S_exist"][idx] > 0).mean())
    gb["P_surplus_gt500Nm3h_CH4"] = float((g["S_exist"][idx] > 500).mean())
    res["gas"] = gb
    sc = {}
    for s in SCEN + ["PW"]:
        npv = out[s + "_npv"][idx] / 1e6
        co2 = out[s + "_co2_100"][idx]
        d = dict(npv_q=qtl(npv), P_npv_pos=float((npv > 0).mean()), co2_100_q=qtl(co2), P_co2_pos=float((co2 > 0).mean()))
        if s != "PW":
            d["co2_20_q"] = qtl(out[s + "_co2_20"][idx])
        pos = co2 > 1.0
        ab = np.where(pos, -npv * 1e6 / (out["afr"][idx] * np.where(pos, co2, np.nan)), np.nan)
        d["abate_q"] = qtl(ab)
        for cpv in (0, 10, 25, 50, 100):
            d["P_npv_pos_cp%d" % cpv] = float(((npv * 1e6 + out["afr"][idx] * cpv * co2) > 0).mean())
        if s in out["capex"]:
            at = after_tax_npv(out[s + "_npv"][idx], out["capex"][s][idx], p["r"][idx]) / 1e6
            d["npv_after_tax_q"] = qtl(at)
        sc[s] = d
    res["scen"] = sc
    hyp = {}
    cc, ck = out["cov_conv"], out["cov_coat"]
    hyp["H1_P_cover_reduces_conv"] = float((cc["avoided"][idx] > 0).mean())
    hyp["H1_P_cover_reduces_coat"] = float((ck["avoided"][idx] > 0).mean())
    hyp["H1_cover_only_ch4_conv"] = qtl(out["S2_cover_only_ch4"][idx])
    hyp["H1_cover_only_ch4_coat"] = qtl(out["S3_cover_only_ch4"][idx])
    gi = out["gross_inc_S2"][idx]
    hyp["H1_gross_vs_net_ratio_median"] = float(np.median((out["S2_ch4"][idx] / np.maximum(gi, 1e-9))[gi > 0]))
    hyp["H1_sc_star_q"] = qtl(np.minimum(cc["sc_star"][idx], 10))
    hyp["H1_P_sc_below_star"] = float((p["s_c"][idx] < cc["sc_star"][idx]).mean())
    pvc, pvp = out["pvc"], out["pvp"]
    hyp["H2_P_paint_lcoe_lower"] = float((pvp["lcoe"][idx] < pvc["lcoe"][idx]).mean())
    hyp["H2_P_conv_npv_pos"] = float((pvc["npv"][idx] > 0).mean())
    hyp["H2_lcoe_conv_q"] = qtl(pvc["lcoe"][idx] * 1000.0); hyp["H2_lcoe_paint_q"] = qtl(pvp["lcoe"][idx] * 1000.0)
    hyp["H2_eta_star_q"] = qtl(out["eta_star"][idx])
    hyp["H2_P_eta_star_gt_10pct"] = float((out["eta_star"][idx] > 0.10).mean())
    u0, u0k = out["u0"], out["u0k"]
    has = g["S_exist"][idx] > 0
    ih = idx[has]
    hyp["H3_P_up_beats_power"] = float((out["H3_up_minus_pw"][ih] > 0).mean())
    hyp["H3_P_up_beats_contract_power"] = float((u0k["npv"][ih] > u0k["npv_pw"][ih]).mean())
    hyp["H3_P_up_npv_pos"] = float((u0["npv"][ih] > 0).mean())
    hyp["H3_P_power_npv_pos"] = float((u0["npv_pw"][ih] > 0).mean())
    hyp["H3_P_contract_power_npv_pos"] = float((u0k["npv_pw"][ih] > 0).mean())
    hyp["H3_npv_up_q"] = [v / 1e6 for v in qtl(u0["npv"][ih])]
    hyp["H3_npv_pw_q"] = [v / 1e6 for v in qtl(u0["npv_pw"][ih])]
    hyp["H3_npv_pw_contract_q"] = [v / 1e6 for v in qtl(u0k["npv_pw"][ih])]
    hyp["H3_route_share"] = [float((u0["route"][ih] == k).mean()) for k in range(3)]
    # break-even electricity value of the added engines (NPV = 0), per draw with surplus
    with np.errstate(divide="ignore", invalid="ignore"):
        pel_star = (u0["capex_pw"][ih] / out["afr"][ih] + p["om_pw"][ih] * u0["capex_pw"][ih]) / (u0["mwh_pw"][ih] * p["m_p"][ih])
    hyp["pel_star_q"] = qtl(pel_star)
    hyp["H3_climate_up_vs_pw_per_yr_q"] = qtl(u0["ne100"][ih] - u0["ne_pw"][ih])
    hyp["H3_P_up_better_climate"] = float((u0["ne100"][ih] > u0["ne_pw"][ih]).mean())
    MMBTU = 0.0339 * X_PROD
    for key in ("pstar_gnc", "pstar_pipe", "pstar_gnc_pw", "pstar_pipe_pw"):
        v = u0[key][ih]
        hyp[key + "_q"] = qtl(v)
        hyp[key + "_mmbtu_q"] = [x / MMBTU if x is not None else None for x in qtl(v)]
    hyp["pstar_pipe_below_pipe_price"] = float((u0["pstar_pipe"][ih] < p["p_pipe"][ih]).mean())
    hyp["pstar_gnc_below_gnc_price"] = float((u0["pstar_gnc"][ih] < p["p_gnc"][ih]).mean())
    hyp["surplus_P_el_ge31"] = qtl(g["S_exist"][idx][p["P_el"][idx] >= 31])
    hyp["surplus_P_el_le25"] = qtl(g["S_exist"][idx][p["P_el"][idx] <= 25])
    hyp["P_surplus_gt0_P_el_ge31"] = float((g["S_exist"][idx][p["P_el"][idx] >= 31] > 0).mean())
    one_pp = g["G"][idx] * 0.01
    hyp["per_pp_eta_tCH4_yr_q"] = qtl(tpy(one_pp)); hyp["per_pp_eta_tCO2e100_q"] = qtl(tpy(one_pp) * GWP100)
    hyp["H4_P_buffer_pos"] = float((out["H4_buf"][idx] > 0).mean())
    hyp["H4_buf_q"] = [v / 1e6 for v in qtl(out["H4_buf"][idx])]
    b0 = out["base_co2_t100"][idx]; s7 = out["S7_co2_t100"][idx]
    hyp["H5_base_tCO2e_per_t_waste_q"] = qtl(b0); hyp["H5_S7_tCO2e_per_t_waste_q"] = qtl(s7)
    hyp["H5_P_S7_lower"] = float((s7 < b0).mean()); hyp["H5_rel_reduction_q"] = qtl(100.0 * (1 - s7 / b0))
    res["hyp"] = hyp
    res["E_tot0_q"] = qtl(out["E_tot0"][idx])
    res["sens_S6b_npv"] = spearman_to_inputs(out, out["S6b_npv"], idx)
    res["sens_S2_ch4"] = spearman_to_inputs(out, out["S2_cover_only_ch4"], idx)
    res["sens_PW_npv"] = spearman_to_inputs(out, out["PW_npv"], idx)
    # balances (medians, per scenario)
    bal = {}
    for k, b in out["bal"].items():
        if b is None:
            continue
        bal[k] = {kk: float(np.median(np.broadcast_to(np.asarray(vv, dtype=float), (out["n"],))[idx])) for kk, vv in b.items()}
    res["balances_median"] = bal
    return res


def design_sweep(n=60000, seed=7, qlist=(250, 500, 1000, 2000, 4000, 8000), kind="lognormal"):
    p = sample(n, seed); g = gas_balance(p)
    idx, _, _ = posterior_index(g, kind, n_post=min(n, 30000))
    idx = idx[g["S_exist"][idx] > 0]                 # draws with surplus gas to use (as in the H3 statistics)
    rows = []
    for q in qlist:
        u = upgrading(p, g["S_exist"], float(q), True)
        rows.append(dict(Q=q, med=float(np.median(u["npv"][idx]) / 1e6), P=float((u["npv"][idx] > 0).mean()),
                         P_pw=float((u["npv_pw"][idx] > 0).mean())))
    return rows


# ------------------------------------------------------------------ time-resolved variant
def temporal(out, idx, Q_des=2000.0):
    """First-order-decay trajectory of generation over the project life: G(t)/G(0) = (1-exp(-k(a+t)))/(1-exp(-k a)) while deposition
    continues, then exponential decay; collection efficiency held at its contemporary value. Annual cash flows replace the annuity for the
    surplus-gas uses (S6b-type upgrading and the power alternative)."""
    p, g = {k: v[idx] for k, v in out["p"].items()}, {k: v[idx] for k, v in out["g"].items()}
    k, a, tc = p["k_dec"], p["age"], p["t_close"]
    yrs = np.arange(T)
    npv_up = np.zeros(idx.size); npv_pw = np.zeros(idx.size)
    u_ref = upgrading(p, g["S_exist"], Q_des, True)
    capex_up, capex_pw = u_ref["capex_total"], u_ref["capex_pw"]
    for t in yrs:
        dep = np.where(t < tc, (1 - np.exp(-k * (a + t))) / (1 - np.exp(-k * a)),
                       (1 - np.exp(-k * (a + tc))) / (1 - np.exp(-k * a)) * np.exp(-k * (t - tc)))
        C_t = g["C"] * dep
        S_t = np.maximum(0.0, C_t - g["eng"])
        u = upgrading(p, S_t, Q_des, True)
        disc = (1 + p["r"]) ** (-(t + 1))
        npv_up += disc * (u["rev"] - u["op"])
        npv_pw += disc * (u["mwh_pw"] * p["p_el"] * p["m_p"] - p["om_pw"] * capex_pw)
    return dict(npv_up=npv_up - capex_up, npv_pw=npv_pw - capex_pw, npv_up_ss=u_ref["npv"], npv_pw_ss=u_ref["npv_pw"])


# ------------------------------------------------------------------ robustness suite
def headline(out, idx):
    g, p = out["g"], out["p"]
    has = idx[g["S_exist"][idx] > 0]
    u0 = out["u0"]
    return dict(eta_c=float(np.median(g["eta_c"][idx])), eta22=float(np.median(g["eta22"][idx])),
                E26=float(np.median(g["E_atm0_th"][idx])),
                S2_avoided_kt=float(np.median(out["S2_co2_100"][idx]) / 1e3),
                P_cover=float((out["cov_conv"]["avoided"][idx] > 0).mean()),
                S6b_npv=float(np.median(out["S6b_npv"][idx]) / 1e6),
                P_pw_pos=float((u0["npv_pw"][has] > 0).mean()),
                P_up_beats_pw=float((out["H3_up_minus_pw"][has] > 0).mean()),
                pstar_gnc=float(np.nanmedian(u0["pstar_gnc"][has])),
                abate_S1=float(np.nanmedian(-out["S1_npv"][idx] / (out["afr"][idx] * np.maximum(out["S1_co2_100"][idx], 1.0)))),
                abate_S2=float(np.nanmedian(-out["S2_npv"][idx] / (out["afr"][idx] * np.maximum(out["S2_co2_100"][idx], 1.0)))),
                any_scen_median_pos=bool(any(np.median(out[s + "_npv"][idx]) > 0 for s in SCEN)))


def robustness(n=120000, seed=31):
    rows = []
    base = run_model(n, seed)
    for kind in LIKELIHOODS:
        idx, ess, acc = posterior_index(base["g"], kind)
        rows.append(dict(variant="likelihood: " + kind, ess=ess, **headline(base, idx)))
    idx0, _, _ = posterior_index(base["g"], "lognormal")
    cons = np.where(base["g"]["consistent"])[0]
    rows.append(dict(variant="prior only (no satellite constraint)", **headline(base, cons)))
    for lab, kw in (("correlated inputs (Iman-Conover)", dict(correlated=True)), ("uniform marginals", dict(uniform=True)),
                    ("priors widened by 50%", dict(widen=0.5)), ("cover: redirected gas unoxidised", dict(cover_structure="no_redirect_ox")),
                    ("cover: all oxidation lost under cover", dict(cover_structure="full_ox_loss"))):
        m = run_model(n, seed, **kw)
        idx, ess, _ = posterior_index(m["g"], "lognormal")
        rows.append(dict(variant=lab, ess=ess, **headline(m, idx)))
    # contracted electricity tariff
    m = run_model(n, seed, p_override=None)
    m["p"]["p_el"] = m["p"]["p_el_k"]
    mk = run_model(n, seed, p_override={"p_el": m["p"]["p_el_k"]})
    idx, _, _ = posterior_index(mk["g"], "lognormal")
    rows.append(dict(variant="contracted electricity tariff (RenovAr-type)", **headline(mk, idx)))
    # WACC discounting
    pp = sample(n, seed)
    wacc = (1 - pp["dv"]) * pp["r_e"] + pp["dv"] * pp["r_d"] * (1 - TAX)
    mw = run_model(n, seed, p_override={"r": wacc})
    idx, _, _ = posterior_index(mw["g"], "lognormal")
    rows.append(dict(variant="WACC from equity, debt and tax", **headline(mw, idx)))
    # discount-rate sweep and credit sweep (base model, lognormal posterior)
    sweep_r = []
    for rv in (0.06, 0.08, 0.10, 0.12, 0.15, 0.18, 0.20):
        mr = run_model(60000, seed, p_override={"r": rv})
        idx, _, _ = posterior_index(mr["g"], "lognormal", n_post=30000)
        has = idx[mr["g"]["S_exist"][idx] > 0]
        sweep_r.append(dict(r=rv, **{s: float((mr[s + "_npv"][idx] > 0).mean()) for s in ("S1", "S2", "S6b")},
                            PW=float((mr["u0"]["npv_pw"][has] > 0).mean()),
                            S6b_med=float(np.median(mr["S6b_npv"][idx]) / 1e6), PW_med=float(np.median(mr["u0"]["npv_pw"][has]) / 1e6)))
    # expected credit revenue with eligibility risk
    rng = np.random.default_rng(seed)
    elig = rng.random(n) < base["p"]["p_elig"]
    cred = {}
    for s in SCEN:
        npvc = base[s + "_npv"] + base["afr"] * np.where(elig, base["p"]["cp"], 0.0) * base[s + "_co2_100"]
        cred[s] = dict(P_npv_pos=float((npvc[idx0] > 0).mean()), median=float(np.median(npvc[idx0]) / 1e6))
    # temporal variability
    sub = idx0[:20000]
    tv = temporal(base, sub)
    has = base["g"]["S_exist"][sub] > 0
    temp = dict(up_median_ss=float(np.median(tv["npv_up_ss"][has]) / 1e6), up_median_t=float(np.median(tv["npv_up"][has]) / 1e6),
                pw_median_ss=float(np.median(tv["npv_pw_ss"][has]) / 1e6), pw_median_t=float(np.median(tv["npv_pw"][has]) / 1e6),
                P_pw_pos_t=float((tv["npv_pw"][has] > 0).mean()), P_up_pos_t=float((tv["npv_up"][has] > 0).mean()),
                P_up_beats_pw_t=float((tv["npv_up"][has] > tv["npv_pw"][has]).mean()))
    return dict(variants=rows, discount_sweep=sweep_r, credit_expected=cred, temporal=temp)


# ------------------------------------------------------------------ tests
def self_test():
    ok = True

    log = []

    def chk(name, cond, info=""):
        nonlocal ok
        print(("PASS  " if cond else "FAIL  ") + name + (("  " + info) if info else ""))
        log.append(dict(name=name, passed=bool(cond), info=info))
        ok &= bool(cond)
    # units and constants
    chk("units: 1 Nm3/h CH4 = 6.281 t/yr", abs(tpy(1.0) - 6.28092) < 1e-4, "%.5f" % tpy(1.0))
    chk("units: carbon per Nm3 CH4 = 0.536 kg", abs(C_PER_NM3 * 1000 - 0.5359) < 1e-3)
    chk("units: annuity factor -> T as r -> 0", abs(af(1e-9) - T) < 1e-3)
    chk("units: capital recovery x annuity = 1", abs(crf(0.1, T) * af(0.1) - 1) < 1e-12)
    # sampling
    p = sample(100000, 1)
    for n_, (a, c, b) in (("Qcoll", (13000, 14800, 16500)), ("L0", (50, 100, 170))):
        chk("LHS mean " + n_, abs(p[n_].mean() - (a + b + c) / 3) / ((a + b + c) / 3) < 2e-3)
    chk("lognormal price multiplier mean 1", abs(p["m_p"].mean() - 1) < 5e-3)
    pc = sample(50000, 2, correlated=True)
    rs = stats.spearmanr(pc["p_gnc"], pc["p_pipe"])[0]
    chk("Iman-Conover induces target rank correlation (0.7)", abs(rs - 0.7) < 0.05, "%.3f" % rs)
    # white-paper screening arithmetic
    raw, x, rec, xp, hrs = 1000.0, 0.5, 0.95, 0.97, 8000
    ch4 = raw * x * rec; prod = ch4 / xp
    chk("screening: CH4 recovered 475 Nm3/h", abs(ch4 - 475) < 1e-9)
    chk("screening: 37.8 GWh/yr", abs(ch4 * hrs * LHV / 1e6 - 37.77) < 0.05)
    # model
    m = run_model(40000, 3)
    g = m["g"]; cc = m["cov_conv"]
    sc = max(1.0, float(np.max(cc["M_c"])))
    chk("cover: CH4 closure (surface = emitted + oxidised + captured)", np.max(np.abs(cc["resid"])) < 1e-6 * sc)
    s_star = cc["sc_star"]; fin = np.isfinite(s_star) & (s_star < 5)
    pp = dict(m["p"]); pp["s_c"] = np.where(fin, s_star, pp["s_c"])
    dE = np.clip(np.minimum(pp["dEta1"], ETA_MAX - g["eta_c"]), 0, None)
    chk("cover: avoided(s_c*) = 0", np.max(np.abs(cover(pp, g, "conv", dE)["avoided"][fin])) < 1e-6 * sc)
    pz = dict(m["p"]); pz["eps_conv"] = pz["eps_conv"] * 0
    chk("limit: barrier that blocks nothing avoids nothing", np.max(np.abs(cover(pz, g, "conv", dE)["avoided"])) < 1e-9)
    pq = dict(m["p"]); pq["delta_ox"] = pq["delta_ox"] * 0; pq["rho_r"] = np.ones_like(pq["rho_r"])
    cl = cover(pq, g, "conv", dE)
    chk("limit: unchanged oxidation gives s_c b (d_f - ox)", np.max(np.abs(cl["avoided"] - cl["cap"] * (pq["d_f"] - pq["ox"]))) < 1e-6 * sc)
    # scenario balances: CH4, carbon, energy
    for s, b in m["bal"].items():
        if b is None:
            continue
        rel = np.max(np.abs(b["resid"])) / np.max(g["G"] * H)
        chk("balance %s: CH4 closes" % s, rel < 1e-9, "%.1e" % rel)
        cres = (g["G"] * H * C_PER_NM3) - (b["c_ch4"] + b["c_co2_bio"] + b["c_export"])
        chk("balance %s: carbon closes" % s, np.max(np.abs(cres)) / np.max(g["G"] * H * C_PER_NM3) < 1e-9)
    for key in ("u6", "u6b", "u7", "u0"):
        u = m[key]
        chk("upgrader %s: CH4 closes (offered = destroyed + emitted + exported)" % key,
            np.max(np.abs(u["ch4"]["resid"])) < 1e-6 * max(1.0, np.max(u["ch4"]["offered"])))
        chk("upgrader %s: energy closes" % key, np.max(np.abs(u["energy"]["resid"])) < 1e-6 * max(1.0, np.max(u["energy"]["e_in"])))
    # cross-check: climate from balances = incremental formulas
    for s in ("S1", "S2", "S6", "S6b"):
        diff = m["bal"][s]["avoided_co2e"] - m[s + "_co2_100"]
        chk("climate %s: balance-based = incremental (GWP100)" % s, np.max(np.abs(diff)) < 1e-6 * max(1.0, np.max(np.abs(m[s + "_co2_100"]))),
            "%.2e" % np.max(np.abs(diff)))
    # upgrading sign conventions on a hand case: perfect plant, no electricity, no leaks: avoided = displaced NG + flare slip avoided
    ph = {k: v[:1].copy() for k, v in m["p"].items()}
    for k_, v_ in (("rec", 1.0), ("fug_plant", 0.0), ("leak_buf", 0.0), ("e_up", 0.0), ("tail_ox", 1.0), ("avail_firm", 1.0), ("var_loss", 0.0),
                   ("uptime", 1.0), ("D_gnc", 1e9), ("d_f", 0.98)):
        ph[k_] = np.array([v_])
    uh = upgrading(ph, np.array([500.0]), Q_des=1e9, buffer=False)
    exp_disp = 500.0 * H * LHV / 1000.0 * EF_NG
    exp_ch4 = 500.0 * H * (1 - 0.98) * RHO / 1000.0 * GWP100
    comp = uh["elec"][0] * ph["ef_grid"][0]
    chk("upgrading hand case: avoided = NG displaced + flare slip - compression", abs(uh["ne100"][0] - (exp_disp + exp_ch4 - comp)) < 1e-6 * exp_disp,
        "%.1f vs %.1f" % (uh["ne100"][0], exp_disp + exp_ch4 - comp))
    # independent NPV benchmark: explicit cash-flow loop for one draw
    i0 = 0
    r0 = m["p"]["r"][i0]
    u = m["u0"]
    cf = [-(u["capex_pw"][i0])] + [u["mwh_pw"][i0] * m["p"]["p_el"][i0] * m["p"]["m_p"][i0] - m["p"]["om_pw"][i0] * u["capex_pw"][i0]] * T
    npv_loop = sum(c / (1 + r0) ** t for t, c in enumerate(cf))
    chk("benchmark: power NPV = explicit cash-flow sum", abs(npv_loop - u["npv_pw"][i0]) < 1e-6 * max(1.0, abs(npv_loop)))
    # limiting case: zero prices -> NPV = -PV(costs)
    pz2 = dict(m["p"]); pz2["p_gnc"] = pz2["p_gnc"] * 0; pz2["p_pipe"] = pz2["p_pipe"] * 0
    uz = upgrading(pz2, g["S_exist"], 2000.0, True)
    chk("limit: zero gas prices -> biomethane NPV < 0", np.all(uz["npv"] < 0))
    # paint break-even identity
    pp2 = dict(m["p"]); pp2["eta_pt"] = m["eta_star"]
    chk("paint eta* gives LCOE parity", np.max(np.abs(pv_paint(pp2, m["A_cov"])["lcoe"] / m["pvc"]["lcoe"] - 1)) < 1e-9)
    # calibration
    idx, ess, _ = posterior_index(g, "window")
    chk("window likelihood: all resampled draws inside 18-38 t/h", np.all((g["E22_th"][idx] >= SAT_LO) & (g["E22_th"][idx] <= SAT_HI)))
    chk("posterior draws are physically consistent", np.all(g["consistent"][idx]))
    m2 = run_model(40000, 3)
    chk("deterministic for fixed seed", np.allclose(m["S6b_npv"], m2["S6b_npv"]))
    # temporal limiting cases. Fast decay with deposition continuing: generation sits at steady state -> annuity result.
    idx_s = np.arange(2000)
    mt = run_model(4000, 9, p_override={"k_dec": 50.0, "t_close": 100.0})
    tv = temporal(mt, idx_s)
    for key in ("pw", "up"):
        rel = np.max(np.abs(tv["npv_" + key] - tv["npv_%s_ss" % key])) / max(1.0, np.max(np.abs(tv["npv_%s_ss" % key])))
        chk("temporal: steady generation reproduces the annuity NPV (%s)" % key, rel < 1e-9, "%.1e" % rel)
    # slow decay, no closure: G(t)/G(0) -> (a+t)/a (linear growth of the deposited mass)
    k, a, t = 1e-7, 28.0, 10.0
    chk("FOD analytic: k -> 0 limit is (a+t)/a", abs((1 - np.exp(-k * (a + t))) / (1 - np.exp(-k * a)) - (a + t) / a) < 1e-5)
    # convergence of a headline probability
    big = run_model(200000, 11)
    idb, essb, _ = posterior_index(big["g"], "lognormal", n_post=100000)
    pr = big["S6b_npv"][idb] > 0
    se = np.sqrt(pr.mean() * (1 - pr.mean()) / essb)
    chk("standard error of P(NPV>0) < 0.01 (on the effective sample size)", se < 0.01, "ESS=%.0f se=%.4f" % (essb, se))
    print("ALL TESTS PASSED" if ok else "SOME TESTS FAILED")
    rd = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results")
    os.makedirs(rd, exist_ok=True)
    json.dump(dict(n=len(log), all_passed=bool(ok), tests=log), open(os.path.join(rd, "tests.json"), "w"), indent=1)
    return ok


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", action="store_true")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--n", type=int, default=300000)
    ap.add_argument("--outdir", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results"))
    a = ap.parse_args()
    if a.test:
        sys.exit(0 if self_test() else 1)
    if a.run:
        import NorteIII_figs
        NorteIII_figs.run_all(a.n, a.outdir)
