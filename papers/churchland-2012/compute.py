"""Stream the J-array session of DANDI:000070 and cache what the figures need.

Uses reach.py from the Encore registry entry churchland-2012 (vendored here unchanged) so that
the trial selection, firing rates and jPCA are the same as in the Encore attempt
churchland-2012-01. Writes cache/churchland-2012/j_array.npz at the repository root.

Run from the repository root:  .venv/bin/python papers/churchland-2012/compute.py
"""

import time
from pathlib import Path

import numpy as np

import reach

SESSION = "J-array"
OUT = Path(__file__).resolve().parents[2] / "cache" / "churchland-2012" / "j_array.npz"
LONG_TIMES_MS = np.arange(-300, 401, 10)   # wider span projected onto the fitted plane (context only)


def main():
    t0 = time.time()
    path = reach.SESSIONS[SESSION]
    url = reach.asset_urls()[path]
    s = reach.load_session(path, url)
    print(f"loaded {path} in {time.time() - t0:.0f} s")

    tr = s["trials"]
    sel = np.where(reach.select_trials(tr))[0]
    align = tr.move_begins_time.values[sel]
    cond = tr.maze_condition.values[sel]
    labels, sums, n = reach.condition_counts(s, sel, align, cond)
    rates = reach.condition_rates(sums, n)                       # conditions x 1 ms bins x units
    res = reach.jpca(rates, n_planes=3)
    summ = reach.summary(res)
    print(f"{len(sel)} trials, {len(labels)} conditions, {rates.shape[2]} units")
    print({k: round(float(v), 3) for k, v in summ.items()})

    # the fitted plane applied to a wider span of times, for context around the analysed window
    tf = dict(res["transform"], times_ms=LONG_TIMES_MS)
    proj_long = reach.project(rates, dict(res, transform=tf), plane=0)

    kin = reach.condition_kinematics(s, sel, align, cond)
    assert np.array_equal(kin["labels"], labels)

    rate_times = np.arange(reach.WINDOW_MS[0], reach.WINDOW_MS[1], 10)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        OUT,
        condition=labels, n_trials=n,
        rate_times_ms=rate_times,
        rates=rates[:, rate_times - reach.WINDOW_MS[0], :].astype(np.float32),   # 10 ms samples
        unit_area=s["unit_area"],
        analysis_times_ms=reach.ANALYSIS_TIMES,
        planes=np.stack(res["planes"]).astype(np.float32),                     # plane x cond x time x 2
        plane_var=res["plane_var"], pc_var=res["pc_var"],
        long_times_ms=LONG_TIMES_MS, proj_long=proj_long.astype(np.float32),
        net_rotation=reach.net_rotation(res["planes"][0]),
        hand_times_ms=np.arange(reach.WINDOW_MS[0], reach.WINDOW_MS[1]),
        hand_pos_mm=(kin["pos"] * 1000).astype(np.float32),                     # cond x 1 ms x 2
        endpoint_mm=kin["endpoint"] * 1000,
        **{f"summary_{k}": v for k, v in summ.items()},
    )
    print(f"wrote {OUT} ({OUT.stat().st_size / 1e6:.1f} MB) in {time.time() - t0:.0f} s total")


if __name__ == "__main__":
    main()
