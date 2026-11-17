"""Stream DANDI:000045 and cache what the IBL 2021 figures need.

Uses ibl_behavior.py from the Encore registry entry ibl-2021 (vendored here unchanged) and
replays the selection and proficiency steps of the attempt's notebook (cells 3, 5, 9, 10, 39
and 64 of reproduce_ibl_2021.ipynb), under the main reading of basic task proficiency (P1).
Writes cache/ibl-2021/*.parquet and summary.json at the repository root.

Run from the repository root:  .venv/bin/python papers/ibl-2021/compute.py
"""

import hashlib
import json
import os
import time
from pathlib import Path

for v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(v, "1")

import numpy as np
import pandas as pd

import ibl_behavior as ib

OUT = Path(__file__).resolve().parents[2] / "cache" / "ibl-2021"


def main():
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)

    # cell 3: every file of the pinned version
    assets = ib.list_assets()
    sessions = ib.read_all(assets.asset_id.tolist())
    sessions = [s for s in sessions if "error" not in s]
    S = ib.session_table(sessions)
    T = ib.trials_frame(sessions)
    print(f"loaded {len(sessions)} sessions in {(time.time() - t0) / 60:.1f} min")

    # cell 5: recordings deposited more than once
    key = {}
    for s in sessions:
        if s.get("choice") is None or len(s["choice"]) < 20:
            continue
        h = hashlib.md5(np.ascontiguousarray(s["choice"]).tobytes()
                        + np.ascontiguousarray(s["contrastLeft"]).tobytes()
                        + np.ascontiguousarray(s["stimOn_times"]).tobytes()).hexdigest()
        key.setdefault(h, []).append(s["session_id"])
    dup_ids = {x for v in key.values() if len(v) > 1 for x in v}

    # cell 9: the project's mice, and those whose whole training is in the dataset
    S = S[~S.session_id.isin(dup_ids) & (S.n_trials > 0)].copy()
    T = T[T.session_id.isin(S.session_id)].copy()
    mice = ib.project_mice(S)
    lab = S.groupby("subject_id").lab_number.first()
    Dall = ib.daily(T, S)
    first = Dall.groupby("subject_id").head(1).set_index("subject_id")
    first_stage = first.contrasts.apply(lambda c: c == frozenset([50.0, 100.0]))
    complete = first_stage[first_stage].index.intersection(mice)
    Sc = S[S.subject_id.isin(complete)]
    Tc = T[T.session_id.isin(Sc.session_id)]
    Dc = Dall[Dall.subject_id.isin(complete)]
    Dfull = ib.daily(Tc, Sc, ["biased"])
    Tm = ib.trials_with_days(Tc, Sc, Dc)

    # cell 10: basic (P1, main reading) and full (P2) task proficiency
    SS = ib.session_summary(Tc, Sc)
    tday = Dc.set_index(["subject_id", "date"]).tday0
    st = ib.training_status(SS, Tc, "each", None)
    P1 = st[st.p1_session.notna()].copy()
    P1["p1_tday0"] = [int(tday[(s, d)]) for s, d in zip(P1.index, P1.p1_date)]
    P2 = ib.full_proficiency(Dfull, Tc, Sc)
    print(f"{len(mice)} project mice, {len(complete)} with their whole training, "
          f"{len(P1)} reach P1, {len(P2)} reach P2")

    # cell 39: the basic-task sessions of the P1 day and the two days before it (S1)
    t1 = ib.window(Tm, P1.p1_tday0, -2, 0, ["training"])
    s1_fits = ib.mouse_fits(t1)
    s1_points = (t1.groupby(["subject_id", "signed_contrast"]).choice_right
                 .agg(["mean", "size"]).reset_index())

    # cell 64: the full-task sessions of the P2 day and the two days before it (S2), by block
    t2 = ib.window(Tm, P2.p2_tday0, -2, 0, ["biased"])
    t2 = t2.assign(block=np.select([np.isclose(t2.probabilityLeft, 0.2), np.isclose(t2.probabilityLeft, 0.8)],
                                   ["2080", "8020"], "5050"))
    s2_fits = ib.mouse_fits(t2, by=("subject_id", "block")).reset_index()
    s2_points = (t2.groupby(["subject_id", "block", "signed_contrast"]).choice_right
                 .agg(["mean", "size"]).reset_index())

    # one row per mouse of the whole-training cohort
    first_date = Sc.groupby("subject_id").date.min()
    mouse = pd.DataFrame({
        "lab": lab[complete], "nickname": S.groupby("subject_id").nickname.first()[complete],
        "first_date": first_date[complete], "n_days": Dc.groupby("subject_id").tday0.max()[complete] + 1,
        "p1_tday0": P1.p1_tday0.reindex(complete), "p2_tday0": P2.p2_tday0.reindex(complete),
    })
    mouse.index.name = "subject_id"
    # first session date of every mouse of the project in the dataset (for the coverage plot)
    all_first = S[S.subject_id.isin(mice)].groupby("subject_id").date.min().rename("first_date").to_frame()
    all_first["lab"] = lab[all_first.index]
    all_first["whole_training"] = all_first.index.isin(complete)

    mouse.reset_index().to_parquet(OUT / "mice.parquet")
    all_first.reset_index().to_parquet(OUT / "project_mice.parquet")
    Dc[["subject_id", "date", "tday0", "n_trials", "perf_easy", "basic_only"]].to_parquet(OUT / "daily.parquet")
    s1_fits.reset_index().to_parquet(OUT / "s1_fits.parquet")
    s1_points.to_parquet(OUT / "s1_points.parquet")
    s2_fits.to_parquet(OUT / "s2_fits.parquet")
    s2_points.to_parquet(OUT / "s2_points.parquet")

    # checks against the attempt (cells 13, 16, 45, 84)
    days = P1.p1_tday0 + 1
    sh = []
    for m, g in s2_fits.set_index("block").groupby("subject_id"):
        if {"2080", "8020"} <= set(g.index):
            p = {b: g.loc[b, ["bias", "threshold", "lapselow", "lapsehigh"]].to_dict() for b in ("2080", "8020")}
            sh.append(100 * (ib.gamma_curve(p["2080"], 0.0) - ib.gamma_curve(p["8020"], 0.0)))
    summary = {
        "project_mice": len(mice), "whole_training": len(complete), "p1": len(P1), "p2": len(P2),
        "days_to_p1_mean_incl": float(days.mean()), "days_to_p1_sd": float(days.std()),
        "days_to_p1_min_incl": int(days.min()), "days_to_p1_max_incl": int(days.max()),
        "s1_threshold_mean": float(s1_fits.threshold.mean()), "s1_threshold_sd": float(s1_fits.threshold.std()),
        "s1_bias_mean": float(s1_fits.bias.mean()), "s1_bias_sd": float(s1_fits.bias.std()),
        "s1_n": int(s1_fits.threshold.notna().sum()),
        "bias_shift_at_0_mean": float(np.nanmean(sh)), "bias_shift_n": int(np.sum(np.isfinite(sh))),
        "first_date": str(S.date.min()), "last_date": str(S.date.max()),
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    print(f"done in {(time.time() - t0) / 60:.1f} min")


if __name__ == "__main__":
    main()
