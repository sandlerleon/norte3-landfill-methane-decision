# Landfill methane recovery and use under deep uncertainty: a satellite-constrained Monte Carlo decision model for the Norte III landfill

Leon Sandler, Independent Researcher — sandler.leon@gmail.com — ORCID 0009-0007-4584-808X

Code, data and manuscript for *"Landfill methane recovery and use under deep uncertainty: a satellite-constrained Monte Carlo decision model for the
Norte III landfill, Buenos Aires,"* prepared for **Waste Management** (Elsevier).

## What the model does

A Latin-hypercube Monte Carlo model (300,000 draws) of landfill-gas generation, collection, surface emission and oxidation, selective covers,
biomethane upgrading (bio-GNC, pipeline, hybrid), additional power generation, photovoltaics and a PV coating, applied to the Norte III landfill
(CEAMSE, Buenos Aires).

* **Satellite constraint in two periods.** A wide bottom-up generation prior is confronted with the 2019–22 satellite emission estimates at their own
  observation date (with the capture of that period) and carried forward to the 2025–26 decision period. Three observation-error models (uniform window,
  Gaussian, lognormal) are compared by importance resampling. The collection efficiency is an inferred model output, not a measurement.
* **Closed balances.** Every scenario closes methane, carbon and energy balances; the climate benefit from the balances equals the incremental formulas.
  Compression electricity is route-specific, plant fugitive methane and flared unsold product are counted, and the power alternative has a climate account.
* **Dated Argentine economics.** PIST gas price, delivered and retail GNC, wholesale and contracted electricity, capital-goods import duties, country risk,
  corporate tax and carbon-credit prices, each with its date and source (manuscript Table 2).
* **Robustness.** Correlated inputs (Iman–Conover), uniform and widened priors, structural cover alternatives, contracted electricity, WACC, after-tax NPV,
  discount-rate sweep, expected credit revenue with eligibility risk, and a first-order-decay gas trajectory.
* **Analytic break-evens.** The captured share of blocked gas above which a selective cover reduces net emissions, and the efficiency a PV coating needs
  to match conventional PV, both verified against the simulation.

Headline (lognormal posterior): none of the eight integrated intervention scenarios has a positive median incremental NPV under the assumed no-credit
conditions; additional engines on uncommitted surplus gas (reported separately) are profitable in most draws at merchant tariffs; biomethane needs a
bio-GNC plant-gate price of about US$0.46 per Nm³ to break even.

## Layout

```
code/       NorteIII_MC.py            model, calibration, balances, robustness, automated tests
            NorteIII_figs.py          figures, results.json and CSV tables (run through NorteIII_MC.py --run)
            build_manuscript.py       manuscript (.docx) from results/results.json; norte_references.py (reference library)
            build_cover_letter.py     cover letter
            docx_engine.py, omml.py, manuscript_template.docx   document engine (Office Math equations)
            dois.json                 Zenodo DOIs written into the manuscript and cover letter
results/    results.json, tests.json, parameters.csv, scenario_summary_posterior.csv, robustness_variants.csv, balances_median.csv
figures/    Fig1-Fig10, FigS1 (200 dpi)
manuscript/ NorteIII_Waste_Management_Manuscript_v2.docx, NorteIII_Cover_Letter.docx
```

## Reproduce

```
pip install -r requirements.txt
cd code
python NorteIII_MC.py --test          # 51 automated tests (closure, units, limiting cases, benchmarks); ~1 min
python NorteIII_MC.py --run           # 300,000 draws + robustness variants + figures; ~2 min
python build_manuscript.py            # manuscript from the stored results
python build_cover_letter.py
```

Published run: Python 3.11, NumPy 2.4.6, SciPy 1.17.1, Matplotlib 3.11.1 (Windows). Seeds are fixed; reruns reproduce results.json.

## Versions

* **v2.0.0** — Revision for Waste Management: two-period satellite calibration with three observation-error models and a widened generation prior;
  explicit methane, carbon and energy balances per scenario with closure tests; route-specific compression, plant fugitive methane, flared unsold
  product and a climate account for the power alternative; dated Argentine benchmarks, import duties, tax, WACC and credit eligibility; correlated
  inputs, alternative priors, structural alternatives and a first-order-decay trajectory; power alternative reported separately; 51 automated tests.
* v1 (not released) — first draft, single-period acceptance window.

## Licence

Code: MIT (LICENSE). Manuscript, figures and data: CC BY 4.0.
