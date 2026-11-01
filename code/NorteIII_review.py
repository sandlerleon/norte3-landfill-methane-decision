# -*- coding: utf-8 -*-
"""
NorteIII_review.py (version 2.1) -- analyses added in response to the second review (October 2026):

  identifiability()   structural identifiability of the collection efficiency (closed form, variance shares, prior-to-posterior contraction,
                      alternative generation histories, widened collection prior), representativeness of the satellite constraint
                      (site-wide scaling, wider and biased observation error), and a second, independent observation (Carbon Mapper 2025)
  pw_cases()          the engine counterfactual: probability of a positive NPV conditional on surplus gas and across all operating states
  climate_variants()  climate accounting: engine methane slip, marginal grid factor, counterfactual flare efficiency, partial displacement of fossil gas
  fig_ident()         identifiability and validation figure

Called from NorteIII_figs.run_all(); every number in the manuscript's new sections is read from results/results.json.
Nothing here is a site measurement; the 2025 observation is a published average of overpass rates and is used as an independent check, with its own error model.
"""
import numpy as np
from scipy import stats

import NorteIII_MC as M

CM25 = 7.6          # t CH4/h, Carbon Mapper 2025 average of overpass emission rates, Campo de Mayo / Norte III (UCLA STOP Methane, 20 April 2026)
CM25_SLN = 0.5      # lognormal sigma assumed for that average (retrieval, wind, sampling): author's assumption, tag A
ENGINE_SLIP = (0.01, 0.03, 0.06)       # pessimistic fraction of CH4 fed to a gas engine that leaves unburnt, tri(min, mode, max), tag A (the base model uses 1 - d_f, 0.5 to 5%)
EF_MARGINAL = (0.35, 0.45, 0.65)       # marginal grid emission factor, tCO2/MWh, tag A
D_F_CF = (0.80, 0.93, 0.98)            # counterfactual flare destruction efficiency (all of the surplus flared), tag A
DISPLACE = (0.3, 0.7, 1.0)             # fraction of biomethane that displaces fossil gas, tag A


def resample(w, n_post=60000, seed=5):
    w = np.asarray(w, dtype=float)
    ess = float(w.sum() ** 2 / max((w * w).sum(), 1e-300))
    rng = np.random.default_rng(seed)
    return rng.choice(w.size, size=n_post, replace=True, p=w / w.sum()), ess


def lognorm_like(E, med, sln):
    with np.errstate(divide="ignore"):
        z = (np.log(np.maximum(E, 1e-9)) - np.log(med)) / sln
    return np.exp(-0.5 * z * z)


def q(x, qs=(5, 50, 95)):
    return M.qtl(x, qs)


def H(out, ix, **extra):
    """headline quantities of the model on the posterior draws ix, with the keys in `extra` taking precedence (e.g. interval versions of eta)."""
    d = M.headline(out, ix)
    d.update(extra)
    return d


def eta_closed(E_th, ox, C_nm3h):
    """Collection efficiency implied by a surface emission E (t/h), oxidation fraction and collected methane (Nm3/h): needs no generation parameter."""
    gen_minus_coll = E_th * 1000.0 / ((1.0 - ox) * M.RHO)
    return C_nm3h / (C_nm3h + gen_minus_coll)


