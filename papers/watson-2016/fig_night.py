"""Interactive figure: one whole night of recording, zoomable from hours to milliseconds.

Reads the caches written by compute_session.py and compute_cells.py. Four tracks share one time
axis, and each is stored at several resolutions so that the viewer loads only what the current
zoom needs:
- sleep states (the lab's scoring, with microarousals as defined by the Encore attempt) and the
  population firing rate of the pyramidal (pE) cells in 10 s bins;
- the spectrogram of the reference LFP channel, 0.5 to 100 Hz;
- the LFP of four channels, one on every second shank, at 250 Hz;
- the spikes of all 93 units, pE cells ordered from the slowest to the fastest WAKE rate, then
  the interneurons (pI).

Run from the repository root:  .venv/bin/python papers/watson-2016/fig_night.py [--upload]
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import figpack.views as fv
from figpack_experimental.views import StackedTraces
from figpack_spike_sorting.views import RasterPlot, RasterPlotItem

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "cache" / "watson-2016"
TITLE = "Watson et al. 2016: one night in rat frontal cortex (Rizzo, 2015-02-27)"
STATE_COLORS = {"WAKE": "#9a9893", "NREM": "#2a78d6", "REM": "#eb6834", "MA": "#1baf7a"}
STATE_NAMES = {"WAKE": "WAKE", "NREM": "nonREM", "REM": "REM", "MA": "microarousal"}
RATE_BIN = 10.0


def main():
    d = np.load(CACHE / "session.npz")
    sext = pd.read_parquet(CACHE / "unit_sextiles.parquet")
    session = str(d["session"])
    t_end = len(d["lfp"]) / float(d["lfp_rate"])

    # states and population rate
    states = fv.TimeseriesGraph(y_label="pE rate (Hz)", legend_opts={"location": "northeast"},
                                hide_nav_toolbar=True)
    for k in ("WAKE", "NREM", "REM", "MA"):
        m = d["state"] == k
        states.add_interval_series(name=STATE_NAMES[k], t_start=d["starts"][m], t_end=d["stops"][m],
                                   color=STATE_COLORS[k], alpha=0.35)
    spikes = np.split(d["spike_times"], d["spike_index"][:-1])
    pe = np.where(d["cell_type"] == "excitatory")[0]
    edges = np.arange(0, t_end + RATE_BIN, RATE_BIN)
    rate = np.mean([np.histogram(spikes[u], edges)[0] for u in pe], axis=0) / RATE_BIN
    states.add_line_series(name="mean pE rate", t=(edges[:-1] + edges[1:]) / 2, y=rate, color="#0b0b0b",
                           width=1.2)

    # each frequency's log power relative to its median over the night, so that changes of
    # state are not swamped by the fall of power with frequency
    rel = (d["spec"] - np.median(d["spec"], axis=0, keepdims=True)).astype(np.float32)
    spec = fv.Spectrogram(start_time_sec=float(d["spec_t0"]), sampling_frequency_hz=1.0 / float(d["spec_dt"]),
                          data=rel, frequencies=d["spec_freqs"], y_label="Frequency (Hz)",
                          hide_nav_toolbar=True)

    lfp = StackedTraces(start_time_sec=0.0, sampling_frequency_hz=float(d["lfp_rate"]), data=d["lfp"],
                        channel_ids=[f"{sh} ({'reference' if i == int(d['lfp_reference']) else 'LFP'})"
                                     for i, sh in enumerate(d["lfp_shanks"])])

    # units: pE by WAKE rate (from slowest), then pI, then the rest
    s = sext[sext.session == session].set_index("unit")
    wake = {u: s.wake_rate.get(u, np.nan) for u in range(len(spikes))}
    order = sorted(pe, key=lambda u: wake[u]) + [u for u in range(len(spikes)) if d["cell_type"][u] == "inhibitory"] \
        + [u for u in range(len(spikes)) if d["cell_type"][u] not in ("excitatory", "inhibitory")]
    items = []
    for u in order:
        kind = {"excitatory": "pE", "inhibitory": "pI"}.get(str(d["cell_type"][u]), "?")
        label = f"{kind} {int(d['unit_ids'][u])}" + (f" s{int(s.sextile[u])}" if u in s.index else "")
        items.append(RasterPlotItem(unit_id=label, spike_times_sec=spikes[u]))
    raster = RasterPlot(start_time_sec=0.0, end_time_sec=t_end, plots=items)

    view = fv.Box(direction="vertical", items=[
        fv.LayoutItem(states, stretch=1.1, title="Sleep states and mean pE firing rate"),
        fv.LayoutItem(spec, stretch=1.3, title="Spectrogram of the reference channel (log10 power relative to each frequency's median)"),
        fv.LayoutItem(lfp, stretch=2.4, title=f"LFP, 4 shanks, {float(d['lfp_rate']):g} Hz ({d['lfp_unit']})"),
        fv.LayoutItem(raster, stretch=2.4, title="Spikes: pE cells from slowest to fastest WAKE rate, then pI"),
    ])

    description = f"""\
One whole session of DANDI:000041 (session {session}, {t_end / 3600:.1f} h, 93 units), from the
data of Watson et al. (2016). All four tracks share one time axis: zoom and pan in any of them.
Sleep states are the lab's scoring as deposited; microarousals (WAKE under 40 s between nonREM
epochs) follow the Encore attempt watson-2016-01. The LFP is low-pass filtered and downsampled
from 1250 Hz to 250 Hz, in the stored ADC units (the file states volts with no valid
conversion factor). The spectrogram uses 2 s windows in 1 s steps at full rate, and shows each frequency's
log10 power relative to its median over the night. Every track is
stored at several resolutions and loaded as needed.
"""
    if "--upload" in sys.argv:
        print(view.show(title=TITLE, description=description, upload=True, open_in_browser=False,
                        wait_for_input=False))
    else:
        out = CACHE / "figures" / "night"
        view.save(str(out), title=TITLE, description=description)
        print(f"saved {out}")


if __name__ == "__main__":
    main()
