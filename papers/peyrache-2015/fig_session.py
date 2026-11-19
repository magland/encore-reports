"""Interactive figure: one session of head-direction cells, waking and sleep, on one time axis.

Reads the caches written by compute.py. Three tracks share one time axis:
- sleep states and the head direction tracked by camera (waking only);
- the posterior over head direction decoded from the 15 thalamic (ADn) head-direction cells,
  50 ms by 6 degrees, in all scored states;
- the spikes of the 24 head-direction cells (ADn and PoS), ordered by preferred direction.

Run from the repository root:  .venv/bin/python papers/peyrache-2015/fig_session.py [--upload]
"""

import sys
from pathlib import Path

import numpy as np
import figpack.views as fv
from figpack_experimental.views import RingRaster
from figpack_spike_sorting.views import RasterPlot, RasterPlotItem

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "cache" / "peyrache-2015"
TITLE = "Peyrache et al. 2015: head-direction cells awake and asleep (Mouse28-140313)"
STATE_COLORS = {"wake": "#9a9893", "SWS": "#2a78d6", "REM": "#eb6834"}
STATE_NAMES = {"wake": "awake", "SWS": "slow-wave sleep", "REM": "REM sleep"}
POST_STEP = 0.05


def main():
    d = np.load(CACHE / "session.npz")
    post = np.load(CACHE / "posterior.npy")
    spikes = np.split(d["spike_times"], d["spike_index"][:-1])
    t_end = post.shape[0] * POST_STEP

    states = fv.TimeseriesGraph(y_label="head direction (deg)", y_range=[0, 360],
                                legend_opts={"location": "northeast"}, hide_nav_toolbar=True)
    for k in ("wake", "SWS", "REM"):
        iv = d[f"state_{k}"]
        states.add_interval_series(name=STATE_NAMES[k], t_start=iv[:, 0], t_end=iv[:, 1],
                                   color=STATE_COLORS[k], alpha=0.25)
    # The file holds an LED angle through the whole session, but only the open field is tracked
    # reliably (in the home cage it jitters by about 30 deg/s while the mouse sleeps), so only
    # waking is shown, as in the attempt.
    w = d["state_wake"]
    ok = np.isfinite(d["hd"]) & (d["hd_t"] >= w[0, 0]) & (d["hd_t"] < w[-1, 1])
    states.add_marker_series(name="head direction", t=d["hd_t"][ok],
                             y=np.degrees(d["hd"][ok]), color="#0b0b0b", radius=1.5)

    nb = post.shape[1]
    decoded = fv.Spectrogram(start_time_sec=0.0, sampling_frequency_hz=1 / POST_STEP, data=post,
                             frequencies=(np.arange(nb) + 0.5) * 360 / nb, y_label="direction (deg)",
                             hide_nav_toolbar=True)

    hdm = np.where(d["is_hd"])[0]
    order = hdm[np.argsort(d["pref"][hdm])]
    items = [RasterPlotItem(unit_id=f"{d['region'][i]} {int(d['unit'][i])} ({np.degrees(d['pref'][i]):.0f}°)",
                            spike_times_sec=spikes[i]) for i in order]
    raster = RasterPlot(start_time_sec=0.0, end_time_sec=t_end, plots=items)

    # the 24 cells on a ring at their preferred directions, at the current time of the timeline
    ring = RingRaster(unit_ids=[f"{d['region'][i]} {int(d['unit'][i])}" for i in order],
                      angles_deg=np.degrees(d["pref"][order]), spike_times_sec=[spikes[i] for i in order],
                      unit_colors=["#6250d6"] * len(order), start_time_sec=0.0, end_time_sec=t_end,
                      flash_sec=0.1, playback_speed=1.0)
    w = d["state_wake"]
    ok = np.isfinite(d["hd"]) & (d["hd_t"] >= w[0, 0]) & (d["hd_t"] < w[-1, 1])
    ring.add_needle(name="head direction (camera)", t=d["hd_t"][ok], angle_deg=np.degrees(d["hd"][ok]),
                    color="#0b0b0b")
    dt = np.concatenate([d[f"dec_t_{k}"] for k in ("wake", "SWS", "REM")])
    da = np.concatenate([d[f"dec_{k}"] for k in ("wake", "SWS", "REM")])
    o = np.argsort(dt)
    ring.add_needle(name="decoded from the 15 thalamic cells", t=dt[o], angle_deg=np.degrees(da[o]),
                    color="#1baf7a", max_gap_sec=0.02)

    tracks = fv.Box(direction="vertical", items=[
        fv.LayoutItem(states, stretch=1.2, title="States and tracked head direction"),
        fv.LayoutItem(decoded, stretch=1.4, title="Direction decoded from the 15 thalamic cells (posterior)"),
        fv.LayoutItem(raster, stretch=2.0, title="Spikes of the 24 head-direction cells, by preferred direction"),
    ])
    view = fv.Box(direction="horizontal", items=[
        fv.LayoutItem(ring, stretch=1, min_size=300, max_size=480,
                      title="The 24 cells at their preferred directions"),
        fv.LayoutItem(tracks, stretch=2.5),
    ])
    description = f"""\
One session of DANDI:000056 (Mouse28-140313, {t_end / 3600:.1f} h), from the data of Peyrache et
al. (2015). All tracks share one time axis: zoom and pan in any of them. The head direction is
tracked by camera in the open field only. The posterior over head direction is decoded from the 15
thalamic (ADn) head-direction cells with their waking tuning curves, as in the Encore attempt
peyrache-2015-02, and shown in 50 ms by 6 degree bins in the scored states. Cells are ordered by
their preferred direction in waking.
"""
    if "--upload" in sys.argv:
        print(view.show(title=TITLE, description=description, upload=True, open_in_browser=False,
                        wait_for_input=False))
    else:
        out = CACHE / "figures" / "session"
        view.save(str(out), title=TITLE, description=description)
        print(f"saved {out}")


if __name__ == "__main__":
    main()
