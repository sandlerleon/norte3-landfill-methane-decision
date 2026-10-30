"""Figures, tables and results export for NorteIII_MC.py (version 2). One call: run_all(n, outdir)."""
import csv
import json
import os
import time

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import NorteIII_MC as M

plt.rcParams.update({"font.size": 9.5, "axes.spines.top": False, "axes.spines.right": False, "figure.dpi": 200, "savefig.bbox": "tight"})
C1, C2, C3, C4, GR = "#1f4e79", "#c55a11", "#548235", "#7030a0", "#7f7f7f"
LCOL = {"lognormal": C1, "gauss": C3, "window": C2}
LLAB = {"lognormal": "lognormal (base)", "gauss": "Gaussian", "window": "uniform window"}


def fig1(out, post, d):
    g, p = out["g"], out["p"]
    cons = np.where(g["consistent"])[0]
    idx = post["lognormal"]
    fig, ax = plt.subplots(2, 2, figsize=(8.4, 6.4))
    a = ax[0, 0]
    bins = np.linspace(0, 160, 70)
    a.hist(g["G22"][cons] / 1e3, bins, alpha=.45, color=GR, density=True, label="prior (physically consistent)")
    for k in M.LIKELIHOODS:
        a.hist(g["G22"][post[k]] / 1e3, bins, histtype="step", lw=1.5, color=LCOL[k], density=True, label="posterior, " + LLAB[k])
    a.set_xlabel("generation around 2022, 10$^3$ Nm$^3$ CH$_4$/h"); a.set_ylabel("density"); a.legend(fontsize=7, frameon=False)
    a.set_title("(a) Generation constrained by the 2022 satellite estimate", fontsize=9.5)
    a = ax[0, 1]
    bins = np.linspace(0, 80, 80)
    a.hist(g["E22_th"][cons], bins, alpha=.45, color=GR, density=True, label="prior")
    for k in M.LIKELIHOODS:
        a.hist(g["E22_th"][post[k]], bins, histtype="step", lw=1.5, color=LCOL[k], density=True, label=LLAB[k])
    a.axvspan(M.SAT_LO, M.SAT_HI, color=C2, alpha=.10)
    a.set_xlabel("modelled surface emission at the observation date, t CH$_4$/h"); a.set_ylabel("density"); a.legend(fontsize=7, frameon=False)
    a.set_title("(b) Three observation-error models", fontsize=9.5)
    a = ax[1, 0]
    bins = np.linspace(0, 0.45, 70)
    a.hist(g["eta22"][idx], bins, alpha=.55, color=C2, density=True, label="2022 (capture as then)")
    a.hist(g["eta_c"][idx], bins, alpha=.55, color=C1, density=True, label="2025-26 (current capture)")
    a.set_xlabel("inferred collection efficiency (model output, not a measurement)"); a.set_ylabel("density"); a.legend(fontsize=7.5, frameon=False)
    a.set_title("(c) Collection efficiency, two periods", fontsize=9.5)
    a = ax[1, 1]
    for lo, hi, c, lab in ((0, 25, C3, "P$_{el}$ ≤ 25 MW"), (31, 40, C2, "P$_{el}$ ≥ 31 MW (expansion complete)")):
        m = idx[(p["P_el"][idx] >= lo) & (p["P_el"][idx] <= hi)]
        a.hist(g["S_exist"][m], np.linspace(0, 4500, 50), alpha=.6, color=c, label=lab, density=True)
    a.set_xlabel("surplus CH$_4$ beyond the engines, Nm$^3$/h"); a.set_ylabel("density"); a.legend(fontsize=7.5, frameon=False)
    a.set_title("(d) Surplus shrinks as engines expand", fontsize=9.5)
    fig.tight_layout(); fig.savefig(d + "/Fig1_gas_balance.png"); plt.close(fig)


def sc_star_curve(out, idx, eps, delta):
    q = {k: np.median(v[idx]) for k, v in out["p"].items()}
    ox, d_f, rho = q["ox"], q["d_f"], q["rho_r"]
    ox_cov = ox * (1 - delta * eps); ox_r = ox * rho
    A0 = (1 - ox) - (1 - eps) * (1 - ox_cov) - eps * (1 - ox_r)
    A1 = eps * (1 - ox_r) - eps * (1 - d_f)
    return -A0 / A1