# ------------------------------------------------------------------ identifiability and representativeness
def identifiability(base=None, n=300000, seed=77):
    res = {}
    if base is None:
        base = M.run_model(n, seed)
    n = base["n"]
    g, p = base["g"], base["p"]
    post, ess = {}, {}
    w_ln = M.likelihood(g["E22_th"], "lognormal") * g["consistent"]
    idx, e = resample(w_ln, 60000, 5)
    cons = np.where(g["consistent"])[0]
    res["n"] = n
    # ---- 1 closed form: eta does not depend on A, L0, f_ss, g_t
    ok = g["G22"] > g["C22"]
    cf = eta_closed(g["E22_th"][ok], p["ox"][ok], g["C22"][ok])
    res["closed_form_max_abs_diff"] = float(np.max(np.abs(cf - g["eta22"][ok])))
    # log-odds of capture is exactly additive: ln((1-eta)/eta) = ln E - ln(1-ox) - ln(rho/1000) - ln C
    lo = np.log((1 - g["eta22"][ok]) / g["eta22"][ok])
    parts = dict(lnE=np.log(g["E22_th"][ok]), ln1mox=-np.log(1 - p["ox"][ok]), lnC=-np.log(g["C22"][ok]))
    res["logodds_identity_max_abs"] = float(np.max(np.abs(lo - (parts["lnE"] + parts["ln1mox"] + parts["lnC"] - np.log(M.RHO / 1000.0)))))

    okidx = np.where(ok)[0]

    def shares(ix):
        ix = np.intersect1d(ix, okidx)
        Z = np.column_stack([parts[k][np.searchsorted(okidx, ix)] for k in ("lnE", "ln1mox", "lnC")])
        C = np.cov(Z, rowvar=False)
        tot = C.sum()
        # each term's contribution to var(sum) = its covariance with the sum
        return dict(lnE=float(C[0].sum() / tot), ln1mox=float(C[1].sum() / tot), lnC=float(C[2].sum() / tot), sd_logodds=float(np.sqrt(tot)))
    res["logodds_shares_prior"] = shares(cons)
    res["logodds_shares_post"] = shares(idx)
    # ---- 2 prior-to-posterior contraction of the generation parameters
    rows = {}
    for name, arr in (("Awaste", p["Awaste"]), ("L0", p["L0"]), ("fss", p["fss"]), ("xCH4", p["xCH4"]), ("ox", p["ox"]), ("Qcoll22", p["Qcoll22"]),
                      ("G22", g["G22"]), ("L0*fss*Awaste (= G22 scaled)", p["L0"] * p["fss"] * p["Awaste"]), ("eta22", g["eta22"])):
        a, b = arr[cons], arr[idx]
        iqr = lambda x: np.subtract(*np.percentile(x, [75, 25]))
        rows[name] = dict(prior_q=q(a), post_q=q(b), contraction=float(1 - iqr(b) / iqr(a)), ks=float(stats.ks_2samp(a, b).statistic))
    res["contraction"] = rows
    # posterior dependence
    Zp = np.column_stack([np.log(p["L0"][idx]), np.log(p["fss"][idx]), np.log(p["Awaste"][idx]), np.log(g["G22"][idx]), g["eta22"][idx], p["ox"][idx],
                          np.log(g["E22_th"][idx])])
    lab = ["lnL0", "lnfss", "lnA", "lnG22", "eta22", "ox", "lnE22"]
    Cc = np.corrcoef(Zp, rowvar=False)
    res["post_corr"] = {"%s,%s" % (lab[i], lab[j]): float(Cc[i, j]) for i in range(len(lab)) for j in range(i + 1, len(lab))}
    Zq = np.column_stack([np.log(p["L0"][cons]), np.log(p["fss"][cons]), np.log(p["Awaste"][cons]), np.log(g["G22"][cons]), g["eta22"][cons], p["ox"][cons],
                          np.log(g["E22_th"][cons])])
    Cq = np.corrcoef(Zq, rowvar=False)
    res["prior_corr"] = {"%s,%s" % (lab[i], lab[j]): float(Cq[i, j]) for i in range(len(lab)) for j in range(i + 1, len(lab))}
    res["marginal_likelihood_base"] = float(w_ln.sum() / g["consistent"].sum())
    res["base"] = H(base, idx, ess=e, eta22=q(g["eta22"][idx]), eta_c=q(g["eta_c"][idx]))
    res["scatter"] = dict(G22=[round(float(x), 1) for x in g["G22"][idx][:2500]], eta22=[round(float(x), 4) for x in g["eta22"][idx][:2500]])
    res["iso"] = dict(C22_med=float(np.median(g["C22"][idx])), ox_med=float(np.median(p["ox"][idx])))

    # ---- 3 alternative generation histories and a widened historical collection prior
    rng = np.random.default_rng(seed + 1)
    tri = lambda a, c, b: rng.triangular(a, c, b, n)
    variants = {}

    def run_variant(label, override):
        m = M.run_model(150000, seed + 3, p_override=override)
        gg = m["g"]
        w = M.likelihood(gg["E22_th"], "lognormal") * gg["consistent"]
        ix, ee = resample(w, 40000, 6)
        variants[label] = H(m, ix, ess=ee, marginal_likelihood=float(w.sum() / gg["consistent"].sum()), eta22=q(gg["eta22"][ix]), eta_c=q(gg["eta_c"][ix]),
                            G22=q(gg["G22"][ix]))
    n2 = 150000
    r2 = np.random.default_rng(seed + 2)
    t2 = lambda a, c, b: r2.triangular(a, c, b, n2)
    run_variant("base prior (wide)", None)
    run_variant("inventory-anchored (L0 90-110, fss 0.45-0.75)", dict(L0=t2(90, 100, 110), fss=t2(0.45, 0.60, 0.75)))
    run_variant("high generation (L0 140-200, fss 0.70-0.95)", dict(L0=t2(140, 170, 200), fss=t2(0.70, 0.85, 0.95)))
    run_variant("low generation (L0 50-90, fss 0.30-0.60)", dict(L0=t2(50, 60, 90), fss=t2(0.30, 0.40, 0.60)))
    k, a_, gam = t2(0.05, 0.09, 0.15), t2(20, 28, 32) - 4.0, t2(0.0, 0.02, 0.05)
    run_variant("first-order-decay history (fss from k, age, growth)", dict(fss=np.clip(k * (1 - np.exp(-(k + gam) * a_)) / (k + gam), 0.05, 1.0)))
    run_variant("widened historical collection (Q22 uniform 8,000-18,000)", dict(Qcoll22=r2.uniform(8000, 18000, n2)))
    res["generation_variants"] = variants

    # ---- 4 representativeness: site-wide scaling and observation error of the satellite emission
    sat = {}
    for s_ in (0.25, 0.5, 0.75, 1.0, 1.5, 2.0):
        w = lognorm_like(g["E22_th"], M.SAT_MED * s_, M.SAT_SLN) * g["consistent"]
        ix, ee = resample(w, 60000, 7)
        sat["scale x%.2f" % s_] = H(base, ix, scale=s_, sln=M.SAT_SLN, ess=ee, eta22=q(g["eta22"][ix]), eta_c=q(g["eta_c"][ix]), E26=q(g["E_atm0_th"][ix]))
    for sl in (0.5, 0.7, 1.0):
        w = lognorm_like(g["E22_th"], M.SAT_MED, sl) * g["consistent"]
        ix, ee = resample(w, 60000, 7)
        sat["sigma_ln %.2f" % sl] = H(base, ix, scale=1.0, sln=sl, ess=ee, eta22=q(g["eta22"][ix]), eta_c=q(g["eta_c"][ix]), E26=q(g["E_atm0_th"][ix]))
    res["satellite_sensitivity"] = sat
    # what would the satellite emission have to be for a given efficiency?
    Cmed = float(np.median(g["C"])); oxm = float(np.median(p["ox"]))
    need = {}
    for eta in (0.14, 0.3, 0.5, 0.7):
        need["%.2f" % eta] = float((Cmed / eta - Cmed) * (1 - oxm) * M.RHO / 1000.0)
    res["emission_for_efficiency"] = need
    # ---- 5 independent observation: Carbon Mapper 2025
    E25 = g["E_atm0_th"]
    pred = q(E25[idx])
    zlog = float(np.log(CM25 / np.median(E25[idx])) / np.sqrt(np.var(np.log(np.maximum(E25[idx], 1e-9))) + CM25_SLN ** 2))
    res["validation"] = dict(obs=CM25, obs_sln=CM25_SLN, pred_q=pred, ratio_obs_to_pred_median=float(CM25 / np.median(E25[idx])),
                             P_pred_below_obs=float((E25[idx] <= CM25).mean()), P_pred_below_obs_with_obs_error=float(
                                 (np.log(np.maximum(E25[idx], 1e-9)) + rng.normal(0, CM25_SLN, idx.size) <= np.log(CM25)).mean()), z_log=zlog,
                             pred_eta_c=q(g["eta_c"][idx]), eta_from_obs=float(eta_closed(CM25, oxm, Cmed)))
    gen_req = (Cmed + CM25 * 1000.0 / ((1 - oxm) * M.RHO)) / (float(np.median(g["C22"][idx])) + M.SAT_MED * 1000.0 / ((1 - oxm) * M.RHO))
    res["validation"]["g_t_required"] = float(gen_req)
    # joint calibrations
    joint = {}
    for lab_, s22, s25, tilt in (("2025 observation alone (sigma 0.5)", None, 0.5, False), ("both observations (0.35 and 0.5)", 0.35, 0.5, True),
                                 ("both, inflated errors (0.7 and 0.7)", 0.7, 0.7, True)):
        w = lognorm_like(E25, CM25, s25) * g["consistent"]
        if s22 is not None:
            w = w * lognorm_like(g["E22_th"], M.SAT_MED, s22)
        ix, ee = resample(w, 60000, 8)
        joint[lab_] = H(base, ix, ess=float(ee), marginal_likelihood=float(w.sum() / g["consistent"].sum()), eta22=q(g["eta22"][ix]), eta_c=q(g["eta_c"][ix]),
                        E22=q(g["E22_th"][ix]), E26=q(E25[ix]), g_t=q(p["g_t"][ix]))
    res["joint"] = joint
    res["prior_E25_q"] = q(E25[cons])
    return res


