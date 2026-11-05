# -*- coding: utf-8 -*-
"""Manuscript (version 3, revised for Waste Management after the second review) and Supplementary Information, built from results/results.json so
that every number in the text is the model's.

    python build_manuscript.py      -> manuscript/NorteIII_Waste_Management_Manuscript_v3.docx, NorteIII_Supplementary_Information_v3.docx
"""
import json
import os
import re

import docx_engine as E
import NorteIII_MC as M
from norte_references import LIB

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
FIG = os.path.join(ROOT, "figures")
OUT = os.path.join(ROOT, "manuscript")
R = json.load(open(os.path.join(ROOT, "results", "results.json"), encoding="utf-8"))
DOIS = json.load(open(os.path.join(HERE, "dois.json"), encoding="utf-8")) if os.path.exists(os.path.join(HERE, "dois.json")) else {}
GITHUB = "https://github.com/sandlerleon/norte3-landfill-methane-decision"
P, PR = R["posterior"], R["prior"]
bm = P["balances_median"]
HY, SC, GA = P["hyp"], P["scen"], P["gas"]
RB = R["robustness"]
RVW = R["review"]
ID, PWC, CLV = RVW["ident"], RVW["pw"], RVW["climate"]
GV, SS, JT, VAL = ID["generation_variants"], ID["satellite_sensitivity"], ID["joint"], ID["validation"]
TESTS = json.load(open(os.path.join(ROOT, "results", "tests.json"), encoding="utf-8"))
assert TESTS["all_passed"], "automated tests have not all passed"
NTEST = TESTS["n"]
VERSION = "2.1.1"
TITLE = ("Landfill methane recovery and use under deep uncertainty: a satellite-constrained Monte Carlo decision model for the Norte III landfill, "
         "Buenos Aires")


# ------------------------------------------------------------------------------------------------ number formatting
def n(x, d=0):
    s = "{:,.{d}f}".format(x, d=d)
    return s.replace("-", "−")


def q3(v, d=0, scale=1.0):
    return "%s (%s to %s)" % (n(v[1] * scale, d), n(v[0] * scale, d), n(v[2] * scale, d))


def qc(v, d=2, scale=1.0):
    """compact: median (P5–P95)"""
    return "%s (%s–%s)" % (n(v[1] * scale, d), n(v[0] * scale, d), n(v[2] * scale, d))


def pct(x, d=0):
    return n(100.0 * x, d) + "%"


def pct0(x, d=0):
    """percentage, floored at zero (contraction values can be slightly negative from sampling noise)"""
    return pct(max(x, 0.0), d)


def prange(vals, d=0):
    a, b = pct(min(vals), d), pct(max(vals), d)
    return a if a == b else "%s to %s" % (a, b)


def var(name):
    return [r for r in RB["variants"] if r["variant"] == name][0]


def gv(prefix):
    return [v for k, v in GV.items() if k.startswith(prefix)][0]


def pwrow(prefix):
    return [r for r in PWC["rows"] if r["case"].startswith(prefix)][0]


# ------------------------------------------------------------------------------------------------ author-year citations
class Harvard:
    PAT = re.compile(r"\[(!?)@([^\]]+)\]")

    def __init__(self, lib):
        self.lib, self.used = lib, set()

    def scan(self, text):
        for m in self.PAT.finditer(text):
            for k in [x.strip().lstrip("@") for x in m.group(2).split(";")]:
                if k not in self.lib:
                    raise KeyError(k)
                self.used.add(k)

    def resolve(self, text):
        def rep(m):
            keys = [x.strip().lstrip("@") for x in m.group(2).split(";")]
            if m.group(1) == "!":                                          # narrative: Author et al. (Year)
                c = self.lib[keys[0]][0]
                a, y = c.rsplit(", ", 1)
                return "%s (%s)" % (a, y)
            keys = sorted(keys, key=lambda k: self.lib[k][1])                # groups of references: alphabetical, then chronological
            return "(" + "; ".join(self.lib[k][0] for k in keys) + ")"
        return self.PAT.sub(rep, text)

    def entries(self):
        unused = [k for k in self.lib if k not in self.used]
        if unused:
            raise ValueError("never cited: " + ", ".join(unused))
        return sorted((self.lib[k][1], self.lib[k][2]) for k in self.used)


# "US$" must not open an inline-math span in the engine: protect it with a private-use character and restore it in the runs
_add_runs = E.add_runs


def _add_runs_dollar(par, text, *a, **k):
    n0 = len(par.runs)
    _add_runs(par, text.replace("US$", "US"), *a, **k)
    for r in par.runs[n0:]:
        if "" in r.text:
            r.text = r.text.replace("", "$")
    return par


E.add_runs = _add_runs_dollar

B = []
add = B.append
g, h = GA, HY
nin = len([p for p in M.P if p[0] not in M.ROBUST_ONLY])
J2 = JT["both observations (0.35 and 0.5)"]
J1 = JT["2025 observation alone (sigma 0.5)"]
J3 = JT["both, inflated errors (0.7 and 0.7)"]
gen_eta = [GV[k]["eta22"][1] for k in GV]
gen_etac = [GV[k]["eta_c"][1] for k in GV]
sat_keys = [k for k in SS if k.startswith("scale")]
eta_over_all = [v["eta_c"][1] for v in list(SS.values()) + list(JT.values()) + list(GV.values())]

# ============================================================================================ front matter
add(("title", TITLE))
add(("author", "Leon Sandler"))
add(("small", "Independent Researcher, Northbrook, Illinois, USA"))
add(("small", "ORCID: https://orcid.org/0009-0007-4584-808X"))
add(("small", "Corresponding author: leon.sandler@alumni.swinburne.edu"))
add(("blank",))
add(("h1", "Highlights"))
for t in ("Satellite-constrained methane balance of a megasite, calibrated in two periods",
          "Capture efficiency of %s to %s is conditional on the data, not measured" % (n(g["eta_c"][1], 2), n(J1["eta_c"][1], 2)),
          "No integrated intervention has a positive median NPV without carbon credits",
          "Added engines pay only where surplus gas exists; biomethane needs US$%s per MMBtu" % n(h["pstar_gnc_mmbtu_q"][1]),
          "Cover helps only if captured share of blocked gas exceeds an analytic threshold"):
    add(("bullet", t))
add(("h1", "Abstract"))
add(("p0", "Very large landfills are major methane sources, but site decisions rarely join operator-reported capture, independent emission estimates "
            "and the economics of competing gas uses. We built a Latin-hypercube Monte Carlo decision model (300,000 draws, %d inputs) of landfill-gas "
            "generation, collection, surface emission, oxidation, selective covers, biomethane upgrading, additional power generation and photovoltaics, "
            "and applied it to the Norte III landfill in Buenos Aires. A bottom-up generation prior is constrained by satellite emission estimates at "
            "their own date (2022) and carried to 2025–26. The inferred collection efficiency, %s in 2022 and %s in 2025–26 (median, 90%% interval), "
            "follows from the emission, oxidation and reported capture, is conditional on the data and not a measurement, and increases to %s with an "
            "independent 2025 observation that the model overpredicts by a factor of %s. Under no-credit conditions none of eight integrated scenarios has "
            "a positive median net present value; wellfield optimization with a selective cover abates methane at a median US$%s per tCO₂e. Additional "
            "engines are profitable in %s of draws that have surplus gas, but in %s of all operating states after the planned expansion; biomethane needs "
            "US$%s per Nm³ (US$%s per MMBtu). A cover helps only if the captured share of blocked gas exceeds an analytic break-even (median %s). "
            "Conclusions hold under alternative generation histories, satellite scaling and dated Argentine benchmarks."
            % (nin, q3(g["eta22"], 2), q3(g["eta_c"], 2), q3(J1["eta_c"], 2), n(1.0 / VAL["ratio_obs_to_pred_median"], 1), n(SC["S2"]["abate_q"][1], 1),
               pct(h["H3_P_power_npv_pos"]), pct(pwrow("planned expansion")["P_pos_all"]), n(h["pstar_gnc_q"][1], 2), n(h["pstar_gnc_mmbtu_q"][1], 0),
               n(h["H1_sc_star_q"][1], 2))))
add(("h1", "Keywords"))
add(("p0", "Landfill gas; Methane mitigation; Satellite constraint; Biomethane; Monte Carlo decision analysis; Techno-economic analysis"))

# ============================================================================================ 1 Introduction
add(("h1", "1. Introduction"))
add(("p", "Landfills are among the largest anthropogenic sources of methane, and airborne and satellite surveys have shown that a small number of very "
          "large sites contribute a disproportionate share of urban emissions [@Duren2019;@Maasakkers2022;@Schuit2023;@Cusworth2024]. Inventories "
          "derived from first-order decay models and assumed collection efficiencies can differ substantially from measurement-based estimates "
          "[@Stuart2026], and at facility scale satellite estimates often do not correlate with reported or modeled values [@Dogniaux2025]. Collection "
          "efficiency itself is poorly constrained in the literature [@Spokas2006;@Giordano2024;@Saul2026]. The Norte III "
          "landfill in Greater Buenos Aires is one of the large sites identified from space. Its operator reports a large and growing capture system "
          "with on-site power generation [@CEAMSE2026;@Canal26], while satellite observations place surface emissions at tens of tonnes of methane per "
          "hour [@Maasakkers2022;@Bloomberg2022]. Both statements can hold only if most of the methane generated is not collected, and a decision model for "
          "the site must respect that tension."))
add(("p", "Mitigation options are numerous: wellfield tuning and leak repair, engineered covers, new uses of recovered gas (additional engines, "
          "compressed bio-GNC for vehicles, pipeline biomethane), on-site solar generation and gas buffering. Techno-economic studies usually evaluate "
          "such options one at a time, with point estimates and a fixed gas supply [@Ghafoori2022;@Agostini2024], whereas the measurement literature "
          "quantifies emissions or collection efficiency without evaluating the decisions that follow from them [@Maasakkers2022;@Cusworth2024;"
          "@Giordano2024]. Neither can answer how a decision-maker should choose between more capture and better use of the gas already "
          "collected when the site's emission is known only through uncertain remote sensing: the climate benefit of a measure is rarely tied to a "
          "mass balance in which blocked or captured gas can reappear elsewhere; uncertainty in prices, exchange rates, taxes and financing is usually "
          "represented by a few scenarios rather than propagated; and the existence of surplus gas for any new use is assumed, not tested."))
add(("p", "This paper therefore asks one question: under which observable physical and economic conditions does additional methane capture "
          "outperform alternative uses of already collected landfill gas? We answer it for a single landfill with a satellite-constrained decision "
          "model that (i) infers the collection efficiency from the satellite emission, the oxidation and the reported capture, and states what that "
          "inference does and does not identify (Section 4.2) and how it compares with an independent 2025 observation (Section 4.3); (ii) closes "
          "methane, carbon and energy balances for every scenario, so that blocked or redirected gas is never lost from the account; (iii) separates "
          "the probability that additional engines are profitable given that surplus gas exists from the probability across all operating states "
          "(Section 4.6); (iv) reports the climate account of each use under alternative counterfactuals (Section 4.7); and (v) derives closed-form "
          "break-evens for selective covers (the minimum captured share of blocked gas) and for photovoltaic coatings (the minimum efficiency), "
          "verified against the simulation. Economic inputs are anchored to dated Argentine benchmarks."))
add(("p", "The study is a screening analysis. It uses no site measurements beyond published operator and satellite figures, it treats prices and "
          "unit costs as distributions conditioned on dated benchmarks, and it makes no claim about what the operator will do or about the accuracy "
          "of the operator's reported figures. Its purpose is to show which decisions are robust to the stated uncertainty, which are not, and which "
          "measurements would resolve them."))

# ============================================================================================ 2 Case study
add(("h1", "2. Case study, reported data and benchmarks"))
add(("h2", "2.1 Operator data and top-down estimates"))
add(("p", "Norte III receives roughly 18,000 t of municipal solid waste per day [@CEAMSE2026]. CEAMSE reports captured biogas of 13,800 m³ h⁻¹ "
          "in 2025, increasing to 16,000 m³ h⁻¹ in April 2026 [@Canal26], against a maximum captured flow of 13,100 Nm³ h⁻¹ in 2013 [@Rosso2016]. "
          "Biogas-fired power plants have operated on site since 2012 [@Canal26]; the operator statement summarized in the project white paper "
          "[@WhitePaper2026] gives 23 MW installed in 2020 and an expansion to 33 MW planned for 2026. Gas not used by the engines is flared. These are "
          "operator statements: they are not measured fugitive emissions, they do not state the methane fraction, and they do not establish that any "
          "gas is uncommitted."))
