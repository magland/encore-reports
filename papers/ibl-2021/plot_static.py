"""Static plots for the IBL 2021 report, written to images/ (run compute.py first).

- coverage.png: when each mouse of the project has its first session in the dataset, against
  the start of the paper's training (January 2019) and the dataset's first and last dates.
- days_by_lab.png: training days to basic task proficiency in each lab, with the training
  days of the mice that did not reach it in the dataset.

Run from the repository root:  .venv/bin/python papers/ibl-2021/plot_static.py
"""

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
CACHE = HERE.parents[1] / "cache" / "ibl-2021"
IMAGES = HERE / "images"

BLUE, ORANGE = "#2a78d6", "#eb6834"           # categorical slots 1 and 2 (validated pair)
GRAY = "#9a9893"
INK, INK2, LINE = "#0b0b0b", "#52514e", "#d9d8d4"
PAPER_START = pd.Timestamp("2019-01-01")      # the paper's mice began training in January 2019
PAPER_IQR = {"Lab 2": 8, "Lab 6": 22}         # within-lab interquartile ranges the paper gives

plt.rcParams.update({
    "font.family": "sans-serif", "font.size": 10, "text.color": INK, "axes.labelcolor": INK2,
    "axes.edgecolor": LINE, "xtick.color": INK2, "ytick.color": INK2,
    "axes.spines.top": False, "axes.spines.right": False, "figure.facecolor": "white",
})


def coverage_plot():
    p = pd.read_parquet(CACHE / "project_mice.parquet")
    s = json.loads((CACHE / "summary.json").read_text())
    start, end = pd.Timestamp(s["first_date"]), pd.Timestamp(s["last_date"])
    p["first"] = pd.to_datetime(p.first_date)
    bins = pd.date_range(PAPER_START, end + pd.Timedelta(days=14), freq="14D")
    whole = np.histogram(p.first[p.whole_training].astype("int64"), bins.astype("int64"))[0]
    other = np.histogram(p.first[~p.whole_training].astype("int64"), bins.astype("int64"))[0]
    left, width = bins[:-1], (bins[1] - bins[0]) * 0.85

    fig, ax = plt.subplots(figsize=(9, 3.6))
    ax.axvspan(PAPER_START, start, color=LINE, alpha=0.6, lw=0, zorder=0)
    ax.bar(left, whole, width=width, align="edge", color=BLUE, zorder=2,
           label=f"whole training in the dataset ({int(p.whole_training.sum())} mice)")
    ax.bar(left, other, width=width, bottom=whole, align="edge", color=GRAY, zorder=2,
           label=f"already past the first stage at their first session ({int((~p.whole_training).sum())} mice)")
    top = (whole + other).max()
    ax.text(PAPER_START + (start - PAPER_START) / 2, top * 0.62,
            "the paper's mice began training\nfrom January 2019;\nno sessions in the dataset",
            ha="center", va="center", fontsize=9, color=INK2)
    for d, lab in ((start, f"first session in the dataset\n{start:%Y-%m-%d}"),
                   (end, f"last session\n{end:%Y-%m-%d}")):
        ax.axvline(d, color=INK2, ls=(0, (3, 3)), lw=1, zorder=3)
        ax.text(d, top * 1.08, lab, ha="center", va="bottom", fontsize=8.5, color=INK2)
    ax.set_ylim(0, top * 1.35)
    ax.set_xlim(PAPER_START - pd.Timedelta(days=7), end + pd.Timedelta(days=21))
    ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=[1, 4, 7, 10]))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    ax.set_ylabel("mice (per 14 days)")
    ax.set_xlabel("date of the mouse's first session in the dataset")
    ax.grid(axis="y", color=LINE, lw=0.6, zorder=0)
    ax.legend(loc="upper left", bbox_to_anchor=(0.45, 0.74), frameon=False, fontsize=8.5)
    fig.tight_layout()
    out = IMAGES / "coverage.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print(f"wrote {out}; whole training {int(p.whole_training.sum())}, other {int((~p.whole_training).sum())}, "
          f"other starting on {start.date()}: {int((p.first[~p.whole_training] == start).sum())}")


def days_by_lab_plot():
    m = pd.read_parquet(CACHE / "mice.parquet").set_index("subject_id")
    d = pd.read_parquet(CACHE / "daily.parquet")
    end = pd.Timestamp(json.loads((CACHE / "summary.json").read_text())["last_date"])
    m["last"] = pd.to_datetime(d.groupby("subject_id").date.max())
    m["days"] = m.p1_tday0 + 1
    m["still_training"] = m["last"] >= end - pd.Timedelta(days=22)   # a session in the last 3 weeks
    labs = sorted(m.lab.unique(), key=lambda s: int(s.split()[1]))
    rng = np.random.default_rng(0)

    fig, ax = plt.subplots(figsize=(9, 4.4))
    rows = []
    for i, lab in enumerate(labs):
        y = len(labs) - 1 - i
        g = m[m.lab == lab]
        prof = g[g.days.notna()]
        q1, med, q3 = prof.days.quantile([0.25, 0.5, 0.75])
        ax.plot([q1, q3], [y, y], color=BLUE, lw=7, alpha=0.25, solid_capstyle="butt", zorder=1)
        ax.plot([med, med], [y - 0.2, y + 0.2], color=BLUE, lw=2, zorder=2)
        ax.scatter(prof.days, y + rng.uniform(-0.13, 0.13, len(prof)), s=18, color=BLUE, zorder=3,
                   label="reached basic task proficiency (day reached)" if i == 0 else None)
        for still, color, label in ((False, GRAY, "did not reach it; training ended earlier (days trained)"),
                                    (True, ORANGE, "did not reach it; still training at the end of the dataset (days trained)")):
            h = g[g.days.isna() & (g.still_training == still)]
            ax.scatter(h.n_days, y + rng.uniform(-0.13, 0.13, len(h)), s=18, facecolors="none",
                       edgecolors=color, linewidths=1.2, zorder=3, label=label if i == 0 else None)
        note = f"{len(prof)}/{len(g)} proficient, IQR {q3 - q1:g} d"
        if lab in PAPER_IQR:
            note += f" (paper {PAPER_IQR[lab]} d)"
        ax.text(1.01, y, note, transform=ax.get_yaxis_transform(), va="center", fontsize=8.5, color=INK2)
        rows.append((lab, len(prof), len(g), q3 - q1))
    ax.set_yticks(range(len(labs)))
    ax.set_yticklabels(labs[::-1])
    ax.set_ylim(-0.6, len(labs) - 0.4)
    shown = pd.concat([m.days.dropna(), m.n_days[m.days.isna()]])
    ax.set_xlim(0, shown.max() + 3)
    ax.set_xlabel("training days (to basic task proficiency, or in total for mice that did not reach it)")
    ax.grid(axis="x", color=LINE, lw=0.6, zorder=0)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.17), ncol=1, frameon=False, fontsize=8.5)
    fig.tight_layout()
    fig.subplots_adjust(right=0.70)
    out = IMAGES / "days_by_lab.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print(f"wrote {out}; {rows}")


if __name__ == "__main__":
    IMAGES.mkdir(exist_ok=True)
    coverage_plot()
    days_by_lab_plot()
