"""Interactive figure: the jPCA rotations of J-array next to the hand paths of each condition.

Reads the cache written by compute.py. By default saves the figure to
cache/churchland-2012/figures/rotations/ for a local look; with --upload, uploads it to the
figpack cloud (needs FIGPACK_API_KEY) and prints the URL.

Run from the repository root:  .venv/bin/python papers/churchland-2012/fig_rotations.py [--upload]
"""

import sys
from pathlib import Path

import matplotlib
import numpy as np
from figpack_experimental.views import LinkedTrajectories, TrajectoryPanel

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "cache" / "churchland-2012"
TITLE = "Churchland et al. 2012: rotations in the jPCA plane and the hand paths (J-array)"
DESCRIPTION = """\
Each of the 108 reach conditions of the J-array session (DANDI:000070) is one curve, drawn in the
same color in both panels. Left: condition-averaged population activity projected onto the first
jPCA plane. Right: the condition's mean hand path. Colors follow the preparatory state along jPC1
at -50 ms, as in the paper's Figure 3. The plane is fitted on -50 to +150 ms from movement onset
(the band on the time slider); times outside that window are projected onto the same plane for
context. Computed with the code of the Encore attempt churchland-2012-01.
"""


def darken(rgba, max_lightness=0.5):
    """Cap the HLS lightness so the pale middle of the colormap stays visible on white."""
    import colorsys
    h, l, s = colorsys.rgb_to_hls(*rgba[:3])
    return matplotlib.colors.to_hex(colorsys.hls_to_rgb(h, min(l, max_lightness), s))


def condition_colors(d):
    """One color per condition, by the preparatory state along jPC1 at -50 ms (paper's Fig. 3)."""
    x0 = d["planes"][0][:, 0, 0]
    cmap = matplotlib.colormaps["RdYlGn_r"]
    return [darken(cmap(v)) for v in (x0 - x0.min()) / np.ptp(x0)]


def main():
    d = np.load(CACHE / "j_array.npz")
    t = d["long_times_ms"]
    proj = d["proj_long"]                                    # cond x time x 2
    hand_idx = t - d["hand_times_ms"][0]
    hand = d["hand_pos_mm"][:, hand_idx, :]                  # cond x time x 2

    colors = condition_colors(d)
    rot = np.degrees(d["net_rotation"])
    labels = [f"condition {c} ({n} trials), net rotation {r:+.0f} deg"
              for c, n, r in zip(d["condition"], d["n_trials"], rot)]

    view = LinkedTrajectories(
        times=t,
        panels=[
            TrajectoryPanel(data=proj, title="Neural state, jPCA plane 1", x_label="jPC1 (a.u.)",
                            y_label="jPC2 (a.u.)"),
            TrajectoryPanel(data=hand, title="Mean hand path", x_label="x (mm)", y_label="y (mm)"),
        ],
        item_labels=labels,
        item_colors=colors,
        time_label="ms from movement onset",
        tail_length=200,
        initial_time=150,
        highlight_interval=(-50, 150),
    )
    if "--upload" in sys.argv:
        url = view.show(title=TITLE, description=DESCRIPTION, upload=True, open_in_browser=False,
                        wait_for_input=False)
        print(url)
    else:
        out = CACHE / "figures" / "rotations"
        view.save(str(out), title=TITLE, description=DESCRIPTION)
        print(f"saved {out}")


if __name__ == "__main__":
    main()