add(("p", "Top-down estimates come from satellites. [!@Maasakkers2022] combined TROPOMI hot-spot detection with high-resolution GHGSat target-mode "
          "observations and reported emissions of 3 to 29 t CH₄ h⁻¹ from strongly emitting landfills in four cities, with the Buenos Aires site near "
          "28 t h⁻¹ [@SRON2022]; a GHGSat observation in September 2022 implied 18 to 38 t h⁻¹ [@Bloomberg2022]. These estimates refer to 2019–2022 and "
          "are retrievals at the time of observation, not annual facility means. Capture has since increased, and comparing them with a 2025–26 "
          "capture rate, as the first version of this analysis did, mixes periods. CEAMSE disputes the characterization of the site [@Canal26]. The "
          "satellite estimates are therefore used as a constraint at their own date, with an explicit observation-error model, not as ground truth "
          "(Section 3.2). One later observation is independent of the calibration: Carbon Mapper retrievals from Tanager-1 and EMIT for 2025, summarized "
          "by the UCLA STOP Methane project as an average of overpass emission rates of %s t CH₄ h⁻¹ for the Greater Buenos Aires landfill operated by "
          "CEAMSE [@STOP2026]. The operator replies that the ranking rests on point satellite measurements under particular atmospheric conditions, which limit "
          "their representativeness [@Canal26]. The observation is used here as an independent check, with its own error model (Sections 3.8 and 4.3)." % n(VAL["obs"], 1)))
add(("h2", "2.2 Dated Argentine economic benchmarks"))
add(("p", "Table 2 lists the market and regulatory benchmarks to which the economic priors are anchored, with their dates. Gas values distinguish the "
          "wellhead (PIST) price that a pipeline injector would receive, the delivered cost of gas to compressed natural gas (GNC) stations in the "
          "Buenos Aires metropolitan area and the retail GNC price; a bio-GNC plant supplying an anchor fleet would sell between the second and the "
          "third, net of compression and station costs. Electricity values distinguish the merchant (wholesale) value of energy from the long-term "
          "contract tariffs that the RenovAr programme awarded to landfill-gas projects. Peso values are converted at an assumed 1,400 ± 100 ARS per "
          "USD (late 2025) and should be re-dated before use. Capital goods carry import duties that Decree 513/2025 reduced to 12.6% for many items, "
          "against the 20% Mercosur common external tariff [@Marval2025]; the imported share, duty and logistics define the capital premium, Eq. (9). "
          "Country risk enters through the real discount rate, and corporate income tax, the debt share and credit eligibility are treated in the "
          "robustness analysis (Section 4.11)."))
TAB2 = [["Wellhead (PIST) gas price, AMBA distributors", "US$2.94–2.98 per MMBtu", "Dec 2025", "[@OFarrell2025]", "p_pipe tri(0.07, 0.10, 0.16) US$ per Nm³"],
        ["Gas delivered to AMBA GNC stations (pre-VAT)", "ARS 221.63 per m³ (≈ US$0.16)", "Nov 2025", "[@Surtidores2025]", "p_gnc tri(0.13, 0.19, 0.40) US$ per Nm³"],
        ["Retail GNC price, AMBA", "ARS 500–570 per m³ (≈ US$0.36–0.41)", "Jul 2025", "[@LaNacion2025]", "upper end of p_gnc"],
        ["Wholesale electricity: marginal and priority-market cost", "US$69 and 64 per MWh", "2024", "[@MEGSA2025]", "p_el tri(60, 75, 95) US$ per MWh (merchant)"],
        ["Monomic wholesale electricity price", "ARS 121,100 per MWh (≈ US$87)", "Aug 2025", "[@UDEA2025]", "c_el tri(70, 95, 130) (purchase incl. network)"],
        ["RenovAr landfill-gas contract awards", "US$128–130 per MWh", "2017", "[@EnergiasRen2017;@RenewableEnergyMag2017]", "p_el,k tri(110, 125, 135) (contract variant)"],
        ["Import duty on capital goods", "12.6% (Decree 513/2025); 20% CET", "Jul 2025", "[@Marval2025]", "duty tri(0, 0.126, 0.20)"],
        ["Country risk (EMBI spread)", "561 to >1,200 bp; 569 bp on 17 Dec", "2025", "[@USAL2025]", "r tri(0.08, 0.12, 0.18) real"],
        ["Corporate income tax, top bracket", "35%", "2021 law", "[@Ley27630]", "after-tax variant"],
        ["Landfill-gas carbon credits; voluntary-market average", "≈US$9.5 and 5.5 per tCO₂e", "2025", "[@MSCI2025]", "cp tri(2, 6, 12), eligibility uni(0.2, 0.8)"]]
add(("table", "Table 2. Dated Argentine benchmarks and the priors anchored to them (US$ conversions at 1,400 ARS per USD, an assumption).",
     ["Item", "Benchmark", "Date", "Source", "Prior used"], TAB2, [2.6, 2.2, 0.8, 1.6, 2.4]))

# ============================================================================================ 3 Methods
add(("h1", "3. Methods"))
add(("h2", "3.1 Methane balance in two periods"))
add(("p", "Gas quantities are in Nm³ CH₄ h⁻¹ unless stated. Generation around the observation date, $G_{22}$, is bottom-up, from waste acceptance "
          "$A$ (t d⁻¹), methane potential $L_0$ (Nm³ CH₄ t⁻¹) and an effective fraction $f_{ss}$ of steady-state generation that absorbs landfill age, "
          "decay rate and lag; the prior is deliberately wide ($L_0$ from 50 to 170, $f_{ss}$ from 0.30 to 0.95; Supplementary Table S2):"))
add(("eq", r"G_{22}=\frac{365\,A\,L_0\,f_{ss}}{8760},\qquad G=g_t\,G_{22}", 1))
add(("p", "where $g_t$ (0.95 to 1.15) carries generation forward to the 2025–26 decision period. Collected methane is the reported biogas flow times "
          "the methane fraction, separately for the historical period ($Q_{22}$, 12,000 to 14,000 Nm³ h⁻¹, between the 2013 peak and the 2025 value) "
          "and the decision period ($Q$, 13,000 to 16,500 Nm³ h⁻¹). The collection efficiency of each period is an inferred quantity, "
          "$\\eta = C/G$, and draws above 0.95 are rejected as inconsistent. Surface emission after oxidation in the cover soil, a fraction $ox$ "
          "[@Chanton2009], is"))
add(("eq", r"E=(G-C)(1-ox)", 2))
add(("p", "evaluated with $G_{22}$ and $C_{22}$ at the observation date and with $G$ and $C$ for the decision period. Existing engines consume "
          "$P_{el}\\,CF/(\\eta_{el}\\,LHV)$, with $LHV$ = 9.94 kWh Nm⁻³; the surplus beyond the engines, $S$, is flared. Methane is converted with "
          "0.717 kg Nm⁻³ and to CO₂-equivalent with the AR6 values for non-fossil methane, 27.0 (GWP100) and 79.7 (GWP20) [@Forster2021;@Balcombe2018]."))
add(("h2", "3.2 Satellite constraint and observation-error models"))
add(("p", "The satellite information enters as a likelihood on the modeled emission at the observation date, $E_{22}$ (t h⁻¹). Three "
          "observation-error models are compared: a uniform window over the reported range (18 to 38 t h⁻¹; I is the indicator function), a Gaussian centered on the peer-reviewed "
          "estimate (28 ± 6 t h⁻¹), and a lognormal with the same median and $\\sigma_{\\ln}$ = 0.35, the base case because emission-rate retrievals "
          "have multiplicative errors [@Schuit2023]:"))
add(("eq", r"L_{\rm win}=\mathrm{I}(18\le E_{22}\le 38),\quad L_{\rm G}=e^{-\frac{(E_{22}-28)^2}{2\cdot 6^2}},\quad L_{\rm LN}=e^{-\frac{(\ln E_{22}-\ln 28)^2}{2\cdot 0.35^2}}", 3))
add(("p", "Posterior samples are drawn by importance resampling of the prior draws with weights $w_i \\propto L(E_{22,i})$ [@Beaumont2002]; the "
          "effective sample size is"))
add(("eq", r"\mathrm{ESS}=\frac{(\sum_i w_i)^2}{\sum_i w_i^2}", 4))
add(("p", "which is %s (lognormal), %s (Gaussian) and %s (window) of %s draws. The window model is equivalent to approximate Bayesian rejection. "
          "Every collection efficiency reported below is an inference conditional on the generation prior and the error model; none is a measurement."
          % (n(R["ess"]["lognormal"]), n(R["ess"]["gauss"]), n(R["ess"]["window"]), n(R["n"]))))
add(("h2", "3.3 Interventions, selective covers and the cover break-even"))
add(("p", "Eight scenarios follow the structure of the project white paper (Table 1). Wellfield optimization (S1) increases the collection efficiency "
          "by an absolute increment $\\Delta\\eta_1$; the added gas is flared unless a later scenario uses it. A selective cover (S2, S3) acts on the "
          "fraction $f_{hot}$ of surface flux passing through the covered area. With $M_c$ the methane arriving at the cover, the barrier blocks "
          "$b = \\varepsilon M_c$; a share $s_c$ of the blocked gas is captured by the extraction system and the rest is redirected to uncovered "
          "surface with oxidation $\\rho\\,ox$, while oxidation under the cover decreases to $ox_{cov} = ox(1-\\delta\\varepsilon)$. The emission after "
          "the cover and the net methane avoided are"))
add(("eq", r"E_1=(E_s-M_c)(1-ox)+(M_c-b)(1-ox_{cov})+(1-s_c)\,b\,(1-\rho\,ox)", 5))
add(("eq", r"\Delta E=E_s(1-ox)-E_1-s_c\,b\,(1-d_f)", 6))
add(("p", "where $E_s$ is the methane reaching the surface after S1 and $d_f$ the destruction efficiency of the flare or engine. Because $\\Delta E$ "
          "is linear in $s_c$, the cover reduces net emissions if and only if"))
add(("eq", r"s_c>s_c^*=-\frac{A_0}{A_1},\quad A_0=M_c(1-ox)-(M_c-b)(1-ox_{cov})-b(1-\rho\,ox),\quad A_1=b(1-\rho\,ox)-b(1-d_f)", 7))
add(("p", "This is the quantitative form of the concern that sealing one area may only redirect leakage. Two structural alternatives are tested: "
          "redirected gas that is not oxidized ($\\rho$ = 0) and complete loss of oxidation under the cover ($\\delta$ = 1)."))
TAB1 = [["S0", "Documented recovery, power generation and flaring", "Reference"], ["S1", "Wellfield optimization and leak detection", "S0"],
        ["S2", "S1 + conventional engineered cover on hot-spot area", "S1"], ["S3", "S1 + selective experimental coating", "S1"],
        ["S4", "S2 + conventional photovoltaics on the covered area", "S2"], ["S5", "S2 + experimental PV paint on the covered area", "S4 at equal area"],
        ["S6", "S2 + gas buffer + biomethane upgrading (surplus + captured gas)", "Flaring"], ["S6b", "S1 + gas buffer + biomethane upgrading, no cover", "Flaring"],
        ["S7", "S6 + PV-assisted upgrader + adaptive control", "S6"], ["PW", "Additional gas engines on the existing surplus (power alternative)", "Flaring"]]
add(("table", "Table 1. Scenario definitions. S1–S7 are the integrated interventions; PW is reported separately as the alternative use of the surplus gas.",
     ["Scenario", "Incremental change", "Counterfactual"], TAB1, [0.8, 5.0, 1.6]))
add(("h2", "3.4 Uses of recovered gas and their climate accounts"))
add(("p", "Three biomethane routes are priced: bio-GNC to an anchor fleet with a demand cap, pipeline injection with a spur and metering station, "
          "and a hybrid; the best route is chosen per draw. Electricity for upgrading (0.20 to 0.40 kWh per Nm³ raw gas) is common to all routes, and "
          "compression is route-specific: 0.25 kWh per Nm³ of product for GNC dispensing and 0.10 kWh per Nm³ for pipeline injection [@Angelidaki2018]. "
          "On the GNC-only route, product in excess of the anchor demand is flared, and its slip is counted. Plant fugitive methane is removed from the "
          "product stream before sale and counted as an emission [@Bakkaloglu2022]. Relative to flaring the same gas, the climate account of upgrading "
          "is"))