def fig2(out, idx, d):
    p = out["p"]
    fig, ax = plt.subplots(1, 2, figsize=(8.6, 3.9))
    a = ax[0]
    data = [out["S2_cover_only_ch4"][idx] / 1e3, out["S3_cover_only_ch4"][idx] / 1e3]
    bp = a.boxplot(data, widths=.5, patch_artist=True, showfliers=False, whis=(5, 95), medianprops=dict(color="k"))
    for b, c in zip(bp["boxes"], (C1, C2)):
        b.set_facecolor(c); b.set_alpha(.6)
    a.axhline(0, color="k", lw=.8, ls="--")
    a.set_xticks([1, 2]); a.set_xticklabels(["conventional\ncover", "experimental\ncoating"]); a.set_ylabel("net CH$_4$ avoided by the cover alone, kt/yr")
    pc = (out["cov_conv"]["avoided"][idx] > 0).mean(); pk = (out["cov_coat"]["avoided"][idx] > 0).mean()
    a.set_title("(a) Net methane effect of a selective cover\nP(net benefit) = %.2f / %.2f" % (pc, pk), fontsize=9.5)
    a = ax[1]
    sub = idx[:4000]
    adv = out["cov_conv"]["avoided"][sub] > 0
    a.scatter(p["eps_conv"][sub][adv], p["s_c"][sub][adv], s=3, color=C3, alpha=.35, label="net benefit")
    a.scatter(p["eps_conv"][sub][~adv], p["s_c"][sub][~adv], s=5, color=C2, alpha=.8, label="net increase")
    e = np.linspace(.05, .95, 100)
    for dl, ls in ((0.2, ":"), (0.6, "-"), (1.0, "--")):
        a.plot(e, np.clip(sc_star_curve(out, idx, e, dl), 0, 1), ls=ls, color="k", lw=1.2, label="analytic $s_c^*$, δ$_{ox}$=%.1f" % dl)
    a.set_xlabel("barrier effectiveness ε"); a.set_ylabel("capture share of blocked gas $s_c$"); a.set_ylim(0, .8)
    a.legend(fontsize=7, frameon=True, framealpha=.85, loc="upper right"); a.set_title("(b) Break-even boundary: analytic vs Monte Carlo", fontsize=9.5)
    fig.tight_layout(); fig.savefig(d + "/Fig2_cover.png"); plt.close(fig)


def fig3(out, idx, d):
    has = idx[out["g"]["S_exist"][idx] > 0]
    fig, (a, b) = plt.subplots(1, 2, figsize=(9.6, 4.2), gridspec_kw=dict(width_ratios=[8, 2.2]))
    data = [out[s + "_npv"][idx] / 1e6 for s in M.SCEN]
    bp = a.boxplot(data, patch_artist=True, showfliers=False, whis=(5, 95), medianprops=dict(color="k"))
    cols = [C1, C1, C2, C3, C3, C4, C4, C4]
    for bx, c in zip(bp["boxes"], cols):
        bx.set_facecolor(c); bx.set_alpha(.55)
    a.axhline(0, color="k", lw=.8, ls="--")
    a.set_xticks(range(1, len(M.SCEN) + 1)); a.set_xticklabels(M.SCEN); a.set_ylabel("incremental NPV vs S0, MUSD (real USD, 20 yr)")
    lo, hi = a.get_ylim(); a.set_ylim(lo, hi + 0.12 * (hi - lo))
    for i, s in enumerate(M.SCEN):
        a.text(i + 1, hi + 0.04 * (hi - lo), "P(>0)=%.2f" % (out[s + "_npv"][idx] > 0).mean(), ha="center", va="bottom", fontsize=6.8)
    a.set_title("(a) Eight integrated interventions (no credit revenue)", fontsize=9.5)
    dd = [out["u0"]["npv_pw"][has] / 1e6, out["u0k"]["npv_pw"][has] / 1e6]
    bp = b.boxplot(dd, patch_artist=True, showfliers=False, whis=(5, 95), medianprops=dict(color="k"), widths=.55)
    for bx in bp["boxes"]:
        bx.set_facecolor(C2); bx.set_alpha(.5)
    b.axhline(0, color="k", lw=.8, ls="--")
    b.set_xticks([1, 2]); b.set_xticklabels(["merchant", "contract"], fontsize=8)
    lo, hi = b.get_ylim(); b.set_ylim(lo, hi + 0.12 * (hi - lo))
    for i, v in enumerate(dd):
        b.text(i + 1, hi + 0.04 * (hi - lo), "P(>0)=%.2f" % (v > 0).mean(), ha="center", va="bottom", fontsize=6.8)
    b.set_title("(b) Power alternative\n(existing surplus)", fontsize=9.5)
    fig.tight_layout(); fig.savefig(d + "/Fig3_npv_scenarios.png"); plt.close(fig)


