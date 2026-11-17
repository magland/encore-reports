"""Stream one whole session of DANDI:000041 (Rizzo, 2015-02-27, 7.2 h) for the whole-night figure.

Reads the session's units, sleep states and four LFP channels (the spindle reference channel
used by the Encore attempt, and the electrode at the same depth on three other shanks, every
second shank). The LFP is read by parallel byte-range requests on its gzip chunks, which are
one channel by 59,174 samples. Each channel is low-pass filtered and downsampled from 1250 Hz to
250 Hz, which keeps everything below 100 Hz. The spectrogram is computed from the reference
channel at full rate, with 2 s Hann windows stepped by 1 s (the attempt's settings for LFP
power), from 0.5 to 100 Hz. Writes cache/watson-2016/session.npz at the repository root.

Run from the repository root:  .venv/bin/python papers/watson-2016/compute_session.py
"""

import time
import zlib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import h5py
import numpy as np
import remfile
import requests
from scipy import signal

import sleepstates as ss

SESSION = "sub-Rizzo/sub-Rizzo_ses-Rizzo-022715_ecephys.nwb"
OUT = Path(__file__).resolve().parents[2] / "cache" / "watson-2016" / "session.npz"
DOWNSAMPLE = 5              # 1250 Hz -> 250 Hz
SPEC_FMAX = 100.0
BLOCK = 8 * 2**20


def _get(url, a, b):
    for attempt in range(5):
        try:
            r = requests.get(url, headers={"Range": f"bytes={a}-{b - 1}"}, timeout=180)
            r.raise_for_status()
            if len(r.content) == b - a:
                return r.content
        except requests.RequestException:
            if attempt == 4:
                raise
    raise RuntimeError(f"short read {a}-{b}")


def read_columns(url: str, d: h5py.Dataset, cols: list[int]) -> np.ndarray:
    """Whole columns of a 2-D dataset chunked as (n, 1) with gzip, by parallel range requests."""
    if d.chunks[1] != 1 or set(d._filters) - {"gzip", "shuffle"}:
        raise ValueError(f"unexpected layout {d.chunks} {d._filters}")
    shuffle = "shuffle" in d._filters
    info = [d.id.get_chunk_info(i) for i in range(d.id.get_num_chunks())]
    want = [c for c in info if c.chunk_offset[1] in cols]
    want.sort(key=lambda c: c.byte_offset)
    groups, cur = [], [want[0]]
    for c in want[1:]:
        if c.byte_offset == cur[-1].byte_offset + cur[-1].size and \
                c.byte_offset + c.size - cur[0].byte_offset <= BLOCK:
            cur.append(c)
        else:
            groups.append(cur)
            cur = [c]
    groups.append(cur)
    out = np.empty((d.shape[0], len(cols)), dtype=d.dtype)
    rows, item = d.chunks[0], d.dtype.itemsize

    def fetch(group):
        raw = _get(url, group[0].byte_offset, group[-1].byte_offset + group[-1].size)
        for c in group:
            buf = zlib.decompress(raw[c.byte_offset - group[0].byte_offset:][:c.size])
            if shuffle:
                buf = np.frombuffer(buf, np.uint8).reshape(item, -1).T.tobytes()
            x = np.frombuffer(buf, dtype=d.dtype)
            r0 = c.chunk_offset[0]
            n = min(rows, d.shape[0] - r0)
            out[r0:r0 + n, cols.index(c.chunk_offset[1])] = x[:n]

    with ThreadPoolExecutor(16) as ex:
        list(ex.map(fetch, groups))
    # spot checks against h5py
    for j, col in enumerate(cols):
        for r0 in (0, d.shape[0] // 2, d.shape[0] - 7):
            if not np.array_equal(out[r0:r0 + 5, j], d[r0:r0 + 5, col]):
                raise ValueError("range read disagrees with h5py")
    return out


def main():
    t0 = time.time()
    url = dict(ss.asset_urls())[SESSION]
    f = h5py.File(remfile.File(url), "r")
    s = ss.load_session(SESSION, url, f)
    el = f["general/extracellular_ephys/electrodes"]
    group = np.array([g.decode() if isinstance(g, bytes) else g for g in el["group_name"][()]])
    depth = el["shank_electrode_number"][()]
    lfp = f["processing/ecephys/LFP/lfp"]
    lfp_el = lfp["electrodes"][()]
    ref_el = int(lfp_el[s.lfp_channel])
    shanks = sorted(set(group), key=lambda g: int(g.replace("shank", "")))
    ref_shank = shanks.index(group[ref_el])
    pick = [sh for i, sh in enumerate(shanks) if i % 2 == ref_shank % 2]
    elec = [int(np.where((group == sh) & (depth == depth[ref_el]))[0][0]) for sh in pick]
    cols = [int(np.where(lfp_el == e)[0][0]) for e in elec]
    # The file states volts with a conversion of NaN (an Encore finding), so the LFP cannot be put
    # in volts; it is kept in the stored ADC units.
    conv = float(lfp["data"].attrs.get("conversion", np.nan))
    scale = conv * 1e6 if np.isfinite(conv) else 1.0
    lfp_unit = "uV" if np.isfinite(conv) else "ADC units"
    print(f"units {len(s.spikes)}, LFP {lfp['data'].shape}, channels {list(zip(pick, elec, cols))}, "
          f"reference {group[ref_el]} electrode {ref_el}, conversion {conv}")

    raw = read_columns(url, lfp["data"], cols)
    print(f"read LFP in {time.time() - t0:.0f} s")
    fs = ss.LFP_RATE
    ref = raw[:, cols.index(s.lfp_channel)].astype(np.float32) * scale
    fr, tt, sxx = signal.spectrogram(ref, fs=fs, window="hann", nperseg=int(2 * fs), noverlap=int(fs))
    keep = (fr >= 0.5) & (fr <= SPEC_FMAX)
    spec = np.log10(sxx[keep].T + 1e-12).astype(np.float32)                         # times x freqs
    lfp_ds = np.stack([signal.decimate(raw[:, j].astype(np.float64) * scale, DOWNSAMPLE,
                                       ftype="fir", zero_phase=True) for j in range(len(cols))],
                      axis=1).astype(np.float32)

    spike_times = np.concatenate(s.spikes)
    spike_index = np.cumsum([len(x) for x in s.spikes])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        OUT, session=s.session_id, subject=s.subject,
        lfp=lfp_ds, lfp_unit=lfp_unit, lfp_rate=fs / DOWNSAMPLE, lfp_shanks=np.array(pick), lfp_electrodes=np.array(elec),
        lfp_reference=cols.index(s.lfp_channel),
        spec=spec, spec_freqs=fr[keep], spec_t0=tt[0], spec_dt=tt[1] - tt[0],
        spike_times=spike_times, spike_index=spike_index, cell_type=s.cell_type,
        unit_ids=f["units/id"][()],
        starts=s.starts, stops=s.stops, labels=s.labels, state=s.state.astype(str),
        cycles=np.array([[c["start"], c["stop"]] for c in ss.cycles(s)]),
    )
    print(f"LFP {lfp_ds.shape} at {fs / DOWNSAMPLE:g} Hz ({lfp_ds.nbytes / 1e6:.0f} MB float32), "
          f"spectrogram {spec.shape}, spikes {len(spike_times)}, hours {raw.shape[0] / fs / 3600:.2f}")
    print(f"wrote {OUT} ({OUT.stat().st_size / 1e6:.0f} MB) in {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
