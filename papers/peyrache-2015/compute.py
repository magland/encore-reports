"""Stream one session of DANDI:000056 and compute what the Peyrache 2015 report shows.

Session Mouse28-140313: 15 thalamic (ADn) and 9 post-subicular (PoS) head-direction cells, 38 min
of waking in the open field, 3.1 h of slow-wave sleep and 23 min of REM sleep. The loading code,
the head-direction cell criteria, the tuning curves and the Bayesian decoder are those of the Encore
attempt peyrache-2015-02 (hd.py, copied unchanged). Writes cache/peyrache-2015/session.npz and
cache/peyrache-2015/summary.json at the repository root.

Run from the repository root:  .venv/bin/python papers/peyrache-2015/compute.py
"""

import json
from pathlib import Path

import numpy as np

import hd

SESSION = "sub-Mouse28/sub-Mouse28_ses-Mouse28-140313_behavior+ecephys.nwb"
OUT = Path(__file__).resolve().parents[2] / "cache" / "peyrache-2015"


def decode_states(s, units, tcs):
    """Decoded head direction (posterior maximum) from the given cells in every state, in 10 ms
    bins with the attempt's state-dependent smoothing (300 ms in waking and REM, 50 ms in SWS)."""
    TC = np.array([tcs[u] for u in units])
    out = {}
    for k in hd.STATES:
        iv = hd.state_iv(s, k)
        C = hd.bin_matrix([s["spikes"][u] for u in units], iv, hd.DEC_BIN)
        _, cen = hd.bin_counts(np.zeros(0), iv, hd.DEC_BIN)
        out[k] = (cen, hd.bayes_decode(hd.gauss_smooth_counts(C, hd.DEC_SMOOTH[k]), TC, hd.DEC_BIN))
    return out


POST_BINS = 60       # 6 degree bins for the posterior shown in the figure
POST_STEP = 0.05     # 50 ms