add(("eq", r"\Delta\mathrm{CO_2e}=EF_{NG}\,E_{\rm exp}-\mathrm{GWP}\,\Delta m_{\rm CH_4}-EF_{\rm grid}\,W_{\rm el}", 8))
add(("p", "with $E_{\\rm exp}$ the energy of biomethane exported (displacing natural gas at 0.202 tCO₂ per MWh), $\\Delta m_{\\rm CH_4}$ the "
          "change in methane emitted (buffer and plant leakage, tail-gas slip and flaring of unsold product, minus the flare slip avoided) and "
          "$W_{\\rm el}$ the grid electricity used. The power alternative (PW) installs additional gas engines on the same surplus [@Bove2006]; its "
          "climate account is the grid electricity displaced. Gas already consumed by existing engines is never counted as feedstock. The first "
          "version of the model applied the GNC compression energy to every route, did not count unsold product or plant fugitive methane, and had "
          "no climate account for the power alternative; all four are corrected here."))
add(("h2", "3.5 Economics"))
add(("p", "Cash flows are in real US dollars over 20 years. The net present value is"))
add(("eq", r"\mathrm{NPV}=-\kappa\,\mathrm{CAPEX}+AF(r)\,(m_p R-O),\qquad AF(r)=\frac{1-(1+r)^{-20}}{r},\qquad \kappa=1+f_{\rm imp}\,(d+l)", 9))
add(("p", "where $\\kappa$ is the capital premium built from the imported share $f_{imp}$, the import duty $d$ and logistics and exchange costs $l$, "
          "$m_p$ a lognormal realized-price multiplier (mean 1, $\\sigma$ = 0.25) for tariff and exchange-rate risk, and $r$ the real discount rate "
          "(8 to 18%, mode 12%, consistent with the 2025 country-risk spread). Replacement of short-lived assets (coatings, paint) is discounted "
          "explicitly. For photovoltaics on the covered area, setting the levelised cost of the paint equal to that of conventional PV gives the "
          "break-even efficiency $\\eta^* = c_{pt}\\,\\kappa\\,[CRF(r,L_{pt})+o_{pt}]/(LCOE_{\\rm conv}\\,H_{poa}\\,PR)$ (Supplementary Section S2). "
          "Carbon-credit revenue is zero in the base case. The levelised abatement cost is $-\\mathrm{NPV}/(AF\\cdot\\Delta\\mathrm{CO_2e})$ and "
          "equals the credit price at which a scenario breaks even. Variants (Section 4.11) add corporate tax at 35% with straight-line depreciation "
          "over 10 years [@Ley27630], a weighted average cost of capital built from debt and equity costs, contracted rather than merchant electricity, "
          "and expected credit revenue with an eligibility probability."))
add(("h2", "3.6 Monte Carlo design, balances and automated tests"))
add(("p", "Inputs (Supplementary Table S2) are sampled by Latin hypercube [@McKay1979] with triangular, uniform or lognormal marginals and are tagged as "
          "operator-reported [R], literature or standard value [L], dated benchmark [B] or assumed [A]. Sensitivity is reported as Spearman rank "
          "correlation [@Saltelli2008]. For every scenario the model closes three balances: methane (generated = emitted + oxidized + destroyed + "
          "exported), carbon (the same flows in tonnes of carbon, with biogenic CO₂ from oxidation and combustion) and energy (offered = exported + "
          "flared + lost, with electricity imported tracked separately). The climate benefit of each scenario is computed both from the incremental "
          "formulas and from the balances, and the two must agree. Before results are produced, %d automated tests must pass (Supplementary Section S4): "
          "unit conversions; closure of the cover, upgrader and scenario balances; agreement of the balance-based and incremental climate benefits; "
          "limiting cases; a hand-calculated upgrading case; an independent cash-flow benchmark of the annuity NPV; the analytic first-order-decay "
          "limits; LCOE parity at $\\eta^*$; the closed-form identity of the collection efficiency (Section 3.8); the limiting cases of the engine "
          "counterfactuals and of the climate variants; and a standard error of P(NPV > 0) below 0.01. The tests verify internal consistency; they do "
          "not validate the model against site data, which Section 4.3 addresses separately." % NTEST))
add(("h2", "3.7 Robustness design"))
add(("p", "Beyond the three observation-error models, the analysis is repeated (120,000 draws each) with rank correlations induced by the "
          "Iman–Conover method [@Iman1982] among prices, among costs and between $L_0$ and $f_{ss}$; with uniform marginals; "
          "with every prior widened by 50%; with the two structural cover alternatives; with contracted electricity; with a WACC; over a sweep of "
          "discount rates; and with expected credit revenue. Temporal variability is tested by replacing constant gas supply with a first-order-decay "
          "trajectory [@IPCC2006],"))
add(("eq", r"\frac{G(t)}{G(0)}=\frac{1-e^{-k(a+t)}}{1-e^{-ka}}\ \ (t<t_c),\qquad \frac{G(t)}{G(0)}=\frac{1-e^{-k(a+t_c)}}{1-e^{-ka}}\,e^{-k(t-t_c)}\ \ (t\ge t_c)", 11))
add(("p", "with decay rate $k$ (0.05 to 0.15 yr⁻¹), years of deposition $a$ and years to closure $t_c$, and annual cash flows replacing the "
          "annuity for the uses of surplus gas."))
add(("h2", "3.8 Identifiability, representativeness and independent check of the satellite constraint"))
add(("p", "Because the satellite constrains the surface emission, the collection efficiency of the observation period follows from Eqs. (1) and (2) as"))
add(("eq", r"\eta_{22}=\frac{C_{22}}{C_{22}+E_{22}/[(1-ox)\,\rho_m]},\qquad \ln\frac{1-\eta_{22}}{\eta_{22}}=\ln E_{22}-\ln(1-ox)-\ln C_{22}-\ln\rho_m", 12))
add(("p", "with $\\rho_m$ = 0.717 × 10⁻³ t Nm⁻³. The efficiency depends on the emission, the oxidation fraction and the reported capture, and on no "
          "generation parameter; $A$, $L_0$ and $f_{ss}$ matter only through the emission they imply, which the likelihood tests. We quantify "
          "this identifiability in four ways: the share of the variance of the log-odds carried by each term of Eq. (12); the prior-to-posterior "
          "contraction of each input; the posterior under five alternative generation histories (an inventory-anchored prior, a high and a low "
          "generation prior, a first-order-decay history in which $f_{ss}$ follows from $k$, the age of the site and the growth of deposition, and a "
          "widened prior on the historical capture, 8,000 to 18,000 Nm³ h⁻¹), compared by their mean likelihood (evidence) relative to the base prior; "
          "and the effect of the observation model."))
add(("p", "Representativeness is tested by scaling the satellite median by 0.25 to 2 (a snapshot that caught an episodic high, a survey biased to "
          "detections, or a site-wide emission above or below the retrieved plume) and by widening $\\sigma_{\\ln}$ to 0.5, 0.7 and 1.0 for wind, "
          "temporal-sampling and retrieval uncertainty. As an independent check, the 2025 observation of %s t h⁻¹ [@STOP2026] is treated as a lognormal "
          "likelihood on the 2025–26 surface emission with $\\sigma_{\\ln}$ = %s (an assumption: the source reports no uncertainty). The model "
          "calibrated on 2019–22 data alone predicts this emission, and the discrepancy is reported as the ratio of observed to predicted median and "
          "as the probability that the predictive distribution lies at or below the observation. The observations are then combined, with their stated "
          "errors and with both errors inflated to 0.7, and the generation growth $g_t$ that would reconcile them is computed." % (n(VAL["obs"], 1), n(VAL["obs_sln"], 1))))
add(("h2", "3.9 Engine counterfactuals and climate-accounting variants"))
add(("p", "The profitability of additional engines is evaluated in nine operating states built on the same posterior draws: installed capacity (23 MW), the "
          "prior range of engine capacity, and the planned 33 MW, each with constant gas supply; the 33 MW case with first-order decline of the gas "
          "supply; reduced availability of the new engines (25% downtime); curtailment of 20% of the output; a low merchant tariff (US$45 per MWh); a "
          "contracted tariff; and a combined stress case. For each state we report the probability that surplus gas exists, the probability of a positive "
          "NPV given that it exists, and the probability across all draws (a draw without surplus gas counts as no profitable deployment)."))
add(("p", "The climate account of the added engines and of biomethane is repeated with four changes, each a sensitivity and not a prediction (tag A): "
          "engine methane slip of 1 to 6% of the methane burned (the base model uses the flare and engine destruction efficiency, 0.5 to 5% slip); a "
          "marginal rather than average grid emission factor (0.35 to 0.65 tCO₂ per MWh, mode 0.45); a poorer counterfactual in which the surplus is "
          "flared with a destruction efficiency of 0.80 to 0.98 (flare uptime and combustion efficiency); and partial displacement of fossil natural "
          "gas by biomethane (fraction 0.3 to 1.0). The slip at which the climate benefit of the engines is exhausted follows from the balance and is "
          "reported."))

# ============================================================================================ 4 Results
add(("h1", "4. Results"))
add(("h2", "4.1 Calibration and the inferred collection efficiency"))
add(("p", "Reported flows imply that the existing engines consume %s Nm³ CH₄ h⁻¹ of a collected %s (median, 90%% interval), leaving a surplus of "
          "%s Nm³ CH₄ h⁻¹. The surplus is positive in %s of draws and exceeds 500 Nm³ h⁻¹ in %s, but it depends strongly on engine capacity: the "
          "median is %s Nm³ h⁻¹ for installed power of 25 MW or less and %s Nm³ h⁻¹ once the expansion to approximately 33 MW is complete (Fig. 1d)."
          % (q3(g["eng_Nm3h"]), q3(g["C_Nm3h"]), q3(g["S_exist_Nm3h"]), pct(g["P_surplus_gt0"]), pct(g["P_surplus_gt500Nm3h_CH4"]),
             n(h["surplus_P_el_le25"][1]), n(h["surplus_P_el_ge31"][1]))))
add(("p", "The prior gives generation around 2022 of %s Nm³ CH₄ h⁻¹ and a modeled 2022 emission of %s t h⁻¹. The satellite constraint shifts "
          "generation to %s Nm³ h⁻¹ and the emission at the observation date to %s t h⁻¹, and the three error models give nearly the same posterior "
          "(Fig. 1a,b): the inferred 2022 collection efficiency is %s (lognormal), %s (Gaussian) and %s (window). Carried forward with the 2025–26 "
          "capture, the efficiency is %s and the surface emission %s t h⁻¹ (Fig. 1c). The collection efficiency of the first version, 0.18, compared a "
          "2025–26 capture with 2019–22 satellite data and is superseded; it was never a measurement. One percentage point of collection efficiency "
          "corresponds to %s kt CH₄ yr⁻¹ (approximately %s kt CO₂e at GWP100), and the total baseline emission including slip from collected gas is %s kt "
          "CH₄ yr⁻¹, approximately %s Mt CO₂e yr⁻¹."
          % (q3(PR["gas"]["G22_Nm3h"]), q3(PR["gas"]["E22_th"]), q3(g["G22_Nm3h"]), q3(g["E22_th"]), q3(g["eta22"], 2),
             q3(R["posterior_gauss"]["gas"]["eta22"], 2), q3(R["posterior_window"]["gas"]["eta22"], 2), q3(g["eta_c"], 2), q3(g["E_atm_th"]),
             q3(h["per_pp_eta_tCH4_yr_q"], 1, 1e-3), n(h["per_pp_eta_tCO2e100_q"][1] / 1e3), q3(P["E_tot0_q"], 0, 1e-3), n(P["E_tot0_q"][1] * M.GWP100 / 1e6, 1))))
add(("fig", "Fig1_gas_balance.png", "Fig. 1. Calibration. (a) Generation around 2022: prior and the posteriors of the three observation-error models. "
            "(b) Modeled surface emission at the observation date with the satellite range shaded. (c) Inferred collection efficiency in 2022 and "
            "2025–26 (lognormal posterior; a model output, not a measurement). (d) Surplus methane beyond the existing engines by installed capacity.", 6.4))