# ------------------------------------------------------------------ the engine counterfactual
def _pw(p, g, cf_mult=1.0, curtail=0.0, pel=None, decline=None, Q_des=2000.0):
    pp = dict(p)
    pp["cf_pw"] = p["cf_pw"] * cf_mult
    u0 = M.upgrading(pp, g["S_exist"], Q_des, True, p_el=pel)
    afr = M.af(p["r"])
    capex = u0["capex_pw"]
    if decline is None:
        npv = -capex + afr * (u0["mwh_pw"] * (1 - curtail) * (p["p_el"] if pel is None else pel) * p["m_p"] - p["om_pw"] * capex)
        return npv, u0
    k, a, tc = p["k_dec"], p["age"], p["t_close"]
    npv = -capex
    for t in range(M.T):
        dep = np.where(t < tc, (1 - np.exp(-k * (a + t))) / (1 - np.exp(-k * a)),
                       (1 - np.exp(-k * (a + tc))) / (1 - np.exp(-k * a)) * np.exp(-k * (t - tc)))
        S_t = np.maximum(0.0, g["C"] * dep - g["eng"])
        u = M.upgrading(pp, S_t, Q_des, True, p_el=pel)
        npv = npv + (1 + p["r"]) ** (-(t + 1)) * (u["mwh_pw"] * (1 - curtail) * (p["p_el"] if pel is None else pel) * p["m_p"] - p["om_pw"] * capex)
    return npv, u0


