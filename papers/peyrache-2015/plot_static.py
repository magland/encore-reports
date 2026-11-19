"""Static plots for the Peyrache 2015 report, written to images/ (run compute.py first).

- tuning.png: the waking tuning curve of each of the 24 head-direction cells of the session, as polar
  plots ordered by preferred direction.
- bump.png: the spikes of the 24 cells, each drawn at its preferred direction, with the direction
  decoded from the 15 thalamic cells, in a window of waking, of REM sleep and of slow-wave sleep.
- preserved.png: firing rates and pair correlations in waking against the same in sleep.
- sleep_tuning.png: the tuning curves of the 9 post-subicular cells measured against the direction
  decoded from the thalamic cells, in REM and slow-wave sleep, against their waking tuning curves.

Run from the repository root:  .venv/bin/python papers/peyrache-2015/plot_static.py
"""

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import hd  # noqa: E402

CACHE = HERE.parents[1] / "cache" / "peyrache-2015"
IMAGES = HERE / "images"

BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"   # categorical slots 1, 2, 3 (validated)
WAKE_GRAY = "#9a9893"
INK, INK2, LINE = "#0b0b0b", "#52514e", "#d9d8d4"
STATE_COLOR = {"wake": WAKE_GRAY, "SWS": BLUE, "REM": ORANGE}
STATE_NAME = {"wake": "waking", "SWS": "slow-wave sleep", "REM": "REM sleep"}

plt.rcParams.update({
    "font.family": "sans-serif", "font.size": 10, "text.color": INK, "axes.labelcolor": INK2,
    "axes.edgecolor": LINE, "xtick.color": INK2, "ytick.color": INK2,
    "axes.spines.top": False, "axes.spines.right": False, "figure.facecolor": "white",
    "axes.titlesize": 11, "axes.titleweight": "bold",
})


def load():
    d = dict(np.load(CACHE / "session.npz"))
    d["spikes"] = np.split(d["spike_times"], d["spike_index"][:-1])
    d["hdi"] = np.where(d["is_hd"])[0]
    return d


def wrapped(t, a_deg):
    """Break a line where the angle wraps around, so that no line crosses the plot."""
    t, a = np.asarray(t, float), np.asarray(a_deg, float)
    jump = np.abs(np.diff(a)) > 180
    gaps = np.r_[False, jump] | np.r_[False, np.diff(t) > 0.1]
    return np.where(gaps, np.nan, t), a