# ---- 4.2 identifiability
cs, cp = ID["logodds_shares_post"], ID["contraction"]
low_g, high_g = gv("low generation"), gv("high generation")
wide_c = gv("widened historical")
sig = [SS[k] for k in SS if k.startswith("sigma")]
add(("h2", "4.2 Identifiability and representativeness of the satellite-constrained collection efficiency"))
add(("p", "The collection efficiency of Eq. (12) is determined by the emission, the oxidation fraction and the reported capture; the identity holds to "
          "%s in the sampled draws. In the lognormal posterior the log-odds of capture has a standard deviation of %s, of which %s is carried by the "
          "emission, %s by the reported capture and %s by oxidation (Supplementary Table S1). The generation parameters are weakly identified "
          "individually: the satellite constraint contracts the interquartile range of $L_0$ by %s and of $f_{ss}$ by %s, and leaves waste acceptance "
          "($A$), the methane fraction and the historical capture essentially unchanged (contractions of %s, %s and %s), whereas their product, the generation, contracts by %s. "
          "Generation and efficiency are strongly dependent in the posterior (correlation of ln $G_{22}$ with $\\eta_{22}$: %s), because efficiency "
          "is the capture divided by generation (Fig. 2a). The bottom-up prior already implies an efficiency of %s before any satellite information is "
          "used (prior median and 90%% interval), so the satellite estimate narrows an inference that the generation prior and the reported capture "
          "already make, rather than creating it."
          % ("%.0e" % max(ID["closed_form_max_abs_diff"], 1e-16), n(cs["sd_logodds"], 2), pct(cs["lnE"]), pct(cs["lnC"]), pct(cs["ln1mox"], 1),
             pct0(cp["L0"]["contraction"]), pct0(cp["fss"]["contraction"]), pct0(cp["Awaste"]["contraction"]), pct0(cp["xCH4"]["contraction"]),
             pct0(cp["Qcoll22"]["contraction"]), pct0(cp["G22"]["contraction"]), n(ID["post_corr"]["lnG22,eta22"], 2), qc(cp["eta22"]["prior_q"]))))
add(("p", "The conclusion does not depend on the generation history (Table 3). Under the five alternatives the median 2022 efficiency ranges from %s "
          "(high generation) to %s (low generation) and the 2025–26 efficiency from %s to %s. The alternatives are not equally compatible with the "
          "satellite estimate: relative to the base prior the evidence is %s for the inventory-anchored prior, %s for the first-order-decay history, "
          "%s for high generation and %s for low generation, which the 18 to 38 t h⁻¹ range disfavors by a factor of approximately %s. Widening the "
          "historical-capture prior widens the 2022 interval to %s but moves the median by less than 0.01. Across the generation histories the "
          "2025–26 efficiency does not exceed %s, and the conclusions on covers, engines and biomethane do not change (Table 3, last columns)."
          % (n(high_g["eta22"][1], 2), n(low_g["eta22"][1], 2), n(min(gen_etac), 2), n(max(gen_etac), 2),
             n(gv("inventory")["marginal_likelihood"] / GV["base prior (wide)"]["marginal_likelihood"], 2),
             n(gv("first-order")["marginal_likelihood"] / GV["base prior (wide)"]["marginal_likelihood"], 2),
             n(high_g["marginal_likelihood"] / GV["base prior (wide)"]["marginal_likelihood"], 2),
             n(low_g["marginal_likelihood"] / GV["base prior (wide)"]["marginal_likelihood"], 2),
             n(GV["base prior (wide)"]["marginal_likelihood"] / low_g["marginal_likelihood"], 0), qc(wide_c["eta22"]), n(max(gen_etac), 2))))
need = ID["emission_for_efficiency"]
add(("p", "Representativeness is the larger uncertainty. The 2019–22 estimates are retrievals at the time of observation, not annual facility means, and "
          "wind, temporal sampling, detection thresholds and intermittent high-emission events can bias them in either direction, although airborne "
          "surveys find that large landfill emissions often persist across repeated visits [@Cusworth2024]. Scaling the satellite median by 0.25 to 2 "
          "moves the 2025–26 efficiency from %s to %s (medians), and widening $\\sigma_{\\ln}$ from 0.35 to 1.0 leaves the median at %s but widens the interval "
          "to %s. For the efficiency to reach 0.5, the surface emission would have to be approximately %s t h⁻¹, a factor of %s below the satellite median, and "
          "for 0.3 approximately %s t h⁻¹. None of these changes the sign of any scenario's median NPV, and the probability that a cover reduces net emissions "
          "remains between %s and %s (Table 3). The inferred efficiency of approximately %s is therefore conditional on the model structure and on the "
          "satellite estimate; it is not evidence that the operator's reported capture is wrong."
          % (n(SS[sat_keys[-1]]["eta_c"][1], 2), n(SS[sat_keys[0]]["eta_c"][1], 2), n(SS["sigma_ln 1.00"]["eta_c"][1], 2),
             qc(SS["sigma_ln 1.00"]["eta_c"]), n(need["0.50"], 1), n(M.SAT_MED / need["0.50"], 0), n(need["0.30"], 0),
             pct(min(v["P_cover"] for v in list(SS.values()) + list(GV.values()) + list(JT.values()))),
             pct(max(v["P_cover"] for v in list(SS.values()) + list(GV.values()) + list(JT.values()))), n(g["eta_c"][1], 2))))
add(("p", "Measured collection efficiencies are not directly comparable between sites. Field studies find that the default efficiencies of inventories tend to overstate capture "
          "[@Spokas2006;@Giordano2024], and reviews caution against transferring efficiencies between sites with different covers, ages and wellfield operation [@Saul2026]. An efficiency of %s at a very "
          "large, young-cover site with a rapidly growing capture system is therefore not implausible in kind, but it lies far outside the efficiencies commonly assumed, and no published value "
          "is used as a prior for Norte III." % n(g["eta_c"][1], 2)))
add(("fig", "Fig2_identifiability.png", "Fig. 2. Identifiability and independent check. (a) Posterior draws of generation and 2022 efficiency lie on the curve "
            "η = C/G; the satellite emission fixes the position along it. (b) Posterior 2022 efficiency under alternative generation histories (median, P5–P95). "
            "(c) 2025–26 efficiency against the scaling of the 2022 satellite emission, and with both observations. (d) Predicted 2025–26 surface emission "
            "against the independent 2025 observation (red line) and the 2022 satellite range.", 6.6))
rows3 = []


def r3(lab, v, with_ev=False):
    ev = n(v["marginal_likelihood"] / GV["base prior (wide)"]["marginal_likelihood"], 2) if with_ev and "marginal_likelihood" in v else "–"
    return [lab, qc(v["eta22"]), qc(v["eta_c"]), ev, n(v["P_cover"], 2), n(v["P_pw_pos"], 2), n(v["S6b_npv"], 1), "no" if not v["any_scen_median_pos"] else "yes"]


for k, lab in (("base prior (wide)", "Base generation prior"), ("inventory", "Inventory-anchored generation"), ("high generation", "High generation"),
               ("low generation", "Low generation"), ("first-order", "First-order-decay history"), ("widened historical", "Wide historical-capture prior")):
    rows3.append(r3(lab, gv(k), True))
for k in sat_keys:
    rows3.append(r3("Satellite emission × %s" % n(SS[k]["scale"], 2), SS[k]))
for k in SS:
    if k.startswith("sigma"):
        rows3.append(r3("Observation error σ = %s" % n(SS[k]["sln"], 2), SS[k]))
for k, lab in (("2025 observation alone (sigma 0.5)", "2025 observation alone"), ("both observations (0.35 and 0.5)", "2022 and 2025 observations"),
               ("both, inflated errors (0.7 and 0.7)", "Both, errors inflated to 0.7")):
    rows3.append(r3(lab, JT[k], False))
add(("table", "Table 3. Identifiability and representativeness: collection efficiency (median, P5–P95) and decision-relevant quantities under alternative "
              "generation histories, scaling and error of the satellite emission, and the independent 2025 observation. Evidence: mean likelihood of the 2022 "
              "satellite estimate under each generation prior, relative to the base prior (not defined for the other rows). "
              "P(cover): probability that the conventional cover reduces net emissions; P(PW > 0): probability that additional engines have a positive NPV given "
              "surplus gas; S6b NPV in MUSD; last column: does any integrated scenario have a positive median NPV?",
     ["Variant", "η 2022", "η 2025–26", "Evidence", "P(cover)", "P(PW>0)", "S6b NPV", "Any > 0"], rows3, [2.4, 1.2, 1.2, 0.7, 0.7, 0.7, 0.7, 0.6]))

# ---- 4.3 validation
add(("h2", "4.3 External validation and model discrepancy"))
add(("p", "The automated tests establish internal consistency, not agreement with site behavior. One observation exists that is independent of the "
          "calibration and of the reported flows: the Carbon Mapper average of %s t CH₄ h⁻¹ for 2025 [@STOP2026]. The model calibrated on 2019–22 "
          "data alone predicts a 2025–26 surface emission of %s t h⁻¹ (median and 90%% interval; Fig. 2d). The observed value is %s of the predicted "
          "median; the predictive distribution lies at or below it in %s of draws (%s when the lognormal error of the observation is included), a "
          "log-discrepancy of %s standard deviations. The model therefore overpredicts the 2025 emission, and the discrepancy is not inside the "
          "stated interval."
          % (n(VAL["obs"], 1), q3(VAL["pred_q"], 1), pct(VAL["ratio_obs_to_pred_median"]), pct(VAL["P_pred_below_obs"], 1),
             pct(VAL["P_pred_below_obs_with_obs_error"], 1), n(VAL["z_log"], 1))))
add(("p", "Three explanations are possible and cannot be separated with the data at hand. First, the emission fell: reaching 2025's value from the "
          "2022 estimate requires generation to fall to %s of its 2022 value within approximately three years (the prior of $g_t$ is 0.95 to 1.15) while about "
          "18,000 t d⁻¹ continue to arrive, which is not credible for generation alone, although an emission reduction from interventions that are not in the model's baseline, such as "
          "new covers or leak repair since 2022, cannot be excluded. Second, the two data sets differ in instrument, "
          "retrieval algorithm, overpass time and averaging convention, and neither is a facility-wide annual mean; facility-scale agreement across "
          "methods is poor in general [@Dogniaux2025]. Third, the model's structure or priors may be wrong, for example the oxidation fraction "
          "or the assumption that the reported flows are complete. When both observations are used with their stated errors, the posterior surface "
          "emission is %s t h⁻¹ in 2022 and %s t h⁻¹ in 2025–26, and the efficiency in 2025–26 is %s; the 2025 observation alone is %s, and "
          "inflating both errors to 0.7 yields %s. The base-case efficiency of %s is therefore the lower end of a range of approximately %s to %s that "
          "the two satellite data sets jointly support, and in every case most of the generated methane is not collected (P95 %s). "
          "Decisions are unchanged across the range: the probability that a cover reduces net emissions is %s, the probability that additional engines "
          "are profitable given surplus gas is %s, and no integrated scenario has a positive median NPV (Table 3)."
          % (pct(VAL["g_t_required"]), qc(J2["E22"], 1), qc(J2["E26"], 1), qc(J2["eta_c"]), qc(J1["eta_c"]), qc(J3["eta_c"]), n(g["eta_c"][1], 2),
             n(g["eta_c"][1], 2), n(J1["eta_c"][1], 2), n(J1["eta_c"][2], 2), prange([v["P_cover"] for v in JT.values()]),
             prange([v["P_pw_pos"] for v in JT.values()]))))
add(("p", "We conclude that the model is externally unvalidated at facility scale. Only one independent observation is available to us, it is a "
          "secondary summary without an uncertainty, and a second independent facility-scale data set does not exist in the sources we could access. "
          "Section 5.2 gives a field-measurement protocol that would convert this check into a validation."))

add(("h2", "4.4 Wellfield optimization and selective covers"))
add(("p", "S1 avoids a median %s kt CO₂e yr⁻¹ at a net present cost of %s MUSD, a levelised abatement cost of US$%s per tCO₂e. A conventional cover "
          "reduces net methane emissions in %s of draws and an experimental coating in %s (Fig. 3a); the net effect of the cover alone is %s kt CH₄ yr⁻¹ "
          "for the conventional cover. Net avoided methane is %s of the gross added capture (median), so gross capture overstates the benefit by about "
          "a third. The break-even captured share $s_c^*$ has a median of %s; the cover increases emissions in exactly the %s of draws in which $s_c$ "
          "falls below its own $s_c^*$, and the analytic boundary tracks the simulated sign change (Fig. 3b). The cover's effect is controlled by $s_c$ "
          "(Spearman ρ = %s), then by $f_{hot}$, $ox$ and $\\varepsilon$. Under the structural alternatives the probability of net benefit decreases to %s "
          "(redirected gas not oxidized) and %s (all oxidation lost under the cover)."
          % (q3(SC["S1"]["co2_100_q"], 0, 1e-3), n(-SC["S1"]["npv_q"][1], 1), n(SC["S1"]["abate_q"][1], 1), pct(h["H1_P_cover_reduces_conv"]),
             pct(h["H1_P_cover_reduces_coat"]), q3(h["H1_cover_only_ch4_conv"], 1, 1e-3), pct(h["H1_gross_vs_net_ratio_median"]),
             q3(h["H1_sc_star_q"], 2), pct(h["H1_P_sc_below_star"], 1), n(dict(P["sens_S2_ch4"])["s_c"], 2),
             pct(var("cover: redirected gas unoxidised")["P_cover"]), pct(var("cover: all oxidation lost under cover")["P_cover"]))))