def fig4(out, idx, sweep, d):
    u0 = out["u0"]
    has = idx[out["g"]["S_exist"][idx] > 0]
    fig, ax = plt.subplots(1, 2, figsize=(8.8, 3.9))
    a = ax[0]
    bins = np.linspace(0, 1.6, 80)
    a.hist(np.clip(u0["pstar_gnc"][has], 0, 1.6), bins, color=C4, alpha=.65, density=True, label="bio-GNC break-even (NPV = 0)")
    a.hist(np.clip(u0["pstar_gnc_pw"][has], 0, 1.6), bins, color=C2, alpha=.55, density=True, label="bio-GNC parity with power engines")
    a.axvspan(0.13, 0.40, color=C3, alpha=.18, label="bio-GNC price prior (2025 benchmarks)")
    a.set_xlabel("realised bio-GNC plant-gate price, USD/Nm$^3$"); a.set_ylabel("density")
    a.legend(fontsize=7.2, frameon=False); a.set_title("(a) Price required vs price assumed", fontsize=9.5)
    a = ax[1]
    Q = [s_["Q"] for s_ in sweep]
    a.plot(Q, [s_["P"] for s_ in sweep], "o-", color=C4, label="P(NPV>0) biomethane")
    a.plot(Q, [s_["P_pw"] for s_ in sweep], "s--", color=C2, label="P(NPV>0) power engines")
    a.set_xscale("log"); a.set_xticks(Q); a.set_xticklabels([str(int(x)) for x in Q]); a.minorticks_off()
    a.set_ylim(0, 1.02); a.set_xlabel("design raw-gas capacity, Nm$^3$/h"); a.set_ylabel("probability NPV > 0")
    a.legend(fontsize=7.5, frameon=False, loc="center right"); a.set_title("(b) Sizing on existing surplus only", fontsize=9.5)
    fig.tight_layout(); fig.savefig(d + "/Fig4_route_and_sizing.png"); plt.close(fig)


def fig5(out, idx, d):
    p = out["p"]
    fig, ax = plt.subplots(1, 2, figsize=(8.6, 3.9))
    a = ax[0]
    q = {k: np.median(v[idx]) for k, v in p.items()}
    lc = np.median(out["pvc"]["lcoe"][idx])
    c = np.linspace(2, 150, 200)
    for L, col in ((3, C2), (8, C1), (15, C3)):
        eta = c * q["cap_prem"] * (M.crf(q["r"], L) + q["om_pt"]) / (lc * q["H_poa"] * q["pr_pt"])
        a.plot(c, eta * 100, color=col, label="life %d yr" % L)
    a.axhline(5, color=GR, ls=":", lw=1); a.text(100, 5.4, "5% (illustrative)", fontsize=7.5, color=GR)
    a.set_ylim(0, 40); a.set_xlabel("installed paint cost, USD/m$^2$"); a.set_ylabel("break-even efficiency η*, %")
    a.legend(fontsize=7.5, frameon=False); a.set_title("(a) Efficiency needed to match conventional PV (LCOE)", fontsize=9.5)
    a = ax[1]
    ratio = out["pvp"]["lcoe"][idx] / out["pvc"]["lcoe"][idx]
    a.hist(np.log10(ratio), np.linspace(-1.2, 1.6, 70), color=C1, alpha=.7)
    a.axvline(0, color="k", lw=1)
    a.set_xlabel("log$_{10}$(LCOE paint / LCOE conventional PV)"); a.set_ylabel("draws")
    a.set_title("(b) P(paint cheaper) = %.2f under wide priors" % (ratio < 1).mean(), fontsize=9.5)
    fig.tight_layout(); fig.savefig(d + "/Fig5_paint_vs_pv.png"); plt.close(fig)