def posterior_timeline(s, units, tcs, t_end):
    """Posterior over head direction from the given cells on one uniform 50 ms grid covering the
    whole session, for the figure. The decoding is the attempt's (10 ms counts, smoothed 300 ms in
    waking and REM and 50 ms in SWS, flat prior, waking tuning curves); here the tuning curves are
    averaged into 6 degree bins and the 10 ms posteriors are averaged in groups of five. Bins outside
    the scored states are zero."""
    n10 = int(t_end / hd.DEC_BIN)
    n10 -= n10 % 5
    edges = np.arange(n10 + 1) * hd.DEC_BIN
    C = np.array([np.histogram(s["spikes"][u], edges)[0] for u in units], dtype=float)
    cen = edges[:-1] + hd.DEC_BIN / 2
    TC = np.array([tcs[u] for u in units]).reshape(len(units), POST_BINS, -1).mean(axis=2)
    TC = np.maximum(TC, 1e-3)
    logt, rate_sum = np.log(TC), TC.sum(0) * hd.DEC_BIN
    state = np.full(n10, "", dtype=object)
    for k in hd.STATES:
        state[hd.in_iv(cen, hd.state_iv(s, k))] = k
    smooth = {k: hd.gauss_smooth_counts(C, sd) for k, sd in (("fast", 0.05), ("slow", 0.3))}
    out = np.zeros((n10 // 5, POST_BINS), dtype=np.float32)
    step = 100000
    for a in range(0, n10, step):
        b = min(a + step, n10)
        sl = state[a:b]
        Cs = np.where(sl == "SWS", smooth["fast"][:, a:b], smooth["slow"][:, a:b])
        ll = Cs.T @ logt - rate_sum
        p = np.exp(ll - ll.max(axis=1, keepdims=True))
        p /= p.sum(axis=1, keepdims=True)
        p[sl == ""] = 0
        out[a // 5:b // 5] = p.reshape(-1, 5, POST_BINS).mean(axis=1)
    return out


def main():
    path, aid = next((p, a) for p, a, _ in hd.list_assets() if p == SESSION)
    s = hd.load_session(aid, path)
    t, a = hd.wake_hd(s)
    W = s["states"]["wake"]
    occ = hd.occupancy(a)
    units = np.where(np.isin(s["region"], [hd.ADN, hd.POS]))[0]
    tcs, cells = {}, []
    for u in units:
        sh = hd.spike_hd(hd.restrict(s["spikes"][u], W), t, a, s["hd_rate"])
        tcs[u] = hd.tuning_curve(sh, occ, 1 / s["hd_rate"])
        f = hd.vm_fit_a(tcs[u], len(sh))
        cells.append(dict(unit=int(u), region="ADn" if s["region"][u] == hd.ADN else "PoS",
                          hd=hd.is_hd(f), pref=float(f["pref"]), kappa=float(f["kappa"]), peak=float(f["peak"]),
                          **{f"rate_{k}": len(hd.restrict(s["spikes"][u], hd.state_iv(s, k))) / hd.total(hd.state_iv(s, k))
                             for k in hd.STATES}))
    adn = [c["unit"] for c in cells if c["hd"] and c["region"] == "ADn"]
    pos = [c["unit"] for c in cells if c["hd"] and c["region"] == "PoS"]
    print(f"{len(adn)} ADn and {len(pos)} PoS HD cells")

    # decoding from the ADn HD cells in every state; the waking error against the tracked head
    dec = decode_states(s, adn, tcs)
    cen, ang = dec["wake"]
    th = hd._hd_at(s, cen)
    ok = np.isfinite(th)
    err = np.degrees(np.abs(hd.circ_diff(ang[ok], th[ok])))

    # tuning curves of the PoS HD cells measured against the direction decoded from ADn, per state
    # (fig5b of the paper), correlated with their waking tuning curves against the tracked head
    tc_dec, r_dec = {}, {}
    for k, (cen_k, ang_k) in dec.items():
        T = hd.bin_matrix([s["spikes"][u] for u in pos], hd.state_iv(s, k), hd.DEC_BIN)
        ab = np.minimum((ang_k / (2 * np.pi) * hd.NBINS).astype(int), hd.NBINS - 1)
        tc_dec[k] = hd._tc_from_bins(T, ab, hd.DEC_BIN)
        r_dec[k] = [float(np.corrcoef(tc_dec[k][i], tcs[u])[0, 1]) for i, u in enumerate(pos)]

    # pair correlations of all HD cells per state (Fig. 3a bins: 300 ms in waking and REM, 50 ms in SWS)
    hdu = adn + pos
    cc = {}
    for k in hd.STATES:
        M = hd.bin_matrix([s["spikes"][u] for u in hdu], hd.state_iv(s, k), hd.CORR_BIN[k])
        cc[k] = np.corrcoef(M)[np.triu_indices(len(hdu), 1)]

    t_end = float(max(s["hd_t"][-1], max(x[-1] for x in s["spikes"] if len(x))))
    post = posterior_timeline(s, adn, tcs, t_end)

    OUT.mkdir(parents=True, exist_ok=True)
    np.save(OUT / "posterior.npy", post)
    spikes = [s["spikes"][c["unit"]] for c in cells]
    np.savez_compressed(
        OUT / "session.npz", session=s["session"], subject=s["subject"],
        unit=np.array([c["unit"] for c in cells]), region=np.array([c["region"] for c in cells]),
        is_hd=np.array([c["hd"] for c in cells]), pref=np.array([c["pref"] for c in cells]),
        tuning=np.array([tcs[c["unit"]] for c in cells]),
        spike_times=np.concatenate(spikes), spike_index=np.cumsum([len(x) for x in spikes]),
        hd_t=s["hd_t"], hd=s["hd"], hd_rate=s["hd_rate"],
        **{f"state_{k}": hd.state_iv(s, k) for k in hd.STATES},
        **{f"dec_t_{k}": dec[k][0] for k in hd.STATES}, **{f"dec_{k}": dec[k][1] for k in hd.STATES},
        dec_units=np.array(adn), pos_units=np.array(pos),
        **{f"tc_dec_{k}": tc_dec[k] for k in hd.STATES},
        hd_units=np.array(hdu), **{f"cc_{k}": cc[k] for k in hd.STATES},
    )
    rates = {k: [c[f"rate_{k}"] for c in cells if c["hd"]] for k in hd.STATES}
    summary = dict(
        session=s["session"], n_adn_hd=len(adn), n_pos_hd=len(pos),
        minutes={k: hd.total(hd.state_iv(s, k)) / 60 for k in hd.STATES},
        wake_decoding_error_median_deg=float(np.median(err)),
        pos_tc_r_median={k: float(np.median(v)) for k, v in r_dec.items()},
        rate_r={k: float(np.corrcoef(rates["wake"], rates[k])[0, 1]) for k in ("SWS", "REM")},
        pair_r={k: float(np.corrcoef(cc["wake"], cc[k])[0, 1]) for k in ("SWS", "REM")},
        n_pairs=int(len(cc["wake"])),
    )
    (OUT / "summary.json").write_text(json.dumps(summary, indent=1))
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