def coverage(a, t0, t1, t):
    """Fraction of 10 degree bins visited by the angle a(t) between t0 and t1."""
    m = (t >= t0) & (t < t1) & np.isfinite(a)
    return len(np.unique((a[m] // np.radians(10)).astype(int))) / 36 if m.any() else 0


def pick_window(iv, t, a, dur, step):
    """The window of `dur` s inside one interval of iv where a(t) covers the most directions."""
    best, out = -1, None
    for s0, s1 in iv:
        for w0 in np.arange(s0, s1 - dur, step):
            c = coverage(a, w0, w0 + dur, t)
            if c > best:
                best, out = c, w0
    return out


def tuning_plot(d):
    idx = d["hdi"][np.argsort(d["pref"][d["hdi"]])]
    fig, axes = plt.subplots(3, 8, figsize=(12, 5.2), subplot_kw={"projection": "polar"})
    for ax, i in zip(axes.flat, idx):
        tc = d["tuning"][i]
        th = np.r_[hd.ANG, hd.ANG[0]]
        r = np.r_[tc, tc[0]] / tc.max()
        ax.fill(th, r, color=INK2, alpha=0.15, lw=0)
        ax.plot(th, r, color=INK, lw=1.4)
        ax.set_theta_zero_location("E")
        ax.set_ylim(0, 1.05)
        ax.set_yticks([])
        ax.set_xticks(np.radians([0, 90, 180, 270]))
        ax.set_xticklabels(["0°", "90°", "180°", "270°"], fontsize=7, color=INK2)
        ax.grid(color=LINE, lw=0.6)
        ax.spines["polar"].set_color(LINE)
        ax.set_title(f"{d['region'][i]}, peak {tc.max():.0f} Hz", fontsize=8.5, fontweight="normal",
                     color=INK2, pad=10)
    fig.tight_layout()
    save(fig, "tuning.png")


def bump_plot(d):
    wake = d["state_wake"]
    hd_t, hd_a = d["hd_t"], d["hd"]
    windows = [
        ("wake", pick_window(wake, hd_t, hd_a, 30, 5), 30),
        ("REM", pick_window(d["state_REM"], d["dec_t_REM"], d["dec_REM"], 30, 5), 30),
        ("SWS", pick_window(d["state_SWS"], d["dec_t_SWS"], d["dec_SWS"], 3, 1), 3),
    ]
    fig, axes = plt.subplots(3, 1, figsize=(11, 9.6))
    for ax, (k, t0, dur) in zip(axes, windows):
        for i in d["hdi"]:
            sp = d["spikes"][i]
            x = sp[(sp >= t0) & (sp < t0 + dur)] - t0
            ax.plot(x, np.full(len(x), np.degrees(d["pref"][i])), "|", color=INK2, ms=7, mew=0.9, alpha=0.8)
        dt, da = d[f"dec_t_{k}"], d[f"dec_{k}"]
        m = (dt >= t0) & (dt < t0 + dur)
        ax.plot(*wrapped(dt[m] - t0, np.degrees(da[m])), color=AQUA, lw=2.4, label="decoded from the 15 thalamic cells")
        if k == "wake":
            m = (hd_t >= t0) & (hd_t < t0 + dur)
            ax.plot(*wrapped(hd_t[m] - t0, np.degrees(hd_a[m])), color=INK, lw=1.6, label="head direction (camera)")
        ax.set_ylim(-5, 365)
        ax.set_yticks([0, 90, 180, 270, 360])
        ax.set_xlim(0, dur)
        ax.set_ylabel("direction (°)")
        ax.set_title(f"{STATE_NAME[k][0].upper() + STATE_NAME[k][1:]}, {dur} s from {t0 / 60:.1f} min into the recording",
                     loc="left")
        ax.grid(axis="y", color=LINE, lw=0.6)
    axes[-1].set_xlabel("time (s)")
    handles, labels = axes[0].get_legend_handles_labels()
    tick = plt.Line2D([], [], color=INK2, marker="|", ls="", ms=9, mew=1.2)
    fig.legend([tick] + handles, ["spike of a cell, drawn at its preferred direction"] + labels, loc="upper center",
               ncol=3, frameon=False, fontsize=9.5)
    fig.tight_layout(rect=(0, 0, 1, 0.965))
    save(fig, "bump.png")
    return windows


def preserved_plot(d, s):
    hdi = d["hdi"]
    rates = {k: np.array([len(hd.restrict(d["spikes"][i], d[f"state_{k}"])) / hd.total(d[f"state_{k}"]) for i in hdi])
             for k in ("wake", "SWS", "REM")}
    fig, axes = plt.subplots(1, 3, figsize=(12, 4.2))
    ax = axes[0]
    lo, hi = 0.05, 100
    for k in ("SWS", "REM"):
        ax.scatter(rates["wake"], rates[k], s=22, color=STATE_COLOR[k], alpha=0.85, lw=0,
                   label=f"{STATE_NAME[k]}, r = {s['rate_r'][k]:.2f}")
    ax.plot([lo, hi], [lo, hi], color=INK2, ls=(0, (3, 3)), lw=1)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlim(lo, hi)
    ax.set_ylim(lo, hi)
    ax.set_aspect("equal")
    ax.set_xlabel("rate in waking (Hz)")
    ax.set_ylabel("rate in sleep (Hz)")
    ax.set_title(f"Firing rates, {len(hdi)} cells", loc="left")
    ax.legend(loc="upper left", fontsize=8.5, frameon=False)
    allc = np.concatenate([d[f"cc_{k}"] for k in ("wake", "SWS", "REM")])
    clo, chi = np.floor(allc.min() * 10) / 10, np.ceil(allc.max() * 10) / 10
    for ax, k in zip(axes[1:], ("SWS", "REM")):
        ax.scatter(d["cc_wake"], d[f"cc_{k}"], s=10, color=STATE_COLOR[k], alpha=0.6, lw=0)
        ax.plot([clo, chi], [clo, chi], color=INK2, ls=(0, (3, 3)), lw=1)
        ax.set_xlim(clo, chi)
        ax.set_ylim(clo, chi)
        ax.set_aspect("equal")
        ax.set_xlabel("correlation in waking")
        ax.set_ylabel(f"correlation in {STATE_NAME[k]}")
        ax.set_title(f"Pair correlations, {STATE_NAME[k]}", loc="left")
        ax.text(0.04, 0.96, f"r = {s['pair_r'][k]:.2f}, {s['n_pairs']} pairs", transform=ax.transAxes,
                va="top", fontsize=9)
    for ax in axes:
        ax.grid(color=LINE, lw=0.5)
    fig.tight_layout()
    save(fig, "preserved.png")


def sleep_tuning_plot(d, s):
    pos = list(d["pos_units"])
    unit_index = {int(u): i for i, u in enumerate(d["unit"])}
    order = sorted(range(len(pos)), key=lambda j: d["pref"][unit_index[int(pos[j])]])
    fig, axes = plt.subplots(3, 3, figsize=(11, 7.6), sharex=True)
    x = np.degrees(hd.ANG)
    for ax, j in zip(axes.flat, order):
        i = unit_index[int(pos[j])]
        lines = [("wake", d["tuning"][i])] + [(k, d[f"tc_dec_{k}"][j]) for k in ("REM", "SWS")]
        for k, tc in lines:
            ax.plot(x, tc / tc.max(), color=STATE_COLOR[k], lw=2.6 if k == "wake" else 1.6,
                    label={"wake": "waking, against head direction"}.get(k, f"{STATE_NAME[k]}, against decoded direction"))
        r = {k: np.corrcoef(d[f"tc_dec_{k}"][j], d["tuning"][i])[0, 1] for k in ("REM", "SWS")}
        ax.set_title(f"PoS cell {int(pos[j])}", loc="left", fontsize=10)
        ax.set_title(f"r = {r['REM']:.2f} REM, {r['SWS']:.2f} SWS", loc="right", fontsize=9,
                     fontweight="normal", color=INK2)
        ax.set_xlim(0, 360)
        ax.set_xticks([0, 90, 180, 270, 360])
        ax.set_ylim(0, 1.08)
        ax.grid(color=LINE, lw=0.5)
    for ax in axes[-1]:
        ax.set_xlabel("direction (°)")
    for ax in axes[:, 0]:
        ax.set_ylabel("rate / peak rate")
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=3, frameon=False, fontsize=9.5)
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    save(fig, "sleep_tuning.png")


def save(fig, name):
    out = IMAGES / name
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print(f"wrote {out}")


if __name__ == "__main__":
    IMAGES.mkdir(exist_ok=True)
    s = json.loads((CACHE / "summary.json").read_text())
    d = load()
    tuning_plot(d)
    for k, t0, dur in bump_plot(d):
        print(f"bump window {k}: {t0:.1f} s to {t0 + dur:.1f} s")
    preserved_plot(d, s)
    sleep_tuning_plot(d, s)