def fig6(out, idx, d):
    fig, a = plt.subplots(figsize=(7.4, 4.2))
    for s, c in (("S1", C1), ("S2", C3), ("S3", C2), ("S6b", C4), ("S7", GR)):
        npv = out[s + "_npv"][idx]; co2 = out[s + "_co2_100"][idx]
        pos = co2 > 1
        ab = -npv[pos] / (out["afr"][idx][pos] * co2[pos])
        x = np.sort(ab); y = np.arange(1, x.size + 1) / x.size
        a.plot(np.clip(x, .3, 300), y, color=c, label=M.SCEN_LABEL[s])
    for cp in (10, 25, 50):
        a.axvline(cp, color="k", ls=":", lw=.8); a.text(cp * 1.02, .03, "$%d" % cp, fontsize=7.5)
    a.set_xscale("log"); a.set_xlabel("levelised abatement cost, USD per tCO$_2$e (GWP100)"); a.set_ylabel("cumulative probability")
    a.legend(fontsize=7, frameon=False, loc="lower right"); a.set_title("Cost of avoided methane (no credit revenue)")
    fig.tight_layout(); fig.savefig(d + "/Fig6_abatement_cost.png"); plt.close(fig)


def fig7(res, d):
    fig, ax = plt.subplots(1, 3, figsize=(11.4, 3.9))
    for a, key, ttl in ((ax[0], "sens_S6b_npv", "(a) NPV of S6b (S1 + biomethane)"), (ax[1], "sens_PW_npv", "(b) NPV of the power alternative"),
                        (ax[2], "sens_S2_ch4", "(c) Net CH$_4$ avoided by the cover")):
        items = res["posterior"][key][:10][::-1]
        a.barh([k for k, _ in items], [v for _, v in items], color=[C1 if v > 0 else C2 for _, v in items])
        a.axvline(0, color="k", lw=.8); a.set_xlabel("Spearman rank correlation"); a.set_title(ttl, fontsize=9.5)
    fig.tight_layout(); fig.savefig(d + "/Fig7_sensitivity.png"); plt.close(fig)


def fig8(out, post, rob, d):
    fig, ax = plt.subplots(1, 2, figsize=(9.6, 3.9))
    a = ax[0]
    cps = np.linspace(0, 60, 25)
    cons = np.where(out["g"]["consistent"])[0]
    for s, c in (("S1", C1), ("S2", C3), ("S6b", C4)):
        for reg, ls, m in (("prior", "--", cons), ("posterior", "-", post["lognormal"])):
            npv, co2, afr = out[s + "_npv"][m], out[s + "_co2_100"][m], out["afr"][m]
            a.plot(cps, [((npv + afr * cp * co2) > 0).mean() for cp in cps], ls=ls, color=c, label="%s, %s" % (s, reg))
    a.set_xlabel("credit price, USD per tCO$_2$e (GWP100)"); a.set_ylabel("P(NPV > 0)")
    a.axvspan(2, 12, color=GR, alpha=.12); a.text(2.5, .93, "2025 market\nrange", fontsize=7, color=GR)
    a.legend(fontsize=7, frameon=False, ncol=2, loc="center right"); a.set_title("(a) Credit price needed for a positive NPV", fontsize=9.5)
    a = ax[1]
    sw = rob["discount_sweep"]
    r = [100 * x["r"] for x in sw]
    for key, c, lab in (("S1", C1, "S1"), ("S2", C3, "S2"), ("S6b", C4, "S6b"), ("PW", C2, "power alternative")):
        a.plot(r, [x[key] for x in sw], "o-", color=c, label=lab, ms=4)
    a.set_xlabel("real discount rate, %"); a.set_ylabel("P(NPV > 0)"); a.set_ylim(0, 1.02); a.legend(fontsize=7.5, frameon=False)
    a.set_title("(b) Discount-rate sensitivity", fontsize=9.5)
    fig.tight_layout(); fig.savefig(d + "/Fig8_credit_discount.png"); plt.close(fig)