def pw_cases(base, idx, n_sub=40000):
    sub = idx[:n_sub]
    P0 = {k: v[sub].copy() for k, v in base["p"].items()}
    rows = []
    cases = [
        ("installed capacity: 23 MW, constant gas supply", dict(P_el=23.0)),
        ("prior range 23-33 MW, constant gas supply (base)", dict()),
        ("planned expansion: 33 MW, constant gas supply", dict(P_el=33.0)),
        ("33 MW, gas supply declining (first-order decay)", dict(P_el=33.0, decline=True)),
        ("base, new engines 25% less available (downtime)", dict(cf_mult=0.75)),
        ("base, 20% of the output curtailed", dict(curtail=0.20)),
        ("base, low tariff (US$45 per MWh)", dict(pel=45.0)),
        ("base, contracted tariff (RenovAr-type)", dict(contract=True)),
        ("stress: 33 MW, decline, 25% downtime, 20% curtailment, US$45", dict(P_el=33.0, decline=True, cf_mult=0.75, curtail=0.20, pel=45.0)),
    ]
    for lab, kw in cases:
        p = {k: v.copy() for k, v in P0.items()}
        if "P_el" in kw:
            p["P_el"] = np.full(sub.size, kw["P_el"])
        g = M.gas_balance(p)
        pel = kw.get("pel")
        pel = np.full(sub.size, pel) if pel is not None else (p["p_el_k"] if kw.get("contract") else None)
        npv, u0 = _pw(p, g, kw.get("cf_mult", 1.0), kw.get("curtail", 0.0), pel, True if kw.get("decline") else None)
        has = g["S_exist"] > 0
        pos = npv > 0
        rows.append(dict(case=lab, P_surplus=float(has.mean()), P_pos_given_surplus=float(pos[has].mean()) if has.any() else None,
                         P_pos_all=float((pos & has).mean()), median_npv_given_surplus=float(np.median(npv[has]) / 1e6) if has.any() else None,
                         median_surplus=float(np.median(g["S_exist"][has])) if has.any() else None,
                         P_surplus_gt500=float((g["S_exist"] > 500).mean())))
    return dict(n=int(sub.size), rows=rows)


