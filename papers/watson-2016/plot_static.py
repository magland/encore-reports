"""Static plots for the Watson 2016 report, written to images/ (run compute_cells.py first).

- first_last.png: each pE cell's rate in the first against the last nonREM packet of a sleep
  period, beside the control that the attempt used for regression to the mean: the first half
  of the first packet against its second half.
- sextiles.png: rates over sleep for each sextile of WAKE rate, normalized per sleep period,
  against the time of the nonREM packet within the period.

Run from the repository root:  .venv/bin/python papers/watson-2016/plot_static.py
"""

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
CACHE = HERE.parents[1] / "cache" / "watson-2016"
IMAGES = HERE / "images"

BLUE, ORANGE = "#2a78d6", "#eb6834"           # categorical slots 1 and 2 (validated pair)
GRAY = "#b8b6b0"
INK, INK2, LINE = "#0b0b0b", "#52514e", "#d9d8d4"

plt.rcParams.update({
    "font.family": "sans-serif", "font.size": 10, "text.color": INK, "axes.labelcolor": INK2,
    "axes.edgecolor": LINE, "xtick.color": INK2, "ytick.color": INK2,
    "axes.spines.top": False, "axes.spines.right": False, "figure.facecolor": "white",
    "axes.titlesize": 11, "axes.titleweight": "bold",
})


def fit(x, y):
    b, a = np.polyfit(x, y, 1)
    return a, b


def first_last_plot(summary):
    fl = pd.read_parquet(CACHE / "first_last.parquet")
    panels = [
        ("first", "last", "First against last nonREM packet",
         "rate in the first packet (Hz)", "rate in the last packet (Hz)", summary["slope_log10"]),
        ("first_half", "second_half", "Control: the two halves of the first packet",
         "rate in the first half (Hz)", "rate in the second half (Hz)", summary["slope_halves_log10"]),
    ]
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.6))
    lo, hi = 10 ** -2.3, 10 ** 1.4
    for ax, (cx, cy, title, xl, yl, s) in zip(axes, panels):
        k = (fl[cx] > 0) & (fl[cy] > 0)
        x, y = np.log10(fl[cx][k]), np.log10(fl[cy][k])
        ax.scatter(10 ** x, 10 ** y, s=6, color=BLUE, alpha=0.35, lw=0, zorder=2)
        ax.plot([lo, hi], [lo, hi], color=INK2, ls=(0, (3, 3)), lw=1, zorder=3)
        a, b = fit(x, y)
        xs = np.linspace(np.log10(lo), np.log10(hi), 50)
        ax.plot(10 ** xs, 10 ** (a + b * xs), color=INK, lw=1.6, zorder=4)
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_xlim(lo, hi)
        ax.set_ylim(lo, hi)
        ax.set_aspect("equal")
        ax.set_title(title, loc="left")
        ax.set_xlabel(xl)
        ax.set_ylabel(yl)
        ax.text(0.04, 0.96, f"slope {s['slope']:.2f} (95% CI {s['lo']:.2f} to {s['hi']:.2f})\n"
                            f"R = {s['r']:.2f}, {s['n']} cell-period pairs",
                transform=ax.transAxes, va="top", fontsize=9, color=INK)
        ax.text(0.97, 0.03, "dashed: equal rates\nsolid: fit on log rates", transform=ax.transAxes,
                ha="right", va="bottom", fontsize=8.5, color=INK2)
        ax.grid(color=LINE, lw=0.5, zorder=0)
    fig.tight_layout()
    out = IMAGES / "first_last.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print(f"wrote {out}")


def sextiles_plot(summary, nbins=5):
    pts = pd.read_parquet(CACHE / "sextile_points.parquet")
    pts = pts[np.isfinite(pts.y)]
    edges = np.linspace(0, 1, nbins + 1)
    centers = (edges[:-1] + edges[1:]) / 2
    fig, ax = plt.subplots(figsize=(8, 4.6))
    labels = {1: "sextile 1 (slowest)", 6: "sextile 6 (fastest)"}
    ends = {}
    for sx in (2, 3, 4, 5, 1, 6):
        d = pts[pts.sextile == sx]
        b = np.clip(np.digitize(d.x, edges) - 1, 0, nbins - 1)
        m = np.array([d.y[b == i].mean() for i in range(nbins)])
        se = np.array([d.y[b == i].std(ddof=1) / np.sqrt((b == i).sum()) for i in range(nbins)])
        color = {1: ORANGE, 6: BLUE}.get(sx, GRAY)
        lw = 2.2 if sx in (1, 6) else 1.0
        ax.plot(centers, m, color=color, lw=lw, marker="o", ms=4 if sx in (1, 6) else 2.5, zorder=3 if sx in (1, 6) else 2)
        if sx in (1, 6):
            ax.fill_between(centers, m - se, m + se, color=color, alpha=0.15, lw=0, zorder=1)
        ends[sx] = m[-1]
    # direct labels at the line ends, pushed apart so that they do not overlap
    order = sorted(ends, key=lambda k: ends[k])
    ys = [ends[k] for k in order]
    gap = 0.013
    for i in range(1, len(ys)):
        ys[i] = max(ys[i], ys[i - 1] + gap)
    shift = (np.mean([ends[k] for k in order]) - np.mean(ys))
    for k, y in zip(order, ys):
        r = summary["sextile_r"][str(k)]
        ax.text(centers[-1] + 0.03, y + shift, f"{labels.get(k, f'sextile {k}')}  R = {r['r']:+.2f}",
                va="center", fontsize=8.5, color=INK if k in (1, 6) else INK2)
    ax.axhline(1, color=INK2, ls=(0, (3, 3)), lw=1, zorder=0)
    ax.set_xlim(0, 1.32)
    ax.set_xticks([0, 0.25, 0.5, 0.75, 1])
    ax.set_xticklabels(["start", "", "middle", "", "end"])
    ax.set_xlabel("time of the nonREM packet within the sleep period")
    ax.set_ylabel("packet rate / the sextile's mean in that period")
    ax.grid(axis="y", color=LINE, lw=0.6, zorder=0)
    fig.tight_layout()
    out = IMAGES / "sextiles.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print(f"wrote {out}")


if __name__ == "__main__":
    IMAGES.mkdir(exist_ok=True)
    s = json.loads((CACHE / "cells_summary.json").read_text())
    first_last_plot(s)
    sextiles_plot(s)
