"""Per-cell firing rates across sleep, over every usable session of DANDI:000041.

Uses sleepstates.py from the Encore registry entry watson-2016-000041 (vendored here unchanged)
and replays the steps of the attempt's notebook (reproduce_watson_2016.ipynb, cells 1, 43, 46,
49 and 52) for the claims fig3-first-last-packet, fig3d-first-last-slope and
fig3b-sextiles-over-sleep. Only units and states are read (no LFP). Writes
cache/watson-2016/first_last.parquet, sextile_points.parquet, unit_sextiles.parquet and
cells_summary.json at the repository root.

Run from the repository root:  .venv/bin/python papers/watson-2016/compute_cells.py
"""

import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
import scipy.stats as st

import sleepstates as ss

OUT = Path(__file__).resolve().parents[2] / "cache" / "watson-2016"


def ols(x, y):
    res = st.linregress(x, y)
    t = st.t.ppf(0.975, len(x) - 2)
    return dict(slope=res.slope, lo=res.slope - t * res.stderr, hi=res.slope + t * res.stderr,
                r=res.rvalue, n=len(x))


def group_mean(rmat, mask):
    """Notebook cell 46: mean over the cells in the mask (cells silent throughout dropped),
    divided by its mean over the points."""
    sub = rmat[mask]
    sub = sub[np.nansum(sub, axis=1) > 0]
    if len(sub) == 0:
        return None
    m = np.nanmean(sub, axis=0)
    mu = np.nanmean(m)
    return m / mu if mu > 0 else None


def main():
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    items = [(p, u) for p, u in ss.asset_urls() if p not in ss.EXCLUDED]
    with ThreadPoolExecutor(8) as ex:
        sessions = list(ex.map(lambda it: ss.load_session(*it), items))
    print(f"loaded {len(sessions)} sessions in {time.time() - t0:.0f} s")
    edges, sext = ss.wake_sextiles(sessions)
    cyc = {s.path: ss.cycles(s) for s in sessions}

    # cell 49: each pE cell's rate in the first and the last NREM packet of each SLEEP period
    fl = []
    for s in sessions:
        for c, p_ in enumerate(cyc[s.path]):
            rr = np.arange(p_["first"], p_["last"] + 1)
            pk = rr[s.state[rr] == "NREM"]
            r1 = ss.rates(s.spikes, s.pe, s.starts[pk[0]], s.stops[pk[0]])
            r2 = ss.rates(s.spikes, s.pe, s.starts[pk[-1]], s.stops[pk[-1]])
            mid = (s.starts[pk[0]] + s.stops[pk[0]]) / 2
            for k, u in enumerate(s.pe):
                fl.append(dict(subject=s.subject, session=s.session_id, cycle=c, unit=int(u),
                               first=r1[k], last=r2[k], sextile=int(sext[s.path][1][k]),
                               first_half=ss.rates(s.spikes, [u], s.starts[pk[0]], mid)[0],
                               second_half=ss.rates(s.spikes, [u], mid, s.stops[pk[0]])[0]))
    fl = pd.DataFrame(fl)
    k2 = (fl["first"] > 0) & (fl["last"] > 0)
    k3 = (fl.first_half > 0) & (fl.second_half > 0)
    slope = ols(np.log10(fl["first"][k2]), np.log10(fl["last"][k2]))
    halves = ols(np.log10(fl.first_half[k3]), np.log10(fl.second_half[k3]))
    sd_ratio = float(np.std(np.log10(fl["last"][k2]), ddof=1) / np.std(np.log10(fl["first"][k2]), ddof=1))

    # cells 46 and 58, reading (a): each NREM packet's rate, normalized per sextile and cycle,
    # against the packet's time within SLEEP
    rows = []
    for s in sessions:
        g = sext[s.path][1]
        for c, p_ in enumerate(cyc[s.path]):
            rr = np.arange(p_["first"], p_["last"] + 1)
            pk = rr[s.state[rr] == "NREM"]
            x = ((s.starts[pk] + s.stops[pk]) / 2 - p_["start"]) / (p_["stop"] - p_["start"])
            rmat = np.array([[ss.counts(s.spikes[u], s.starts[i], s.stops[i]) / (s.stops[i] - s.starts[i])
                              for i in pk] for u in s.pe])
            for sx in range(1, 7):
                v = group_mean(rmat, g == sx)
                if v is None:
                    continue
                for xi, yi in zip(x, v):
                    rows.append(dict(session=s.session_id, cycle=c, sextile=sx, x=xi, y=yi))
    pts = pd.DataFrame(rows)
    sext_r = {}
    for sx in range(1, 7):
        d = pts[(pts.sextile == sx) & np.isfinite(pts.y)]
        r, p = st.pearsonr(d.x, d.y)
        sext_r[sx] = dict(r=float(r), p=float(p), n=len(d))

    units = pd.DataFrame([dict(session=s.session_id, unit=int(u), wake_rate=float(sext[s.path][0][k]),
                               sextile=int(sext[s.path][1][k]))
                          for s in sessions for k, u in enumerate(s.pe)])
    fl.to_parquet(OUT / "first_last.parquet")
    pts.to_parquet(OUT / "sextile_points.parquet")
    units.to_parquet(OUT / "unit_sextiles.parquet")
    summary = {
        "sessions": len(sessions), "cycles": int(fl.groupby(["session", "cycle"]).ngroups),
        "pairs": len(fl), "first_mean": float(fl["first"].mean()), "last_mean": float(fl["last"].mean()),
        "wilcoxon_p": float(st.wilcoxon(fl["first"], fl["last"]).pvalue),
        "slope_log10": slope, "slope_halves_log10": halves, "sd_ratio_log10": sd_ratio,
        "sextile_r": sext_r, "sextile_edges_hz": [float(e) for e in edges],
    }
    (OUT / "cells_summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    print(f"done in {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