# ------------------------------------------------------------------ climate accounting
def climate_variants(base, idx, n_sub=60000):
    rng = np.random.default_rng(1234)
    sub = idx[:n_sub]
    p = {k: v[sub] for k, v in base["p"].items()}
    g = {k: v[sub] for k, v in base["g"].items()}
    n = sub.size
    tri = lambda t: rng.triangular(t[0], t[1], t[2], n)
    slip, efm, dfc, phi = tri(ENGINE_SLIP), tri(EF_MARGINAL), tri(D_F_CF), tri(DISPLACE)
    u0 = M.upgrading(p, g["S_exist"], 2000.0, True)
    has = g["S_exist"] > 0
    ch4_pw, mwh = u0["Qin"] * M.H * p["cf_pw"] * p["xCH4"], u0["mwh_pw"]
    rho_t = M.RHO / 1000.0
    pw = {}
    pw["base (average grid factor, engines as flare)"] = u0["ne_pw"]
    pw["pessimistic engine slip (1-6%)"] = mwh * p["ef_grid"] - ch4_pw * (slip - (1 - p["d_f"])) * rho_t * M.GWP100
    pw["marginal grid factor"] = u0["ne_pw"] + mwh * (efm - p["ef_grid"])
    pw["poor counterfactual flare (efficiency 0.80-0.98)"] = mwh * p["ef_grid"] - ch4_pw * ((1 - p["d_f"]) - (1 - dfc)) * rho_t * M.GWP100
    pw["slip + marginal factor + poor flare"] = mwh * efm - ch4_pw * (slip - (1 - dfc)) * rho_t * M.GWP100
    u6 = u0
    off, emit, exp_, el = u6["ch4"]["offered"], u6["ch4"]["emitted"], u6["exported"], u6["elec"]
    disp = exp_ * M.LHV / 1000.0 * M.EF_NG
    bm = {}
    bm["base (full displacement, average grid factor)"] = u6["ne100"]
    bm["partial displacement of fossil gas (0.3-1.0)"] = phi * disp - (emit - u6["ch4"]["emitted_flare"]) * rho_t * M.GWP100 - el * p["ef_grid"]
    bm["marginal grid factor for upgrader electricity"] = disp - (emit - u6["ch4"]["emitted_flare"]) * rho_t * M.GWP100 - el * efm
    bm["poor counterfactual flare (efficiency 0.80-0.98)"] = disp - (emit - off * (1 - dfc)) * rho_t * M.GWP100 - el * p["ef_grid"]
    bm["all three"] = phi * disp - (emit - off * (1 - dfc)) * rho_t * M.GWP100 - el * efm
    out = dict(n=int(n), P_surplus=float(has.mean()))
    out["PW"] = {k: dict(q=q(v[has] / 1e3), P_pos=float((v[has] > 0).mean())) for k, v in pw.items()}
    out["biomethane"] = {k: dict(q=q(v[has] / 1e3), P_pos=float((v[has] > 0).mean())) for k, v in bm.items()}
    # reference: the capture measures, per year, from the base model on the same draws
    out["S1_S2_kt"] = dict(S1=q(base["S1_co2_100"][sub] / 1e3), S2=q(base["S2_co2_100"][sub] / 1e3))
    out["PW_share_of_S2_median"] = float(np.median(u0["ne_pw"][has]) / np.median(base["S2_co2_100"][sub]))
    # slip at which the engines' climate benefit is exhausted: mwh * ef = ch4_pw * (s - (1 - d_f)) * rho * GWP
    s_star = (1 - p["d_f"]) + mwh * p["ef_grid"] / (ch4_pw * rho_t * M.GWP100)
    out["engine_slip_breakeven_q"] = q(s_star[has])
    out["params"] = dict(slip=ENGINE_SLIP, ef_marginal=EF_MARGINAL, d_f_counterfactual=D_F_CF, displacement=DISPLACE)
    return out