def fig9(rob, d):
    rows = rob["variants"]
    labs = [r["variant"].replace("gauss", "Gaussian").replace("window", "uniform window 18-38 t/h") for r in rows]
    fig, ax = plt.subplots(1, 3, figsize=(11.6, 4.6), sharey=True)
    y = np.arange(len(rows))[::-1]
    for a, key, ttl, fmt in ((ax[0], "S2_avoided_kt", "S2 avoided, ktCO$_2$e/yr (median)", "%.0f"),
                             (ax[1], "S6b_npv", "S6b NPV, MUSD (median)", "%.1f"),
                             (ax[2], "P_pw_pos", "P(power alternative NPV > 0)", "%.2f")):
        v = [r[key] for r in rows]
        a.barh(y, v, color=[C1 if i < 3 else (GR if i == 3 else C3) for i in range(len(rows))], alpha=.75)
        for yy, vv in zip(y, v):
            a.text(vv, yy, " " + fmt % vv, va="center", fontsize=7)
        a.axvline(rows[0][key], color="k", lw=.8, ls=":")
        a.set_title(ttl, fontsize=9)
    ax[0].set_yticks(y); ax[0].set_yticklabels(labs, fontsize=7.5)
    fig.tight_layout(); fig.savefig(d + "/Fig9_robustness.png"); plt.close(fig)


def fig10(res, d):
    bal = res["posterior"]["balances_median"]
    keys = ["S0", "S1", "S2", "S4", "S6", "S6b", "S7"]
    comp = [("ch4_emit", "emitted as CH$_4$", C2), ("ch4_ox", "oxidised in cover soil", C3), ("ch4_destroy", "destroyed (engines, flares, tail gas)", C1),
            ("ch4_export", "exported as biomethane", C4)]
    fig, ax = plt.subplots(1, 2, figsize=(10.0, 4.0))
    a = ax[0]
    bottom = np.zeros(len(keys))
    for k, lab, c in comp:
        v = np.array([bal[s][k] * M.RHO / 1e6 for s in keys])
        a.bar(keys, v, bottom=bottom, color=c, alpha=.75, label=lab)
        bottom += v
    a.set_ylabel("kt CH$_4$/yr (median draw)"); a.legend(fontsize=7, frameon=False, loc="lower right")
    a.set_title("(a) Fate of the generated methane", fontsize=9.5)
    a = ax[1]
    ks = keys[1:]
    ch4 = [(bal["S0"]["co2e"] - bal[s]["co2e"] + bal[s]["fossil"]) / 1e3 for s in ks]
    fos = [-bal[s]["fossil"] / 1e3 for s in ks]
    xx = np.arange(len(ks))
    a.bar(xx - .2, ch4, .4, color=C1, alpha=.75, label="methane avoided (GWP100)")
    a.bar(xx + .2, fos, .4, color=C3, alpha=.75, label="fossil CO$_2$ displaced − grid electricity used")
    a.axhline(0, color="k", lw=.8)
    a.set_xticks(xx); a.set_xticklabels(ks); a.set_ylabel("ktCO$_2$e/yr vs S0 (median draw)"); a.legend(fontsize=7, frameon=False)
    a.set_title("(b) Climate account from the balances", fontsize=9.5)
    fig.tight_layout(); fig.savefig(d + "/Fig10_balances.png"); plt.close(fig)


def figS1(d):
    fig, a = plt.subplots(figsize=(6.4, 3.6))
    for seed, c in ((11, C1), (12, C2), (13, C3)):
        o = M.run_model(150000, seed)
        idx, ess, _ = M.posterior_index(o["g"], "lognormal", n_post=60000, seed=seed)
        x = (o["S6b_npv"][idx] > 0).astype(float); k = np.arange(1, x.size + 1)
        a.plot(k[200::50], (np.cumsum(x) / k)[200::50], color=c, lw=1, label="seed %d (ESS %.0f)" % (seed, ess))
    a.set_xlabel("resampled draws"); a.set_ylabel("running P(NPV>0), S6b"); a.set_ylim(0, .12); a.legend(frameon=False, fontsize=8)
    fig.tight_layout(); fig.savefig(d + "/FigS1_convergence.png"); plt.close(fig)


