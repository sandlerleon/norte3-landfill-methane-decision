# -*- coding: utf-8 -*-
"""Cover letter for the Waste Management submission (numbers from results/results.json; DOIs from dois.json).
    python build_cover_letter.py   -> manuscript/NorteIII_Cover_Letter.docx"""
import datetime
import json
import os

from docx import Document
from docx.shared import Pt, Inches

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
R = json.load(open(os.path.join(ROOT, "results", "results.json"), encoding="utf-8"))
DOIS = json.load(open(os.path.join(HERE, "dois.json"), encoding="utf-8")) if os.path.exists(os.path.join(HERE, "dois.json")) else {}
import build_manuscript as BM

g, h, sc = R["posterior"]["gas"], R["posterior"]["hyp"], R["posterior"]["scen"]
d = Document()
st = d.styles["Normal"]; st.font.name = "Calibri"; st.font.size = Pt(11); st.paragraph_format.space_after = Pt(8)
for s in d.sections:
    s.left_margin = s.right_margin = Inches(1.0); s.top_margin = s.bottom_margin = Inches(0.9)


def para(t, bold=False, after=None):
    p = d.add_paragraph(); r = p.add_run(t); r.bold = bold
    if after is not None:
        p.paragraph_format.space_after = Pt(after)
    return p


para("Leon Sandler", True, 0)
for t in ("Independent Researcher", "Northbrook, Illinois, USA", "sandler.leon@gmail.com", "ORCID 0009-0007-4584-808X"):
    para(t, after=0)
para("")
para(datetime.date.today().strftime("%d %B %Y").lstrip("0"))
para("The Editor-in-Chief", after=0); para("Waste Management", after=0); para("Elsevier")
para("Dear Editor,")
para("I submit the manuscript “%s” as a Research Paper for consideration in Waste Management." % BM.TITLE)
para("Very large landfills are among the largest anthropogenic methane sources identified from space, yet site decisions are usually made without joining "
     "the operator's reported gas capture, independent emission estimates and the economics of the competing uses of the recovered gas. The manuscript does "
     "this for the Norte III landfill in Buenos Aires with a Monte Carlo decision model of 300,000 draws. A wide bottom-up generation prior is constrained by "
     "the satellite emission estimates at their own observation date, with the capture of that period, and carried forward to the 2025–26 decision period; "
     "three observation-error models are compared. The inferred collection efficiency, about %.2f in 2022 and %.2f in 2025–26, is reported as a model "
     "output conditional on the priors, not as a measurement." % (g["eta22"][1], g["eta_c"][1]))
para("The main results are decision-relevant and robust. None of the eight integrated intervention scenarios has a positive median incremental net present "
     "value under the assumed no-credit conditions, although the capture measures abate methane at a median of a few US dollars per tonne of CO₂e, so credit "
     "eligibility rather than engineering decides their bankability. Additional engines on genuinely uncommitted surplus gas, reported separately as the "
     "competing use, are profitable in %.0f%% of draws at merchant tariffs, whereas biomethane would need a bio-GNC plant-gate price of about US$%.2f per "
     "Nm³ (US$%.0f per MMBtu). A selective cover reduces net emissions only when the captured share of the gas it blocks exceeds a closed-form break-even "
     "(median %.2f), which the simulation reproduces."
     % (100 * h["H3_P_power_npv_pos"], h["pstar_gnc_q"][1], h["pstar_gnc_mmbtu_q"][1], h["H1_sc_star_q"][1]))
para("Three features distinguish the work. Every scenario closes explicit methane, carbon and energy balances, and the climate benefit computed from the "
     "balances equals the incremental formulas; the economic priors are anchored to dated Argentine benchmarks for gas, electricity, import duties, country "
     "risk, tax and carbon credits; and the conclusions are tested against correlated inputs, alternative and widened priors, structural alternatives for the "
     "cover, contracted against merchant electricity, after-tax and WACC discounting, expected credit revenue and a time-varying first-order-decay gas supply. "
     "%d automated tests (mass, carbon and energy closure, units, limiting cases and an independent cash-flow benchmark) must pass before results are produced." % BM.NTEST)
para("The study is a screening analysis built on published operator figures and satellite estimates; it uses no new site measurements and states which "
     "measurements would change the decisions: a calibrated site flux survey, hourly gas and engine dispatch records, and a firm offtake or tariff quotation. "
     "The model, tests, parameter table and results are openly available at https://github.com/sandlerleon/norte3-landfill-methane-decision and archived at "
     "https://doi.org/%s; the manuscript is archived at https://doi.org/%s. One command regenerates every number, table and figure."
     % (DOIS.get("code", "(to be assigned)"), DOIS.get("paper", "(to be assigned)")))
para("A generative AI tool (Claude, Anthropic) assisted with source gathering, code development, drafting and editing; I reviewed and checked all of it and "
     "take full responsibility for the content, as disclosed in the manuscript. The manuscript is original, has not been published elsewhere and is not under "
     "consideration at any other journal. I am the sole author, I have no competing interests, and the work received no external funding. The photovoltaic-coating "
     "concept examined in one scenario originates from my own unpublished competition submission, which is disclosed in the manuscript.")
para("Thank you for considering this submission.")
para("Sincerely,")
para("Leon Sandler", True)
out = os.path.join(ROOT, "manuscript", "NorteIII_Cover_Letter.docx")
d.save(out)
print("saved", out)
