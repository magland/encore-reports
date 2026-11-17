"""Static plots for the report, written to images/ (run compute.py first).

- angles.png: the distribution of the angle between the neural state and its derivative in
  the first jPCA plane, for the J-array data, shuffles 2 and 3 and the velocity model (as in
  the paper's Figure 6a).
- spike_index.png: the stored spike times of units 0 and 1 of the J-array file in file order,
  with the stored and the true end of unit 0 (the spike_times_index fault).

Run from the repository root:  .venv/bin/python papers/churchland-2012/plot_static.py
"""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

import reach

HERE = Path(__file__).resolve().parent
CACHE = HERE.parents[1] / "cache" / "churchland-2012"
IMAGES = HERE / "images"

BLUE, ORANGE = "#2a78d6", "#eb6834"          # categorical slots 1 and 2 (validated pair)
GRAY = "#9a9893"                             # controls
INK, INK2, LINE = "#0b0b0b", "#52514e", "#d9d8d4"

plt.rcParams.update({
    "font.family": "sans-serif", "font.size": 10, "text.color": INK, "axes.labelcolor": INK2,
    "axes.edgecolor": LINE, "xtick.color": INK2, "ytick.color": INK2,
    "axes.spines.top": False, "axes.spines.right": False, "figure.facecolor": "white",
    "axes.titlesize": 11, "axes.titleweight": "bold",
})


def angles_plot():
    d = np.load(CACHE / "j_array.npz")
    c = np.load(CACHE / "controls.npz")
    pops = [("Data", d["planes"][0], BLUE),
            ("Shuffle 2", c["shuffle_2_plane"], GRAY),
            ("Shuffle 3", c["shuffle_3_plane"], GRAY),
            ("Velocity model", c["velocity_model_plane"], GRAY)]
    edges = np.linspace(-1, 1, 37)                  # 36 bins over -pi to pi, as in the attempt
    fig, axes = plt.subplots(1, 4, figsize=(12, 3.1), sharey=True)
    peaks = {}
    for ax, (name, plane, color) in zip(axes, pops):
        ang = reach.state_angles(plane) / np.pi
        h, _ = np.histogram(ang, bins=edges)
        frac = h / h.sum()
        peak = reach.angle_peak(ang * np.pi) / np.pi
        peaks[name] = peak
        ax.bar(edges[:-1], frac, width=np.diff(edges) * 0.85, align="edge", color=color, zorder=2)
        if name == "Velocity model":
            ax.axvspan(0, 0.25, color=LINE, alpha=0.6, zorder=1, lw=0)
            ax.text(0.03, 0.62, "expected\nfor the\nmodel", transform=ax.get_xaxis_transform(),
                    va="top", ha="left", fontsize=8.5, color=INK2)
        ax.axvline(0.5, color=INK2, ls=(0, (3, 3)), lw=1, zorder=3)
        # a triangle over the tallest bar, and its value in the corner
        ax.plot(peak, frac.max() + 0.006, marker="v", ms=7, color=INK, zorder=4)
        ax.text(0.02, 0.97, f"peak {peak:.2f}π", transform=ax.transAxes, ha="left", va="top",
                fontsize=9.5, color=INK)
        ax.set_title(name, loc="left")
        ax.set_xlim(-1, 1)
        ax.set_xticks([-1, -0.5, 0, 0.5, 1])
        ax.set_xticklabels(["-π", "-π/2", "0", "π/2", "π"])
        ax.grid(axis="y", color=LINE, lw=0.6, zorder=0)
    axes[0].set_ylabel("fraction of samples")
    fig.supxlabel("angle between the state and its derivative in the first jPCA plane "
                  "(all conditions and times, -50 to +150 ms)", fontsize=10, color=INK2)
    axes[0].set_ylim(0, max(a.get_ylim()[1] for a in axes) * 1.12)
    fig.tight_layout()
    out = IMAGES / "angles.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print(f"wrote {out}; peaks / pi: { {k: round(v, 3) for k, v in peaks.items()} }")


def spike_index_plot():
    s = np.load(CACHE / "spike_index.npz")
    t = s["times"]
    stored_end, true_end = int(s["index_stored"][0]), int(s["index_fixed"][0])
    pos = np.arange(len(t))
    step = 25                                        # every 25th spike is enough to draw the lines
    fig, ax = plt.subplots(figsize=(9, 3.8))
    ax.axvspan(stored_end, true_end, color=LINE, alpha=0.5, lw=0, zorder=1)
    for a, b, color, label in ((0, true_end, BLUE, "unit 0 (corrected index)"),
                               (true_end, len(t), ORANGE, "unit 1 (corrected index)")):
        ax.plot(pos[a:b:step], t[a:b:step], color=color, lw=1.6, label=label, zorder=2)
    ax.axvline(stored_end, color=INK2, ls=(0, (3, 3)), lw=1, zorder=3)
    ax.axvline(true_end, color=INK, lw=1, zorder=3)
    top = t.max()
    ax.text(stored_end, top * 1.06, f"  stored end of unit 0\n  ({stored_end:,})", fontsize=8.5,
            color=INK2, va="bottom", ha="left")
    ax.text(true_end, top * 1.06, f"  true end of unit 0\n  ({true_end:,} = {stored_end:,} + "
            f"{int(s['wraps'])} × 65,536)", fontsize=8.5, color=INK, va="bottom", ha="left")
    ax.text((stored_end + true_end) / 2, top * 0.5, "unit 0's spikes that\nare read as unit 1",
            fontsize=8.5, color=INK2, ha="center", va="center")
    ax.set_ylim(0, top * 1.3)
    ax.set_xlim(0, len(t))
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{int(v):,}"))
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{int(v):,}"))
    ax.set_xlabel("position in units/spike_times (spikes of units 0 and 1, in file order)")
    ax.set_ylabel("spike time (s)")
    ax.legend(loc="lower right", frameon=False)
    ax.grid(axis="y", color=LINE, lw=0.6, zorder=0)
    fig.tight_layout()
    out = IMAGES / "spike_index.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print(f"wrote {out}")


if __name__ == "__main__":
    IMAGES.mkdir(exist_ok=True)
    angles_plot()
    spike_index_plot()