# ------------------------------------------------------------------ figure
def fig_ident(ident, base, idx, fdir):
    import os
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    g, p = base["g"], base["p"]
    fig, ax = plt.subplots(2, 2, figsize=(10.2, 7.6))
    # (a) posterior eta22 against generation, with iso-emission curves
    a = ax[0, 0]
    sc = ident["scatter"]
    G = np.array(sc["G22"]) / 1e3
    a.scatter(G, sc["eta22"], s=2, alpha=0.25, color="#3a6ea5", rasterized=True)
    C22, oxm = ident["iso"]["C22_med"], ident["iso"]["ox_med"]
    Gx = np.linspace(25, 80, 200)
    a.plot(Gx, C22 / (Gx * 1e3), "-", color="k", lw=1.0, label="η = C/G at the median capture")
    for E, mk in ((18, "v"), (28, "o"), (38, "^")):
        Ge = C22 + E * 1000.0 / ((1 - oxm) * M.RHO)
        a.plot(Ge / 1e3, C22 / Ge, mk, color="#b03a2e", ms=7, label="satellite emission %d t/h" % E)
    a.set_xlabel("generation around 2022 (thousand Nm³ CH₄ h⁻¹)"); a.set_ylabel("collection efficiency 2022")
    a.set_title("(a) posterior lies on the curve η = C/G; the emission fixes the point", fontsize=8.5)
    a.legend(fontsize=7); a.set_ylim(0, 0.35)
    # (b) posterior eta22 under alternative generation histories
    b = ax[0, 1]
    names = list(ident["generation_variants"].keys())
    data = [ident["generation_variants"][k]["eta22"] for k in names]
    ypos = np.arange(len(names))[::-1]
    for y, d in zip(ypos, data):
        b.plot([d[0], d[2]], [y, y], color="#3a6ea5", lw=2); b.plot(d[1], y, "o", color="#1f3b5c")
    short = ["base (wide)", "inventory-anchored", "high generation", "low generation", "decay history", "wide capture prior"]
    b.set_yticks(ypos); b.set_yticklabels(short, fontsize=7.5)
    b.set_xlabel("posterior collection efficiency 2022 (median, P5-P95)"); b.set_xlim(0, 0.35)
    b.set_title("(b) alternative generation histories", fontsize=8.5)
    # (c) efficiency 2025-26 against site-wide scaling of the satellite emission
    c = ax[1, 0]
    ks = [k for k in ident["satellite_sensitivity"] if k.startswith("scale")]
    sc_ = [ident["satellite_sensitivity"][k]["scale"] for k in ks]
    ev = [ident["satellite_sensitivity"][k]["eta_c"] for k in ks]
    c.errorbar(sc_, [e[1] for e in ev], yerr=[[e[1] - e[0] for e in ev], [e[2] - e[1] for e in ev]], fmt="o-", color="#1f3b5c", capsize=3, label="2022 satellite emission scaled")
    j = ident["joint"]["both observations (0.35 and 0.5)"]["eta_c"]
    c.axhspan(j[0], j[2], color="#b03a2e", alpha=0.15, label="both observations: P5-P95")
    c.axhline(j[1], color="#b03a2e", lw=1.4, label="both observations: median")
    c.set_xscale("log"); c.set_xticks([0.25, 0.5, 1, 2]); c.set_xticklabels(["0.25", "0.5", "1", "2"]); c.minorticks_off()
    c.set_xlabel("scaling of the 2022 satellite emission (1 = 28 t/h)"); c.set_ylabel("collection efficiency 2025-26")
    c.set_title("(c) representativeness of the satellite constraint", fontsize=8.5); c.legend(fontsize=7); c.set_ylim(0, 0.8)
    # (d) predictive distribution of the 2025-26 surface emission and the independent observation
    d = ax[1, 1]
    E25 = g["E_atm0_th"][idx]
    d.hist(np.log10(np.maximum(E25, 1e-3)), bins=60, color="#3a6ea5", alpha=0.75, density=True, label="prediction (2022 constraint)")
    d.axvline(np.log10(CM25), color="#b03a2e", lw=2, label="Carbon Mapper 2025: %.1f t/h" % CM25)
    d.axvspan(np.log10(M.SAT_LO), np.log10(M.SAT_HI), color="grey", alpha=0.2, label="2022 satellite range 18-38 t/h")
    d.set_xlabel("log10 surface emission 2025-26 (t CH₄ h⁻¹)"); d.set_ylabel("density"); d.legend(fontsize=7)
    d.set_title("(d) independent 2025 observation against prediction", fontsize=8.5)
    for x in ax.ravel():
        x.tick_params(labelsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(fdir, "Fig2_identifiability.png"), dpi=200)
    plt.close(fig)