def _r(x, k=4):
    return None if x is None else round(float(x), k)


def run_all(n=300000, outdir="results"):
    t0 = time.time()
    os.makedirs(outdir, exist_ok=True)
    fdir = os.path.join(outdir, "..", "figures")
    os.makedirs(fdir, exist_ok=True)
    out = M.run_model(n)
    post, ess, acc = {}, {}, {}
    for k in M.LIKELIHOODS:
        post[k], ess[k], acc[k] = M.posterior_index(out["g"], k)
    cons = np.where(out["g"]["consistent"])[0]
    res = dict(n=n, version="2.0.0", n_consistent=int(cons.size), ess=ess, acceptance=acc,
               prior=M.summarize(out, cons, "prior"), posterior=M.summarize(out, post["lognormal"], "posterior (lognormal, base)"),
               posterior_gauss=M.summarize(out, post["gauss"], "posterior (Gaussian)"),
               posterior_window=M.summarize(out, post["window"], "posterior (window 18-38 t/h)"))
    print("base summaries [%.0fs]" % (time.time() - t0))
    res["sweep"] = M.design_sweep()
    rob = M.robustness()
    res["robustness"] = rob
    print("robustness [%.0fs]" % (time.time() - t0))
    params = [dict(name=a, dist=b, args=list(c), tag=t, desc=ds) for a, b, c, t, ds in M.P]
    res["params"] = params
    with open(os.path.join(outdir, "results.json"), "w") as f:
        json.dump(res, f, indent=1)
    with open(os.path.join(outdir, "parameters.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["name", "distribution", "arguments", "tag", "description"])
        for q in params:
            w.writerow([q["name"], q["dist"], q["args"], q["tag"], q["desc"]])
    with open(os.path.join(outdir, "scenario_summary_posterior.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["scenario", "NPV_P5", "NPV_P50", "NPV_P95", "P_NPV_pos", "NPV_after_tax_P50", "tCO2e100_P5", "tCO2e100_P50", "tCO2e100_P95", "abate_P50"])
        for s in M.SCEN + ["PW"]:
            r = res["posterior"]["scen"][s]
            w.writerow([s] + [_r(v, 3) for v in r["npv_q"]] + [_r(r["P_npv_pos"])] + [_r(r.get("npv_after_tax_q", [None] * 3)[1], 3)]
                       + [_r(v, 0) for v in r["co2_100_q"]] + [_r(r["abate_q"][1], 1)])
    with open(os.path.join(outdir, "robustness_variants.csv"), "w", newline="") as f:
        keys = ["variant", "eta22", "eta_c", "E26", "S2_avoided_kt", "P_cover", "S6b_npv", "P_pw_pos", "P_up_beats_pw", "pstar_gnc", "abate_S1", "abate_S2",
                "any_scen_median_pos"]
        w = csv.writer(f); w.writerow(keys)
        for r in rob["variants"]:
            w.writerow([r[k] if isinstance(r[k], (str, bool)) else round(r[k], 4) for k in keys])
    with open(os.path.join(outdir, "balances_median.csv"), "w", newline="") as f:
        bal = res["posterior"]["balances_median"]
        keys = ["ch4_emit", "ch4_ox", "ch4_destroy", "ch4_export", "resid", "c_ch4", "c_co2_bio", "c_export", "co2e", "fossil", "elec_out", "elec_in", "e_product"]
        w = csv.writer(f); w.writerow(["scenario"] + keys)
        for s, b in bal.items():
            w.writerow([s] + [round(b.get(k, 0.0), 1) for k in keys])
    idx = post["lognormal"]
    fig1(out, post, fdir); fig2(out, idx, fdir); fig3(out, idx, fdir); fig4(out, idx, res["sweep"], fdir)
    fig5(out, idx, fdir); fig6(out, idx, fdir); fig7(res, fdir); fig8(out, post, rob, fdir); fig9(rob, fdir); fig10(res, fdir); figS1(fdir)
    print("done ->", outdir, "[%.0fs]" % (time.time() - t0))
