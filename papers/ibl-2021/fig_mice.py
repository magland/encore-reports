"""Interactive figure: every mouse's learning curve and psychometric curves, linked by mouse.

Reads the cache written by compute.py. One item per mouse whose whole training is in the
dataset (136), colored by lab:
- learning: % correct on easy trials (50% and 100% contrast) on each training day, with the
  day of basic task proficiency (P1) marked;
- basic task proficiency: the psychometric fit and the choice fractions of the sessions of the
  P1 day and the two days before it (S1);
- full task proficiency: the fits for the 20:80 and 80:20 blocks at full task proficiency (S2).

Run from the repository root:  .venv/bin/python papers/ibl-2021/fig_mice.py [--upload]
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from figpack_experimental.views import LinkedCurves

import ibl_behavior as ib

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "cache" / "ibl-2021"
TITLE = "IBL 2021: learning and psychometric curves of every mouse, by lab"
SYMLOG_C = 5.0
CONTRAST_TICKS = [-100, -25, -6.25, 0, 6.25, 25, 100]

DESCRIPTION = """\
One curve set per mouse of the IBL project whose whole training is in DANDI:000045 (136 mice,
first session 2019-06-11 or later), colored by laboratory. Left: percent correct on easy trials
(50% and 100% contrast) on each training day; the marker is the day the mouse reached basic task
proficiency (83 mice). Middle: rightward choices against signed contrast in the basic-task
sessions of that day and the two days before it, with the psychometric fit (81 mice with a fit).
Right: the fits at full task proficiency for the 20:80 blocks (right more likely, solid) and the
80:20 blocks (left more likely, dashed) (60 mice). Proficiency and fits are computed with the
code of the Encore attempt ibl-2021-01, under its main reading of the paper's criteria.
"""


def fit_curve(pars, xs):
    return 100 * ib.gamma_curve(pars, xs)


def main():
    mice = pd.read_parquet(CACHE / "mice.parquet").set_index("subject_id")
    daily = pd.read_parquet(CACHE / "daily.parquet")
    s1 = pd.read_parquet(CACHE / "s1_fits.parquet").set_index("subject_id")
    s1_pts = pd.read_parquet(CACHE / "s1_points.parquet")
    s2 = pd.read_parquet(CACHE / "s2_fits.parquet")

    # order mice by lab, then by days to proficiency, so items in a lab are adjacent
    mice = mice.assign(days=mice.p1_tday0 + 1).sort_values(["lab", "days", "nickname"])
    idx = {m: i for i, m in enumerate(mice.index)}
    labels = [f"{r.nickname}: " + (f"proficient on day {int(r.days)}" if pd.notna(r.days)
                                   else f"not proficient in {int(r.n_days)} days")
              for r in mice.itertuples()]

    view = LinkedCurves(item_labels=labels, item_groups=mice.lab.tolist(), num_columns=3)
    p_learn = view.add_panel(title="Learning", x_label="training day",
                             y_label="% correct on easy trials", y_range=(0, 102),
                             legend_position="lower right")
    p_basic = view.add_panel(title="At basic task proficiency", x_label="signed contrast (%)",
                             y_label="% rightward choices", y_range=(-2, 102), x_scale="symlog",
                             symlog_constant=SYMLOG_C, x_ticks=CONTRAST_TICKS)
    p_full = view.add_panel(title="At full task proficiency", x_label="signed contrast (%)",
                            y_label="% rightward choices", y_range=(-2, 102), x_scale="symlog",
                            symlog_constant=SYMLOG_C, x_ticks=CONTRAST_TICKS)

    # a fine grid evenly spaced on the symlog axis
    u = np.linspace(-np.log10(1 + 100 / SYMLOG_C), np.log10(1 + 100 / SYMLOG_C), 121)
    xs = np.sign(u) * SYMLOG_C * (10 ** np.abs(u) - 1)
    pars = ["bias", "threshold", "lapselow", "lapsehigh"]

    for m, d in daily[daily.subject_id.isin(idx)].groupby("subject_id"):
        d = d.sort_values("tday0")
        view.add_curve(p_learn, item=idx[m], x=d.tday0 + 1, y=d.perf_easy, series="daily % correct")
        p1 = mice.loc[m, "p1_tday0"]
        if pd.notna(p1):
            y = d.set_index("tday0").perf_easy.get(int(p1), np.nan)
            view.add_curve(p_learn, item=idx[m], x=[p1 + 1], y=[y], style="markers",
                           marker_size=4, series="basic task proficiency")
    for m, r in s1.iterrows():
        if m not in idx or r[pars].isna().any():
            continue
        view.add_curve(p_basic, item=idx[m], x=xs, y=fit_curve(r[pars].to_dict(), xs), series="fit")
        pts = s1_pts[s1_pts.subject_id == m]
        view.add_curve(p_basic, item=idx[m], x=pts.signed_contrast, y=100 * pts["mean"],
                       style="markers", marker_size=2.5, series="data")
    for (m, block), r in s2.set_index(["subject_id", "block"]).iterrows():
        if m not in idx or block == "5050" or r[pars].isna().any():
            continue
        view.add_curve(p_full, item=idx[m], x=xs, y=fit_curve(r[pars].to_dict(), xs),
                       dashed=(block == "8020"),
                       series="20:80 blocks (right likely)" if block == "2080" else "80:20 blocks (left likely)")

    if "--upload" in sys.argv:
        print(view.show(title=TITLE, description=DESCRIPTION, upload=True, open_in_browser=False,
                        wait_for_input=False))
    else:
        out = CACHE / "figures" / "mice"
        view.save(str(out), title=TITLE, description=DESCRIPTION)
        print(f"saved {out}")


if __name__ == "__main__":
    main()