add(("fig", "Fig3_cover.png", "Fig. 3. Selective cover. (a) Net methane avoided by the cover alone (boxes P25–P75, whiskers P5–P95). (b) Simulated net "
            "benefit or increase against barrier effectiveness and captured share, with the analytic break-even $s_c^*$ for three values of the "
            "oxidation-loss parameter.", 6.2))
add(("h2", "4.5 Scenario economics without credits"))
add(("p", "None of the eight integrated intervention scenarios has a positive median incremental NPV under the assumed no-credit conditions "
          "(Fig. 4a; Table 4). The probability of a positive NPV is at most %s (S6b). Measures do not add: S6, which upgrades the gas captured by the "
          "cover, has a lower median NPV than S6b, which upgrades without a cover (%s against %s MUSD), because the cover costs more than the extra gas "
          "is worth, and S7 avoids the most methane (%s kt CO₂e yr⁻¹) at the largest cost. Corporate tax with depreciation shields reduces the losses "
          "but does not change any sign (Table 4, after-tax column)."
          % (n(max(SC[s]["P_npv_pos"] for s in M.SCEN), 3), n(SC["S6"]["npv_q"][1], 1), n(SC["S6b"]["npv_q"][1], 1), n(SC["S7"]["co2_100_q"][1] / 1e3))))
rows4 = []
for s in M.SCEN + ["PW"]:
    r = SC[s]
    rows4.append([s, q3(r["npv_q"], 1), n(r["P_npv_pos"], 3), n(r["npv_after_tax_q"][1], 1), q3(r["co2_100_q"], 0, 1e-3),
                  n(r["abate_q"][1], 1) if s != "PW" else "(profit)", n(r["P_npv_pos_cp25"], 2)])
add(("table", "Table 4. Scenario results, lognormal posterior (median, P5 to P95). NPV incremental to S0 in MUSD with no credit revenue; after-tax "
              "median with 35% tax and 10-year depreciation; avoided emissions at GWP100; abatement cost in US$ per tCO₂e; last column P(NPV > 0) with a "
              "US$25 credit. PW: additional engines on the existing surplus (draws with surplus gas).",
     ["Scenario", "NPV", "P(NPV>0)", "After tax", "Avoided (kt CO₂e/yr)", "Abatement", "P(>0), US$25"], rows4, [0.8, 2.0, 0.9, 0.9, 1.8, 1.0, 1.0]))
add(("fig", "Fig4_npv_scenarios.png", "Fig. 4. (a) Incremental NPV of the eight integrated interventions, lognormal posterior, no credit revenue (boxes "
            "P25–P75, whiskers P5–P95). (b) NPV of additional engines on the existing surplus at merchant and contracted tariffs.", 6.4))
add(("h2", "4.6 Additional engines and biomethane: counterfactuals for the surplus gas"))
add(("p", "The power alternative is reported separately because it is not an emission-reduction intervention but a competing use of gas that is "
          "already collected. Additional engines on the existing surplus have a positive NPV in %s of the draws with surplus gas at merchant tariffs "
          "(median %s MUSD) and in %s with a RenovAr-type contract (median %s MUSD; Fig. 4b). That probability is conditional on surplus gas existing "
          "and says nothing about whether it will exist (Table 5). At the installed 23 MW the surplus exists in %s of draws and engines are profitable "
          "in %s of all draws; with the prior range of capacity (23 to 33 MW) the figures are %s and %s; after the planned expansion to 33 MW surplus "
          "gas exists in only %s of draws (median %s Nm³ CH₄ h⁻¹ where it exists) and a profitable deployment in %s. Declining gas supply lowers the "
          "probability given surplus to %s; 25%% downtime of the new engines to %s; a US$45 per MWh tariff to %s; a contracted tariff increases it to %s. "
          "Combining a 33 MW fleet, declining supply, downtime, curtailment and the low tariff leaves a profitable deployment in %s of draws "
          "(%s of those with surplus). The finding that engines are profitable on genuinely uncommitted gas is robust; whether genuinely uncommitted gas "
          "will remain after the expansion is not."
          % (pct(h["H3_P_power_npv_pos"], 1), q3(h["H3_npv_pw_q"], 1), pct(h["H3_P_contract_power_npv_pos"], 1), q3(h["H3_npv_pw_contract_q"], 1),
             pct(pwrow("installed")["P_surplus"]), pct(pwrow("installed")["P_pos_all"]), pct(pwrow("prior")["P_surplus"]), pct(pwrow("prior")["P_pos_all"]),
             pct(pwrow("planned")["P_surplus"]), n(pwrow("planned")["median_surplus"]), pct(pwrow("planned")["P_pos_all"]),
             pct(pwrow("33 MW, gas")["P_pos_given_surplus"]), pct(pwrow("base, new engines")["P_pos_given_surplus"]), pct(pwrow("base, low")["P_pos_given_surplus"]),
             pct(pwrow("base, contracted")["P_pos_given_surplus"]), pct(pwrow("stress")["P_pos_all"]), pct(pwrow("stress")["P_pos_given_surplus"]))))
rows5 = [[r["case"].replace("33 MW", "33 MW"), n(r["P_surplus"], 2), n(r["P_pos_given_surplus"], 2), n(r["P_pos_all"], 2), n(r["median_npv_given_surplus"], 1)]
         for r in PWC["rows"]]
add(("table", "Table 5. Additional engines on the surplus gas under nine operating states (%s posterior draws each). P(surplus): probability that surplus "
              "gas exists; P(NPV>0 | surplus): probability of a positive NPV given that it exists; P(NPV>0, all): probability across all draws, counting a "
              "draw without surplus gas as no profitable deployment; median NPV in MUSD given surplus." % n(PWC["n"]),
     ["Operating state", "P(surplus)", "P(NPV>0 | surplus)", "P(NPV>0, all)", "Median NPV"], rows5, [3.8, 0.8, 1.1, 1.0, 0.9]))
add(("p", "For the surplus beyond the existing engines, biomethane has a positive NPV in %s of draws (median %s MUSD) and beats additional engines "
          "in %s. Where it is built, bio-GNC to an anchor customer is the preferred route in %s of draws, because the pipeline price anchored to the "
          "PIST benchmark is low relative to the cost of a spur. The break-even realized bio-GNC plant-gate price is US$%s per Nm³ (approximately US$%s per "
          "MMBtu) against a prior of 0.13 to 0.40; pipeline injection would need US$%s per Nm³ (US$%s per MMBtu), approximately six times the PIST price. "
          "To match additional engines, bio-GNC would need US$%s per Nm³. Sizing does not rescue upgrading: with only the existing surplus as feedstock, "
          "the probability of a positive NPV peaks at %s at 2,000 Nm³ h⁻¹ of raw gas (Fig. 5b). A gas buffer lowers NPV in %s of draws (median %s MUSD)."
          % (pct(h["H3_P_up_npv_pos"], 1), q3(h["H3_npv_up_q"], 1), pct(h["H3_P_up_beats_power"], 2), pct(h["H3_route_share"][0], 1),
             q3(h["pstar_gnc_q"], 2), n(h["pstar_gnc_mmbtu_q"][1]), n(h["pstar_pipe_q"][1], 2), n(h["pstar_pipe_mmbtu_q"][1]), n(h["pstar_gnc_pw_q"][1], 2),
             n(max(s_["P"] for s_ in R["sweep"]), 2), pct(1 - h["H4_P_buffer_pos"], 2), n(h["H4_buf_q"][1], 2))))
add(("fig", "Fig5_route_and_sizing.png", "Fig. 5. (a) Bio-GNC plant-gate price required for NPV = 0 and for parity with additional engines, against "
            "the prior (values above US$1.6 per Nm³ pooled). (b) Probability of positive NPV against design capacity, existing surplus only.", 6.2))

# ---- 4.7 climate accounting
cw, cb = CLV["PW"], CLV["biomethane"]
kpw = list(cw.keys()); kbm = list(cb.keys())
add(("h2", "4.7 Climate accounting of the uses of recovered gas"))
add(("p", "A project can have a positive NPV and a small climate benefit, and the base account of Table 4 makes two simplifying choices that Table 6 tests. "
          "For additional engines the base account credits only the displaced grid electricity at the average emission factor and treats the engines "
          "like the flare they replace; the median benefit is %s kt CO₂e yr⁻¹, %s of that of the cover (S2). The benefit is exhausted only if the engines "
          "slip more than %s of the methane they burn (median break-even slip, P5 to P95: %s), well above the 1 to 6%% range tested, and a marginal "
          "grid factor increases it to %s kt. If the surplus is not reliably flared (destruction efficiency 0.80 to 0.98), the benefit of burning it rises "
          "to %s kt; with slip, marginal factor and poor flaring together it is %s kt. For biomethane the benefit depends mainly on whether it displaces "
          "fossil gas: with displacement between 0.3 and 1.0 the median decreases from %s to %s kt CO₂e yr⁻¹ and the benefit is positive in %s of draws "
          "instead of %s. Financial and climate rankings differ: additional engines have the highest NPV of the uses of surplus gas and a benefit of a "
          "few percent of that of the capture measures, whereas S2 has the largest benefit and a negative NPV."
          % (n(cw[kpw[0]]["q"][1], 1), pct(CLV["PW_share_of_S2_median"], 1), pct(CLV["engine_slip_breakeven_q"][1], 1), "%s to %s" % (pct(CLV["engine_slip_breakeven_q"][0], 1),
             pct(CLV["engine_slip_breakeven_q"][2], 1)), n(cw[kpw[2]]["q"][1], 1), n(cw[kpw[3]]["q"][1], 1), n(cw[kpw[4]]["q"][1], 1),
             n(cb[kbm[0]]["q"][1], 1), n(cb[kbm[1]]["q"][1], 1), pct(cb[kbm[1]]["P_pos"]), pct(cb[kbm[0]]["P_pos"]))))
rows6 = []
for k in kpw:
    rows6.append(["Added engines: " + k, qc(cw[k]["q"], 1), n(cw[k]["P_pos"], 2)])
for k in kbm:
    rows6.append(["Biomethane (S6b gas): " + k, qc(cb[k]["q"], 1), n(cb[k]["P_pos"], 2)])
add(("table", "Table 6. Climate benefit (GWP100) of additional engines and of biomethane on the existing surplus under alternative accounting choices, "
              "in kt CO₂e per year relative to flaring the same gas (median and P5–P95, draws with surplus gas); sensitivities of tag A, not predictions.",
     ["Account", "Benefit (kt CO₂e/yr)", "P(benefit > 0)"], rows6, [4.6, 1.8, 1.1]))
add(("p", "Credits add a further layer that this model does not resolve. Only the capture that is additional to what the operator is already "
          "required or committed to do could earn credits, and the engines' displaced grid electricity could be claimed under an electricity-certificate "
          "scheme as well as in a methane-credit project; the eligibility probability of 0.2 to 0.8 used in Section 4.11 is a placeholder for these "
          "tests, not an estimate of them."))
add(("h2", "4.8 Photovoltaics and the coating"))
add(("p", "The comparison of a conventional photovoltaic array with the experimental coating on the covered area is given in Supplementary Section S2 "
          "(Fig. S2), because the coating's performance priors are unvalidated. Conventional PV has a positive NPV in %s of draws, with a median LCOE of "
          "US$%s per MWh, above the merchant value of electricity because of the landfill foundation premium, the capital premium and the discount "
          "rate. The coating is cheaper in %s of draws under deliberately wide priors, a property of those priors; the transferable result is the break-even "
          "efficiency $\\eta^*$, with a median of %s, exceeding 10%% in %s of draws. Until that efficiency is demonstrated, the area is better used "
          "for the capture that Sections 4.4 and 4.5 evaluate."
          % (pct(h["H2_P_conv_npv_pos"], 1), q3(h["H2_lcoe_conv_q"]), pct(h["H2_P_paint_lcoe_lower"]), pct(h["H2_eta_star_q"][1], 1), pct(h["H2_P_eta_star_gt_10pct"]))))
