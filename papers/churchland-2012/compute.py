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
    print(f"wrote {OUT} ({OUT.stat().st_size / 1e6:.1f} MB) in {time.time() - t0:.0f} s")

    # the spike_times_index fault: the stored spike times of units 0 and 1, in file order, with
    # the stored and corrected index (reach.fix_first_index corrects only the first entry)
    assert s["index_stored"][1] == s["index_fixed"][1]
    np.savez_compressed(
        OUT.parent / "spike_index.npz",
        times=np.concatenate([s["spikes"][0], s["spikes"][1]]),
        index_stored=s["index_stored"][:2], index_fixed=s["index_fixed"][:2],
        wraps=s["index_wraps"],
        session_range=[tr.start_time.min(), tr.stop_time.max()],
    )

    compute_controls(s, tr, sel, align, rates, n, kin, res)
    print(f"done in {time.time() - t0:.0f} s total")


def compute_controls(s, tr, sel, align, rates, n, kin, res):
    """The attempt's shuffle 2, its median shuffle 3 run and its velocity model, for J-array.

    The attempt drew its controls from fixed seeds, J-array first (notebook cells 20 and 63),
    so the same runs are replayed here: shuffle seed 7012 is consumed by the 20 runs of
    shuffle 1, shuffle 2 uses no random numbers, then the 20 runs of shuffle 3 follow; the
    velocity model with a 100 ms lead is the first draw from seed 7016.
    """
    go_rel = np.median((tr.go_cue_time.values - tr.move_begins_time.values)[sel]) * 1000
    t0_ms = int(round(go_rel + 50))
    t0_index = t0_ms - reach.WINDOW_MS[0]
    rng = np.random.default_rng(7012)
    for _ in range(20):                                          # shuffle 1 draws, not needed here
        rng.random((rates.shape[0], 1, rates.shape[2]))
    sources = {"shuffle 2": reach.shuffle_rates(rates, t0_index, 2, rng)}
    states, r2s = [], []
    for _ in range(20):
        states.append(rng.bit_generator.state)                    # to replay the chosen run
        r2s.append(reach.jpca(reach.shuffle_rates(rates, t0_index, 3, rng))["r2_skew"])
    r2s = np.array(r2s)
    median_run = int(np.argsort(r2s)[len(r2s) // 2])
    replay = np.random.default_rng()
    replay.bit_generator.state = states[median_run]
    sources["shuffle 3"] = reach.shuffle_rates(rates, t0_index, 3, replay)
    sources["velocity model"] = reach.simulate_population(
        "velocity", kin, rates, n, np.random.default_rng(7016), lead_ms=100)

    out = {"t0_ms": t0_ms, "shuffle3_run": median_run,
           "shuffle3_r2_skew_all": r2s, "data_r2_skew": res["r2_skew"]}
    for name, src in sources.items():
        r = reach.jpca(src)
        key = name.replace(" ", "_")
        tf = dict(r["transform"], times_ms=LONG_TIMES_MS)
        out[f"{key}_proj_long"] = reach.project(src, dict(r, transform=tf), plane=0).astype(np.float32)
        out[f"{key}_plane"] = r["planes"][0].astype(np.float32)
        out[f"{key}_net_rotation"] = reach.net_rotation(r["planes"][0])
        for k, v in reach.summary(r).items():
            out[f"{key}_summary_{k}"] = v
        print(name, {k: round(float(v), 3) for k, v in reach.summary(r).items()
                     if k in ("r2_skew", "r2_ratio_6d", "angle_peak", "frac_ccw", "plane_var")})
    print(f"dividing point {t0_ms} ms; shuffle 3 median run {median_run}; "
          f"R2(M_skew) data {res['r2_skew']:.3f}, shuffle 3 runs {np.median(r2s):.3f} median")
    np.savez_compressed(OUT.parent / "controls.npz", **out)
    print(f"wrote {OUT.parent / 'controls.npz'}")


if __name__ == "__main__":
    main()
