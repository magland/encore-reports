"""Interactive figure: jPCA on the J-array data next to jPCA on the attempt's controls.

Reads the caches written by compute.py. Each panel is the first jPCA plane fitted separately
to one population: the data, shuffle 2, the median run of shuffle 3, and the simulated
velocity-tuned population. Conditions keep the colors of the rotations figure.

Run from the repository root:  .venv/bin/python papers/churchland-2012/fig_controls.py [--upload]
"""

import sys
from pathlib import Path

import numpy as np
from figpack_experimental.views import LinkedTrajectories, TrajectoryPanel

from fig_rotations import condition_colors

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "cache" / "churchland-2012"
TITLE = "Churchland et al. 2012: jPCA on the data and on the controls (J-array)"


def main():
    d = np.load(CACHE / "j_array.npz")
    c = np.load(CACHE / "controls.npz")
    t = d["long_times_ms"]
    t0 = int(c["t0_ms"])

    pops = [  # (cache key, panel name)
        (None, "Data"),
        ("shuffle_2", "Shuffle 2"),
        ("shuffle_3", "Shuffle 3"),
        ("velocity_model", "Velocity model"),
    ]
    panels, rotations = [], []
    for key, name in pops:
        if key is None:
            proj, rot = d["proj_long"], d["net_rotation"]
            ratio, ccw = d["summary_r2_ratio_6d"], d["summary_frac_ccw"]
        else:
            proj, rot = c[f"{key}_proj_long"], c[f"{key}_net_rotation"]
            ratio, ccw = c[f"{key}_summary_r2_ratio_6d"], c[f"{key}_summary_frac_ccw"]
        n_ccw = int(round(float(ccw) * len(rot)))
        panels.append(TrajectoryPanel(
            data=proj,
            title=f"{name}: fit ratio {float(ratio):.2f}, {n_ccw}/{len(rot)} counter-clockwise",
            x_label="jPC1 (a.u.)", y_label="jPC2 (a.u.)"))
        rotations.append(np.degrees(rot))

    labels = [f"condition {cond}: net rotation " + ", ".join(
                  f"{name.lower()} {r[i]:+.0f}" for (_, name), r in zip(pops, rotations)) + " deg"
              for i, cond in enumerate(d["condition"])]

    r2 = {k: float(c[f"{k}_summary_r2_skew"]) / float(d["summary_r2_skew"])
          for k in ("shuffle_2", "shuffle_3", "velocity_model")}
    description = f"""\
Each panel is the first jPCA plane fitted separately to one population of the J-array session
(DANDI:000070), with each of the 108 reach conditions in the same color in every panel (the
colors of the rotations figure). The fit ratio in each title is R2 of the rotational dynamics
over R2 of unconstrained linear dynamics, in the 6-D PC space.

- Data: the condition-averaged rates.
- Shuffle 2: activity after {t0} ms (50 ms after the median go cue) inverted about its value
  at that time, for every condition and unit. Its rotational fit (R2) is
  {100 * r2['shuffle_2']:.0f}% of the data's.
- Shuffle 3: activity after {t0} ms taken from another condition and joined to this one's
  value at that time; the run with the median rotational fit of the attempt's 20 runs,
  at {100 * r2['shuffle_3']:.0f}% of the data's.
- Velocity model: simulated units tuned to hand velocity and speed, with preparatory activity
  tuned to the reach endpoint, leading the hand by 100 ms; its rotational fit is
  {100 * r2['velocity_model']:.0f}% of the data's.

jPCA orients every plane so that the net rotation is counter-clockwise, which is why most
conditions turn that way in every panel. The plane is fitted on -50 to +150 ms (the band on
the time slider); other times are projected onto it for context. The controls and their
random seeds are those of the Encore attempt churchland-2012-01.
"""

    view = LinkedTrajectories(
        times=t,
        panels=panels,
        item_labels=labels,
        item_colors=condition_colors(d),
        time_label="ms from movement onset",
        tail_length=200,
        initial_time=150,
        highlight_interval=(-50, 150),
        num_columns=2,
    )
    if "--upload" in sys.argv:
        url = view.show(title=TITLE, description=description, upload=True, open_in_browser=False,
                        wait_for_input=False)
        print(url)
    else:
        out = CACHE / "figures" / "controls"
        view.save(str(out), title=TITLE, description=description)
        print(f"saved {out}")


if __name__ == "__main__":
    main()