add(("h2", "4.9 Abatement cost"))
add(("p", "Median levelised abatement costs are low in absolute terms: US$%s (S2), %s (S1), %s (S7) and %s (S6b) per tCO₂e at GWP100 (Fig. 6). "
          "At GWP20 the avoided CO₂e is %s times larger and the cost correspondingly lower; the median avoided in S2 becomes %s kt CO₂e yr⁻¹."
          % (n(SC["S2"]["abate_q"][1], 1), n(SC["S1"]["abate_q"][1], 1), n(SC["S7"]["abate_q"][1], 1), n(SC["S6b"]["abate_q"][1], 1),
             n(M.GWP20 / M.GWP100, 2), n(SC["S2"]["co2_20_q"][1] / 1e3))))
add(("fig", "Fig6_abatement_cost.png", "Fig. 6. Cumulative distribution of levelised abatement cost (GWP100, no credit revenue); dotted lines mark "
            "credit prices of US$10, 25 and 50 per tCO₂e.", 5.6))
add(("h2", "4.10 Sensitivity"))
sS6b, sPW = dict(P["sens_S6b_npv"]), dict(P["sens_PW_npv"])
add(("p", "The NPV of upgrading without a cover (S6b) is controlled by price and capital: the realized-price multiplier (ρ = %s), the bio-GNC price "
          "(%s) and the upgrader capital cost (%s); gas-side inputs rank lower (Fig. 7a). The value of additional engines depends on the same "
          "price multiplier (%s), then on the methane fraction, the discount rate and the installed engine capacity (Fig. 7b). Tariff and exchange-rate "
          "risk, not gas chemistry, is the dominant uncertainty for monetizing recovered gas."
          % (n(sS6b["m_p"], 2), n(sS6b["p_gnc"], 2), n(sS6b["capex_up"], 2), n(sPW["m_p"], 2))))
add(("fig", "Fig7_sensitivity.png", "Fig. 7. Spearman rank correlations, lognormal posterior: (a) NPV of S6b; (b) NPV of the power alternative; (c) net "
            "methane avoided by the conventional cover. Top ten inputs.", 6.6))
add(("h2", "4.11 Credits, tax, financing and the discount rate"))
ce = RB["credit_expected"]
ds = {round(x["r"], 2): x for x in RB["discount_sweep"]}
add(("p", "Because the abatement costs are low, a credit near US$5 to 10 per tCO₂e would make the capture measures viable if the added capture "
          "were eligible: at US$25 the probability of a positive NPV is %s for S1 and %s for S2 (Fig. 8a). At the 2025 market range, with an "
          "eligibility probability between 0.2 and 0.8, the expected credit revenue increases P(NPV > 0) only to %s (S1) and %s (S2). The discount rate "
          "does not change any conclusion between 6 and 20%% real (Fig. 8b): S1 and S2 remain negative at every rate, S6b reaches at most %s, and the "
          "power alternative remains above %s. A WACC built from equity and debt costs gives a median S6b NPV of %s MUSD against %s in the base case. "
          "CEAMSE reports that it began certifying carbon credits linked to biogas management in 2025 [@Canal26]; whether the added capture modeled "
          "here would be additional, verifiable and saleable is outside this study."
          % (n(SC["S1"]["P_npv_pos_cp25"], 2), n(SC["S2"]["P_npv_pos_cp25"], 2), n(ce["S1"]["P_npv_pos"], 2), n(ce["S2"]["P_npv_pos"], 2),
             n(max(x["S6b"] for x in RB["discount_sweep"]), 3), n(min(x["PW"] for x in RB["discount_sweep"]), 2),
             n(var("WACC from equity, debt and tax")["S6b_npv"], 1), n(var("likelihood: lognormal")["S6b_npv"], 1))))
add(("fig", "Fig8_credit_discount.png", "Fig. 8. (a) Probability of positive NPV against credit price for S1, S2 and S6b, prior (dashed) and lognormal "
            "posterior (solid), with the 2025 market range shaded. (b) Probability of positive NPV against the real discount rate.", 6.4))
add(("h2", "4.12 Robustness"))
tm = RB["temporal"]
add(("p", "Table 7 and Fig. 9 repeat the headline quantities under every variant. The decision-relevant conclusions do not change: no integrated "
          "scenario has a positive median NPV in any variant, additional engines on the surplus remain profitable in %s to %s of draws with surplus, "
          "upgrading beats them in under 1%% of draws, and the cover's net benefit remains between %s and %s. The climate case moves with the generation "
          "prior and the emission estimate: without the satellite constraint S2 avoids %s kt CO₂e yr⁻¹ instead of %s, and widening every prior by 50%% "
          "increases it to %s. Correlated inputs change no headline quantity by more than a few percent. With a first-order-decay supply trajectory, "
          "the median NPV of additional engines decreases from %s to %s MUSD and remains positive in %s of draws, while upgrading decreases from %s to %s MUSD."
          % (pct(min(v["P_pw_pos"] for v in RB["variants"])), pct(max(v["P_pw_pos"] for v in RB["variants"])),
             pct(min(v["P_cover"] for v in RB["variants"])), pct(max(v["P_cover"] for v in RB["variants"])),
             n(var("prior only (no satellite constraint)")["S2_avoided_kt"]), n(var("likelihood: lognormal")["S2_avoided_kt"]),
             n(var("priors widened by 50%")["S2_avoided_kt"]), n(tm["pw_median_ss"], 1), n(tm["pw_median_t"], 1), pct(tm["P_pw_pos_t"]),
             n(tm["up_median_ss"], 1), n(tm["up_median_t"], 1))))
rows7 = []
for v in RB["variants"]:
    rows7.append([v["variant"].replace("unoxidized", "unoxidized").replace("gauss", "Gaussian").replace("window", "uniform window"), n(v["eta22"], 3), n(v["eta_c"], 3), n(v["S2_avoided_kt"]),
                  n(v["P_cover"], 2), n(v["S6b_npv"], 1), n(v["P_pw_pos"], 2), n(v["pstar_gnc"], 2), n(v["abate_S2"], 1), "no" if not v["any_scen_median_pos"] else "yes"])
add(("table", "Table 7. Robustness of the headline quantities (medians unless stated). η: inferred collection efficiency; S2 avoided in kt CO₂e "
              "yr⁻¹; P(cover): probability that the cover reduces net emissions; S6b NPV in MUSD; P(PW > 0): probability that additional engines have "
              "positive NPV given surplus gas; p*: bio-GNC break-even price in US$ per Nm³; abatement cost of S2 in US$ per tCO₂e; last column: does any "
              "integrated scenario have a positive median NPV?",
     ["Variant", "η 2022", "η 2025–26", "S2 avoided", "P(cover)", "S6b NPV", "P(PW>0)", "p*", "Abatement S2", "Any > 0"], rows7,
     [3.0, 0.7, 0.8, 0.8, 0.8, 0.8, 0.8, 0.6, 0.9, 0.7]))
add(("fig", "Fig9_robustness.png", "Fig. 9. Headline quantities under the observation-error models (blue), without the satellite constraint (grey) and "
            "under the other robustness variants (green); the dotted line marks the base case.", 6.6))

# ============================================================================================ 5 Discussion
add(("h1", "5. Discussion"))
add(("h2", "5.1 What the model says about priorities"))
add(("p", "The largest finding concerns scale. Collected methane is approximately %s t h⁻¹, whereas the satellite-constrained generation is approximately %s t h⁻¹, so "
          "most generated methane is not collected. The measures that change the balance are those that increase collection efficiency, at approximately %s kt "
          "CH₄ yr⁻¹ per percentage point; coatings, PV and buffers act on the margin. The integrated package S7 lowers per-tonne emissions by a median "
          "%s. This conclusion follows from the reported capture and the satellite constraint and does not depend on the economic priors, but its "
          "size depends on which satellite estimate is trusted (Sections 4.2 and 4.3). Because measured collection efficiencies at active sites span "
          "a wide range [@Spokas2006;@Giordano2024;@Saul2026], a site flux campaign is the measurement with the largest value of information."
          % (n(g["C_Nm3h"][1] * M.RHO / 1e3, 1), n(g["G_Nm3h"][1] * M.RHO / 1e3), n(h["per_pp_eta_tCH4_yr_q"][1] / 1e3, 1), pct(h["H5_rel_reduction_q"][1] / 100))))
add(("h2", "5.2 Decisions that are robust, and decisions that are not"))
add(("p", "Robust under the stated priors and every variant: no integrated measure pays without credit revenue; abatement is cheap per tonne; a cover "
          "needs a minimum captured share to help; a buffer does not pay; additional engines on genuinely uncommitted surplus gas are profitable at "
          "merchant and contracted tariffs. Not robust: the existence of surplus gas once the engine expansion is complete; the profitability of the "
          "engines under a low tariff, downtime and a declining supply; the ranking of the capture measures by abatement cost, which depends on the "
          "emission estimate; and the comparison of paint with PV, which depends on three unvalidated numbers. The break-even prices, $s_c^*$ and "
          "$\\eta^*$ are the portable outputs, readable against a dated quotation or a measured captured share. We "
          "recommend that no capital be committed to coatings, buffers or upgrading before three measurements are in hand: a calibrated site flux "
          "survey to fix the collection efficiency, hourly gas flow and engine dispatch records to fix the true surplus, and a firm offtake or tariff "
          "quotation."))
add(("p", "A field protocol would turn the check of Section 4.3 into a validation. (i) Facility-wide emission measurements across seasons "
          "with an independent method, for example tracer-gas dispersion or airborne mass balance, reported with wind and sampling uncertainty. (ii) A "
          "time series of satellite retrievals from more than one instrument with a common wind product, so that the 2019–22 and 2025 values can be "
          "compared on equal terms. (iii) Hourly biogas flow, "
          "methane fraction and engine dispatch, which fix $C$ and the surplus directly. (iv) Pre-registration of the model's predictive interval "
          "for the surface emission (%s t h⁻¹, Section 4.1) before the measurements are made, and its comparison with them afterwards. The operator "
          "reports that it now uses drones with the Sniffer method to measure fugitive emissions [@Canal26]; publication of those data would serve "
          "(i) and (iv)."
          % q3(g["E_atm_th"])))
add(("h2", "5.3 Limitations"))
add(("p", "The model is a lumped-parameter screening tool. It has no spatial gas-flow solution, so the hot-spot fraction, barrier effectiveness and "
          "captured share are parameters, not predictions; a pressure-resolved porous-media model is the next step for the cover question. The "
          "satellite constraint rests on a few retrievals from 2019–22 with wind and retrieval uncertainty, and the three error models span but do not "
          "exhaust the possibilities. The efficiency is determined by the emission, the oxidation fraction and the reported capture alone, so an error in "
          "any of them passes directly into it; the generation prior only restricts the draws. The model overpredicts the one independent 2025 "
          "observation by a factor of approximately %s and is externally unvalidated at facility scale (Section 4.3). The generation prior and the growth factor "
          "that carries it to 2025–26 are assumptions. Operator figures were taken as reported, and the 23 MW and 33 MW capacities come from the white "
          "paper's summary of the operator statement. Prices are anchored to the benchmarks of Table 2, but peso conversions and the plant-gate price a "
          "bio-GNC buyer would actually pay are assumptions. The engine slip, marginal grid factor, flare counterfactual and displacement ranges of "
          "Section 4.7 are assumptions, and credit additionality is not modeled. The PV-paint concept derives from the author's unpublished "
          "competition submission, and no experimental data exist for it; treating its performance as a prior asks what it would need to achieve, "
          "not what it will achieve." % n(1.0 / VAL["ratio_obs_to_pred_median"], 1)))
add(("h2", "5.4 What would falsify these conclusions"))
TAB6 = [["Covers reduce net methane", "The captured share of blocked gas falls below $s_c^*$ (median %s), for example when extraction headroom or "
         "header capacity is limiting." % n(h["H1_sc_star_q"][1], 2)],
        ["Biomethane loses to power", "A firm bio-GNC price above approximately US$%s per Nm³, or electricity worth less than the engines' break-even (median "
         "US$%s per MWh), or no engine capacity can be added." % (n(h["pstar_gnc_pw_q"][1], 2), n(h["pel_star_q"][1]))],
        ["Surplus gas exists", "The 33 MW expansion is commissioned (surplus positive in %s of those draws, median %s Nm³ CH₄ h⁻¹), or hourly records show "
         "all collected gas committed." % (pct(h["P_surplus_gt0_P_el_ge31"]), n(h["surplus_P_el_ge31"][1]))],
        ["Collection efficiency near 0.14 to 0.24", "A calibrated flux survey after the 2025–26 capture increase finds a surface emission outside about "
         "%s to %s t h⁻¹, or capture measured against generation inferred from deposition exceeds 0.5." % (n(J1["E26"][0]), n(g["E_atm_th"][2]))],
        ["PV paint is unlikely to beat PV", "Validated efficiency exceeds $\\eta^*$ for its measured cost and life (Fig. S2a)."]]
add(("table", "Table 8. Conditions under which each conclusion fails.", ["Conclusion", "Fails if"], TAB6, [2.4, 5.4]))

# ============================================================================================ 6 Conclusions
add(("h1", "6. Conclusions"))
for t in ("A methane balance constrained by satellite estimates at their own observation date implies a collection efficiency of approximately %s in 2022 "
          "and %s in 2025–26 at Norte III, increasing to %s when an independent 2025 observation is added. The efficiency is determined by the emission, "
          "the oxidation fraction and the reported capture, not by the generation prior; it is conditional on the data and the model and is not a "
          "measurement. The leading mitigation lever is collection efficiency, worth approximately %s kt CH₄ yr⁻¹ per percentage point."
          % (n(g["eta22"][1], 2), n(g["eta_c"][1], 2), n(J1["eta_c"][1], 2), n(h["per_pp_eta_tCH4_yr_q"][1] / 1e3, 1)),
          "The model overpredicts the one independent 2025 emission observation by a factor of approximately %s and is externally unvalidated at facility "
          "scale; a field-measurement protocol is proposed to resolve this." % n(1.0 / VAL["ratio_obs_to_pred_median"], 1),
          "None of the eight integrated intervention scenarios has a positive median incremental NPV under the assumed no-credit conditions, although "
          "the median abatement costs are US$%s to %s per tCO₂e; credit eligibility, not engineering feasibility, decides bankability."
          % (n(min(SC[s]["abate_q"][1] for s in M.SCEN), 1), n(max(SC[s]["abate_q"][1] for s in M.SCEN), 1)),
          "Additional engines on uncommitted surplus gas are profitable in %s of draws that have surplus gas at merchant tariffs, but in %s of all "
          "operating states once the 33 MW expansion is complete, and their climate benefit is a few percent of that of the capture measures; "
          "biomethane would need approximately US$%s per Nm³ (US$%s per MMBtu) to break even."
          % (pct(h["H3_P_power_npv_pos"]), pct(pwrow("planned")["P_pos_all"]), n(h["pstar_gnc_q"][1], 2), n(h["pstar_gnc_mmbtu_q"][1])),
          "A selective cover helps only when the captured share of the gas it blocks exceeds a closed-form threshold (median %s); gross capture "
          "overstates the net benefit by approximately one-third." % n(h["H1_sc_star_q"][1], 2),
          "Every scenario closes its methane, carbon and energy balances, and the decision conclusions survive alternative generation histories, "
          "satellite scaling and error, correlated inputs, structural cover alternatives, tax and financing assumptions and climate-accounting choices."):
    add(("num", t))

# ============================================================================================ declarations
add(("h1", "Declarations"))
add(("p0", "CRediT authorship contribution statement. Leon Sandler: Conceptualization, Methodology, Software, Formal analysis, Investigation, "
           "Writing – original draft, Writing – review and editing."))
add(("p0", "Declaration of generative AI and AI-assisted technologies in the writing process. During the preparation of this work the author used "
           "Claude (Anthropic) to assist with source gathering, code development, drafting and editing. The author reviewed and edited the content as "
           "needed and takes full responsibility for the content of the publication."))
add(("p0", "Funding. This research received no external funding."))
add(("p0", "Declaration of competing interest. The author declares no known competing financial interests or personal relationships that could have "
           "influenced the work reported in this paper. The PV-coating concept examined in Section 4.8 originates from the author's own unpublished "
           "competition submission."))
code_doi = DOIS.get("code_concept", DOIS.get("code", "to be assigned"))
paper_doi = DOIS.get("paper_concept", DOIS.get("paper", "to be assigned"))
add(("p0", "Data and code availability. The model (NorteIII_MC.py), the identifiability and counterfactual analyses (NorteIII_review.py), the automated "
           "tests, the figure and export code (NorteIII_figs.py), the parameter table and all results are available at %s and archived at "
           "https://doi.org/%s (software, all versions; this manuscript describes version %s); this manuscript and its Supplementary Information are "
           "archived at https://doi.org/%s (all versions). One command regenerates every number, table and figure." % (GITHUB, code_doi, VERSION, paper_doi)))
add(("refs",))

# ============================================================================================ Supplementary Information
BS = []
adds = BS.append
adds(("title", "Supplementary Information"))
adds(("small", "for: " + TITLE))
adds(("author", "Leon Sandler"))
adds(("blank",))
adds(("h1", "S1. Identifiability: variance shares, contraction and dependence"))
adds(("p", "Eq. (12) of the manuscript gives the 2022 collection efficiency from the satellite emission, the oxidation fraction and the reported "
           "capture. It holds to %s in the sampled draws. Because the log-odds of capture is a sum of three terms, its variance divides into shares: "
           "in the prior (draws consistent with η ≤ 0.95) the emission carries %s of the variance of ln[(1−η)/η] (standard deviation %s), the reported "
           "capture %s and oxidation %s; in the lognormal posterior the shares are %s, %s and %s (standard deviation %s). Table S1 gives the "
           "prior-to-posterior contraction of the inputs that enter generation; contraction is 1 − IQR(posterior)/IQR(prior), and KS is the "
           "Kolmogorov–Smirnov distance between the two marginals."
           % ("%.0e" % max(ID["closed_form_max_abs_diff"], 1e-16), pct(ID["logodds_shares_prior"]["lnE"]), n(ID["logodds_shares_prior"]["sd_logodds"], 2),
              pct(ID["logodds_shares_prior"]["lnC"], 1), pct(ID["logodds_shares_prior"]["ln1mox"], 1), pct(cs["lnE"]), pct(cs["lnC"]), pct(cs["ln1mox"], 1),
              n(cs["sd_logodds"], 2))))
rowsS1 = []
for nm_, lab_ in (("Awaste", "Waste acceptance A (t/d)"), ("L0", "Methane potential L0 (Nm³ CH₄/t)"), ("fss", "Steady-state fraction f_ss"),
                  ("xCH4", "Methane fraction"), ("ox", "Oxidation fraction"), ("Qcoll22", "Collected biogas 2022 (Nm³/h)"),
                  ("G22", "Generation G22 (Nm³ CH₄/h)"), ("eta22", "Efficiency η 2022")):
    c_ = cp[nm_]
    d_ = 2 if nm_ in ("fss", "xCH4", "ox", "eta22") else 0
    rowsS1.append([lab_, qc(c_["prior_q"], d_), qc(c_["post_q"], d_), pct(c_["contraction"]), n(c_["ks"], 3)])
adds(("table", "Table S1. Prior-to-posterior contraction (prior: draws consistent with η ≤ 0.95; posterior: lognormal).",
      ["Input", "Prior, median (P5–P95)", "Posterior, median (P5–P95)", "Contraction", "KS"], rowsS1, [2.6, 1.8, 1.8, 0.9, 0.6]))
pcor = ID["post_corr"]
adds(("p", "Posterior correlations (Pearson, of logarithms for the generation terms) are: ln L0 with ln f_ss %s (prior %s), ln G22 with η22 %s, ln E22 with "
           "η22 %s, ln L0 with η22 %s and ln f_ss with η22 %s. The negative correlation between L0 and f_ss is the ridge along which generation is "
           "constant; the satellite constraint selects the ridge, not a point on it."
           % (n(pcor["lnL0,lnfss"], 2), n(ID["prior_corr"]["lnL0,lnfss"], 2), n(pcor["lnG22,eta22"], 2), n(pcor["eta22,lnE22"], 2), n(pcor["lnL0,eta22"], 2),
              n(pcor["lnfss,eta22"], 2))))
adds(("h1", "S2. Photovoltaic coating against conventional photovoltaics"))
adds(("p", "On the covered area, conventional PV has a positive NPV in %s of draws and a median LCOE of US$%s per MWh, above the merchant value of "
           "electricity because of the landfill foundation premium, the capital premium and the discount rate. The paint, with deliberately wide "
           "priors (efficiency 2 to 10%%, installed cost US$5 to 150 per m², life 2 to 20 years), has a median LCOE of US$%s per MWh and is cheaper in %s "
           "of draws. Setting the levelised cost of the paint equal to that of conventional PV gives the break-even efficiency"
           % (pct(h["H2_P_conv_npv_pos"], 1), q3(h["H2_lcoe_conv_q"]), q3(h["H2_lcoe_paint_q"]), pct(h["H2_P_paint_lcoe_lower"]))))
adds(("eq", r"\eta^*=\frac{c_{pt}\,\kappa\,[CRF(r,L_{pt})+o_{pt}]}{LCOE_{\rm conv}\,H_{poa}\,PR}", "S1"))
adds(("p", "which has a median of %s and exceeds 10%% in %s of draws (Fig. S2a). The %s figure is a property of unvalidated priors; the transferable "
           "result is the $\\eta^*$ surface. Verified against the simulation: setting the paint efficiency to $\\eta^*$ gives LCOE parity to numerical precision "
           "(automated test)."
           % (pct(h["H2_eta_star_q"][1], 1) + " (%s to %s)" % (pct(h["H2_eta_star_q"][0], 1), pct(h["H2_eta_star_q"][2], 1)), pct(h["H2_P_eta_star_gt_10pct"]),
              pct(h["H2_P_paint_lcoe_lower"]))))
adds(("fig", "FigS2_paint_vs_pv.png", "Fig. S2. (a) Break-even efficiency of PV paint for LCOE parity with conventional PV against installed cost, for three "
              "lifetimes (other inputs at posterior medians). (b) Distribution of the LCOE ratio.", 6.2))
adds(("h1", "S3. Input distributions"))
adds(("p0", "Table S2 lists the sampled inputs. Distributions are triangular (minimum, mode, maximum), uniform (minimum, maximum) or lognormal (σ, mean "
            "1). Tags: R, operator-reported or published programme value; L, literature or standard value; B, dated market or regulatory benchmark "
            "(Table 2 of the manuscript); A, assumed by the author and requiring a site-specific or dated quotation before use in a decision. Inputs "
            "marked * enter only the robustness variants. The sensitivities of Sections 3.8 and 3.9 of the manuscript (alternative generation priors, "
            "satellite scaling, engine slip 1 to 6%, marginal grid factor 0.35 to 0.65 with mode 0.45, counterfactual flare destruction 0.80 to 0.98, "
            "displacement 0.3 to 1.0) are tag A and are defined in NorteIII_review.py."))


def fmt_arg(x):
    if abs(x) >= 1000:
        return n(x)
    return "%g" % x


rowsA = []
for name, dist, args, tag, desc in M.P:
    a = ", ".join(fmt_arg(v) for v in args)
    rowsA.append([name + ("*" if name in M.ROBUST_ONLY else ""), desc, {"tri": "tri", "uni": "uni", "logn": "logn"}[dist] + "(" + a + ")", tag])
adds(("table", "Table S2. Input distributions.", ["Input", "Description", "Distribution", "Tag"], rowsA, [1.1, 4.6, 1.8, 0.5], 15))
adds(("h1", "S4. Balances and automated tests"))
rowsB = []
for s in ("S0", "S1", "S2", "S4", "S6", "S6b", "S7"):
    b = bm[s]
    rowsB.append([s, n(b["ch4_emit"] * M.RHO / 1e6, 1), n(b["ch4_ox"] * M.RHO / 1e6, 1), n(b["ch4_destroy"] * M.RHO / 1e6, 1),
                  n(b["ch4_export"] * M.RHO / 1e6, 1), n(b["c_co2_bio"] / 1e3, 1), n(b["e_product"] / 1e3, 1), n(b["elec_in"] / 1e3, 1),
                  n(b["co2e"] / 1e6, 2)])
adds(("table", "Table S3. Scenario balances for the median draw: methane emitted, oxidized, destroyed and exported (kt CH₄ yr⁻¹); biogenic carbon "
               "released as CO₂ (kt C yr⁻¹); biomethane energy exported and grid electricity used (GWh yr⁻¹); total emissions (Mt CO₂e yr⁻¹, GWP100). "
               "Residuals of all balances are below 10⁻⁹ of generation.",
      ["Scenario", "Emitted", "Oxidised", "Destroyed", "Exported", "Biogenic C", "Exported energy", "Electricity", "Total CO₂e"], rowsB,
      [0.8, 0.8, 0.8, 0.8, 0.8, 0.9, 1.0, 0.9, 0.9]))
adds(("fig", "FigS3_balances.png", "Fig. S3. (a) Fate of the generated methane by scenario (median draw). (b) Climate account from the balances: methane "
              "avoided (GWP100) and fossil CO₂ displaced net of grid electricity used, relative to S0.", 6.4))
adds(("p0", "The automated test suite (python NorteIII_MC.py --test) contains %d checks, all of which pass: unit conversions (methane mass, carbon "
            "content, annuity and capital recovery factors); Latin-hypercube moments and the induced rank correlation; the white paper's screening "
            "arithmetic; closure of the cover balance; the analytic break-even $s_c^*$; two limiting cases of the cover; methane and carbon closure of "
            "seven scenario balances; methane and energy closure of four upgrader accounts; equality of balance-based and incremental climate benefits "
            "for four scenarios; a hand-calculated upgrading case; an explicit cash-flow benchmark of the annuity NPV; unprofitability at zero gas "
            "prices; LCOE parity at $\\eta^*$; the calibration window; physical consistency of the posterior; determinism; the steady-state limit of the "
            "time-resolved NPV and the analytic slow-decay limit of the first-order-decay model; the closed-form identity of the collection "
            "efficiency and the additive identity of its log-odds; the uninformative limit of the observation model; the reproduction of the annuity NPV "
            "by the engine counterfactual in the constant-supply and fast-decay limits; the capital-and-O&M floor under full curtailment; the zero of the "
            "engines' climate benefit at the break-even slip; the consistency of the conditional and unconditional probabilities; and the Monte Carlo "
            "standard error." % NTEST))
adds(("fig", "FigS1_convergence.png", "Fig. S1. Running probability of positive NPV for S6b across three independent seeds (resampled lognormal "
              "posterior; ESS in the legend).", 5.4))
adds(("p0", "Balances and climate account. In every scenario the methane, carbon and energy balances close to round-off (relative residuals below 10⁻⁹), and the climate benefit "
            "computed from the balances equals the incremental benefit to within 10⁻⁸. For a median draw in the reference case %s kt CH₄ yr⁻¹ is emitted, %s kt is oxidized in the cover soil "
            "and %s kt is destroyed in engines and flares; the measures shift methane from the first category to the third, and upgrading exports %s kt CH₄ yr⁻¹ as biomethane (Table S3 and "
            "Fig. S3). The fossil-CO₂ credit of upgrading (displaced natural gas minus grid electricity used) is small against the methane term."
            % (n(bm["S0"]["ch4_emit"] * M.RHO / 1e6), n(bm["S0"]["ch4_ox"] * M.RHO / 1e6), n(bm["S0"]["ch4_destroy"] * M.RHO / 1e6), n(bm["S6"]["ch4_export"] * M.RHO / 1e6, 1))))
adds(("h1", "S5. Scorecard for the research hypotheses"))
TAB5 = [["H1: cover plus pressure-managed extraction lowers total emissions", "Supported conditionally: net reduction in %s of draws if $s_c > s_c^*$ "
         "(median %s); net benefit is %s of gross capture." % (pct(h["H1_P_cover_reduces_conv"]), n(h["H1_sc_star_q"][1], 2), pct(h["H1_gross_vs_net_ratio_median"]))],
        ["H2: PV coatings beat conventional PV only above measurable thresholds", "Paint cheaper in %s of draws under wide, unvalidated priors; "
         "break-even efficiency %s at median inputs." % (pct(h["H2_P_paint_lcoe_lower"]), pct(h["H2_eta_star_q"][1], 1))],
        ["H3: biomethane from surplus gas has higher risk-adjusted NPV than alternatives", "Not supported: beats additional engines in %s of draws; "
         "break-even US$%s per Nm³ (US$%s per MMBtu)." % (pct(h["H3_P_up_beats_power"], 2), n(h["pstar_gnc_q"][1], 2), n(h["pstar_gnc_mmbtu_q"][1]))],
        ["H4: buffering offsets its leakage, energy and capital costs", "Not supported: positive in %s of draws; median ΔNPV %s MUSD."
         % (pct(h["H4_P_buffer_pos"], 2), n(h["H4_buf_q"][1], 2))],
        ["H5: the integrated configuration has lower lifecycle CO₂e per tonne of waste", "Supported but small: S7 lower in %s of draws; median "
         "reduction %s, from %s to %s tCO₂e per tonne." % (pct(h["H5_P_S7_lower"], 1), pct(h["H5_rel_reduction_q"][1] / 100, 1),
                                                            n(h["H5_base_tCO2e_per_t_waste_q"][1], 2), n(h["H5_S7_tCO2e_per_t_waste_q"][1], 2))]]
adds(("table", "Table S4. Outcome of the five hypotheses of the project white paper (lognormal posterior).", ["Hypothesis", "Result"], TAB5, [3.2, 4.6]))


# ============================================================================================ build
def build(path, blocks, cit, with_refs=True, journal=False, line_numbers=True, eq_images=False):
    doc = E.Doc(cit, journal, line_numbers, eq_images)
    num = 0
    for b in blocks:
        k = b[0]
        if k == "title":
            doc.title(b[1])
        elif k == "author":
            doc.centered(b[1], 24)
        elif k == "small":
            doc.centered(b[1], 19)
        elif k == "blank":
            doc.blank()
        elif k == "h1":
            doc.h1(b[1])
        elif k == "h2":
            doc.h2(b[1])
        elif k == "p":
            doc.p(b[1])
        elif k in ("p0", "bullet", "num"):
            t = b[1]
            if k == "bullet":
                t = "• " + t
            elif k == "num":
                num += 1
                t = "%d. %s" % (num, t)
            doc.p(t, indent=False)
        elif k == "eq":
            doc.eq(b[1], b[2])
        elif k == "fig":
            doc.fig(os.path.join(FIG, b[1]), b[2], b[3])
        elif k == "table":
            doc.table(b[1], b[2], b[3], b[4] if len(b) > 4 else None, size=b[5] if len(b) > 5 else 16)
        elif k == "pagebreak":
            doc.pagebreak()
        elif k == "caplist":
            doc.caplist(b[1], b[2])
        elif k == "refs":
            doc.h1("References")
            for _, text in cit.entries():
                par = doc.d.add_paragraph()
                E._spacing(par, 0, 60)
                if journal:
                    doc._ds(par)
                par.paragraph_format.left_indent = E.Emu(317 * 635)
                par.paragraph_format.first_line_indent = E.Emu(-317 * 635)
                E.add_runs(par, text, 24 if journal else 18)
    doc.save(path)


# ============================================================================================ journal layout (Waste Management technical check, 2026-11-02)
# "the total number of figures + tables should be no more than 8": the manuscript keeps Figs 1-4 and Tables 1, 2 (old 4), 3 (old 5), 4 (old 8);
# the other tables and figures move to the Supplementary Information with new numbers, and every cross-reference is renumbered.
TAB_MAP = {"1": "1", "2": "S5", "3": "S6", "4": "2", "5": "3", "6": "S7", "7": "S8", "8": "4"}
FIG_MAP = {"1": "1", "2": "2", "3": "3", "4": "4", "5": "S4", "6": "S5", "7": "S6", "8": "S7", "9": "S8"}
MOVE_TAB = {"2", "3", "6", "7"}
MOVE_FIG = {"5", "6", "7", "8", "9"}
_REF = re.compile(r"(Supplementary )?(Table|Fig\.)\s(\d)(?![\d])")


def _renum(text, supp):
    """renumber 'Table N' / 'Fig. N' (digits only: S-numbered items are untouched); in the manuscript, moved items read 'Supplementary Table S5'"""
    def rep(m):
        kind, d = m.group(2), m.group(3)
        new = (TAB_MAP if kind == "Table" else FIG_MAP)[d]
        pre = "Supplementary " if (new.startswith("S") and not supp) else ""
        return "%s%s %s" % (pre, kind, new)
    out = _REF.sub(rep, text)
    return re.sub(r"(Table S\d) of the manuscript", r"\1", out) if supp else out


def _map_block(b, supp):
    out = [b[0]]
    for x in b[1:]:
        if isinstance(x, str):
            out.append(_renum(x, supp))
        elif isinstance(x, list):
            out.append([[(_renum(c, supp) if isinstance(c, str) else c) for c in row] if isinstance(row, list) else (_renum(row, supp) if isinstance(row, str) else row)
                        for row in x])
        else:
            out.append(x)
    return tuple(out)


def journal_blocks():
    main, moved = [], []
    for b in B:
        cap = b[2] if b[0] == "fig" else (b[1] if b[0] == "table" else "")
        m = re.match(r"(Table|Fig\.)\s(\d)\.", cap or "")
        if m and ((m.group(1) == "Table" and m.group(2) in MOVE_TAB) or (m.group(1) == "Fig." and m.group(2) in MOVE_FIG)):
            moved.append(b)
        else:
            main.append(b)
    order = lambda b: int(re.match(r"(?:Table|Fig\.)\s(\d)", b[2] if b[0] == "fig" else b[1]).group(1))
    jm = [_map_block(b, False) for b in main]
    si = [_map_block(b, True) for b in BS]
    si.append(("h1", "S6. Further tables and figures of the main analysis"))
    si.append(("p0", "These tables and figures were part of the main text of the first submission and moved here to keep the main text within eight tables and "
                     "figures. They are cited from the main text as Supplementary Tables S5 to S8 and Supplementary Figs. S4 to S8."))
    for b in sorted((x for x in moved if x[0] == "table"), key=order):
        si.append(_map_block(b, True))
    for b in sorted((x for x in moved if x[0] == "fig"), key=order):
        si.append(_map_block(b, True))
    return jm, si


def submission_blocks(jm):
    """Waste Management technical check (2026-11-04): tables each on a separate page at the end of the Word file, then the list of figure captions on its own page;
    the figures themselves are uploaded as separate files (Fig1_..., Fig2_..., numbered) and are not placed in the Word file."""
    text, tabs, figs = [], [], []
    for b in jm:
        (tabs if b[0] == "table" else figs if b[0] == "fig" else text).append(b)
    out = list(text)
    for t in tabs:
        out += [("pagebreak",), t]
    out += [("pagebreak",), ("caplist", "List of figure captions", [f[2] for f in figs])]
    return out


def scan_all(cit, blocks=None):
    for b in (blocks if blocks is not None else B + BS):
        for x in b[1:]:
            if isinstance(x, str):
                cit.scan(x)
            elif isinstance(x, list):
                for row in x:
                    for c in (row if isinstance(row, list) else [row]):
                        if isinstance(c, str):
                            cit.scan(c)


if __name__ == "__main__":
    for t in [b[1] for b in B if b[0] == "bullet"]:
        assert len(t) <= 85, (len(t), t)
    os.makedirs(OUT, exist_ok=True)
    cit = Harvard(LIB)
    JB, JS = journal_blocks()
    scan_all(cit, JB + JS)
    build(os.path.join(OUT, "NorteIII_Waste_Management_Manuscript_v3.docx"), submission_blocks(JB), cit, journal=True)
    build(os.path.join(OUT, "NorteIII_Supplementary_Information_v3.docx"), JS, cit)
    # complete manuscript for ChemRxiv: figures and tables in the text, no line numbers, equations as pictures (a Word-to-PDF conversion on the server mishandled Office Math)
    build(os.path.join(OUT, "NorteIII_ChemRxiv_Manuscript.docx"), JB, cit, journal=False, eq_images=True)
    # main figures for upload, with the figure number in the file name
    import shutil
    up = os.path.join(OUT, "figures_for_upload"); os.makedirs(up, exist_ok=True)
    for f in sorted(os.listdir(FIG)):
        if re.match(r"Fig[1-4]_", f):
            shutil.copy(os.path.join(FIG, f), os.path.join(up, f))
    words = sum(len(b[1].split()) for b in B if b[0] in ("p", "p0", "num") and not b[1].startswith(("CRediT", "Declaration", "Funding", "Data and")))
    abstract = [b[1] for b in B if b[0] == "p0"][0]
    print("built; %d references; abstract %d words; text ~%d words" % (len(cit.used), len(abstract.split()), words))
    assert len(abstract.split()) <= 250, "abstract too long"
