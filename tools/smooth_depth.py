#!/usr/bin/env python3
"""ECADEMY ECDIS · smooth the simulated offshore depths of an existing chart pack.

The world packs build offshore depth from Natural Earth depth zones rasterised in ~2 NM blocks,
which gives staircase contours (straight, right-angled, with the 100/200/1000 m lines stacked on
one cliff). This smooths every cell's depth grid offshore and redraws its contours, without the
original source data:

  * near the coast (< ~0.5 NM) the depth is kept as built; full smoothing from ~3 NM out
  * shallow water (< 15 m) is never made deeper: shoals, reefs and the safety-relevant depths stay
  * dredged channels keep their maintained depth
  * land, cells, soundings source and everything else in the pack are unchanged

usage: python3 -I smooth_depth.py <pack-id> [<pack-id> ...] [--sigma NM] [--dir ASSETS]
       python3 -I smooth_depth.py --seams <pack-id> ...   # then make neighbouring cells meet at their edges
"""
import gzip, json, math, os, sys
import numpy as np
from scipy import ndimage
from skimage import measure, draw
from shapely.geometry import LineString

LAND_Q = 104
BAND_LEVELS = {1: [0, 20, 50, 100, 200, 500, 1000, 2000], 2: [0, 5, 10, 20, 30, 50, 100, 200, 500, 1000, 2000],
               3: [0, 2, 5, 10, 15, 20, 30, 50, 100, 200, 500, 1000], 4: [0, 2, 5, 10, 15, 20, 30, 50, 100, 200], 5: [0, 2, 5, 10, 15, 20, 30, 50]}
HERE = os.path.dirname(os.path.abspath(__file__))


def decode(blob, n):
    q = np.frombuffer(blob, dtype="<u2").astype(np.int64)
    return (np.cumsum(q) & 0xffff)[:n]


def encode(depth, land):
    dq_ = np.where(depth < 30, 0.1, np.where(depth < 100, 0.5, np.where(depth < 300, 2.0, np.where(depth < 1000, 10.0, 50.0))))
    depth = np.round(depth / dq_) * dq_
    q = np.clip(np.round((depth + 10) * 10), 1, 65000).astype(np.int64)
    q[land] = LAND_Q
    q[(q >= 102) & (q <= 106) & ~land] = 107
    return (np.diff(q.ravel(), prepend=0) & 0xffff).astype("<u2").tobytes()


def flat(pts, nd=3):
    return [round(float(v), nd) for p in pts for v in p]


def contours(depth, land, x0, y0, res, levels, tol):
    out = {}
    dd = np.where(land, -5.0, depth)
    for L in levels:
        thr = 0.0 if L == 0 else L
        lines = []
        for c in measure.find_contours(dd, thr - (0.001 if L == 0 else 0)):
            if len(c) < 3: continue
            pts = [(x0 + p[1] * res, y0 + p[0] * res) for p in c]
            if len(pts) >= 3: pts = list(LineString(pts).simplify(tol, preserve_topology=False).coords)
            if len(pts) >= 2: lines.append(flat(pts))
        if lines: out[str(L)] = lines
    return out


def smooth_cell(depth, land, res, drg, x0, y0, sigma_nm):
    sea = ~land
    if not sea.any(): return depth
    dcoast = ndimage.distance_transform_edt(sea) * res if land.any() else np.full(depth.shape, 1e3)
    s = max(1.0, sigma_nm / res)
    w = sea.astype(np.float64)
    num = ndimage.gaussian_filter(np.where(sea, depth, 0.0).astype(np.float64), s, mode="nearest")
    den = ndimage.gaussian_filter(w, s, mode="nearest")
    sm = np.where(den > 1e-6, num / np.maximum(den, 1e-6), depth)
    a = np.clip((dcoast - 0.5) / 2.5, 0.0, 1.0)                  # 0 at the coast -> 1 from ~3 NM out
    new = a * sm + (1 - a) * depth
    shallow = depth < 15
    new = np.where(shallow, np.minimum(depth, new), new)          # never deepen shallow water
    new = np.where(new < 15, np.minimum(new, np.maximum(depth, 15.0)), new)   # never make deep water shallower than 15 m
    # dredged channels keep their maintained depth
    for d in drg:
        pts = d["pts"]; m = np.zeros(depth.shape, bool)
        for (ax, ay), (bx, by) in zip(pts[:-1], pts[1:]):
            rr, cc = draw.line(int(round((ay - y0) / res)), int(round((ax - x0) / res)), int(round((by - y0) / res)), int(round((bx - x0) / res)))
            ok = (rr >= 0) & (rr < depth.shape[0]) & (cc >= 0) & (cc < depth.shape[1]); m[rr[ok], cc[ok]] = True
        if m.any():
            m = ndimage.binary_dilation(m, iterations=max(1, int(round((d["hw"] + 0.1) / res))))
            new = np.where(m, depth, new)
    return np.where(land, depth, new).astype(np.float32)


def process(pid, adir, sigma_nm):
    cf, df = os.path.join(adir, f"ecdis_{pid}_chart.gz"), os.path.join(adir, f"ecdis_{pid}_depth.gz")
    js = json.load(gzip.open(cf))
    if js.get("smooth"): print(f"  {pid}: already smoothed, skipped"); return
    raw = gzip.open(df).read()
    offs = js["offs"] + [len(raw)]
    drg = js["feat"].get("drg", [])
    blobs = []
    for i, c in enumerate(js["cells"]):
        n = c["nx"] * c["ny"]
        q = decode(raw[offs[i]:offs[i + 1]], n).reshape(c["ny"], c["nx"])
        land = q == LAND_Q
        depth = q / 10.0 - 10
        new = smooth_cell(depth, land, c["res"], drg, c["x0"], c["y0"], sigma_nm)
        c["cont"] = contours(new, land, c["x0"], c["y0"], c["res"], BAND_LEVELS[c["band"]], c["res"] * 0.6)
        blobs.append(encode(new, land))
    o = [0]
    for b in blobs: o.append(o[-1] + len(b))
    js["offs"] = o[:-1]; js["smooth"] = sigma_nm
    with gzip.open(cf, "wb", compresslevel=9) as f: f.write(json.dumps(js, separators=(",", ":")).encode())
    with gzip.open(df, "wb", compresslevel=9) as f:
        for b in blobs: f.write(b)
    print(f"  {pid}: {len(js['cells'])} cells smoothed (sigma {sigma_nm} NM)")


def seams(pid, adir, width_nm=2.0):
    """make neighbouring cells meet: near its box edge, blend each cell's depth into the depth of the cell
    that is shown next to it (lower band, or an earlier cell of the same band), so contours run on across
    the cell boundary instead of stopping or jumping there"""
    cf, df = os.path.join(adir, f"ecdis_{pid}_chart.gz"), os.path.join(adir, f"ecdis_{pid}_depth.gz")
    js = json.load(gzip.open(cf))
    if js.get("seams"): print(f"  {pid}: seams already done, skipped"); return
    raw = gzip.open(df).read(); offs = js["offs"] + [len(raw)]; cells = js["cells"]
    grids = []
    for i, c in enumerate(cells):
        q = decode(raw[offs[i]:offs[i + 1]], c["nx"] * c["ny"]).reshape(c["ny"], c["nx"])
        grids.append([q / 10.0 - 10, q == LAND_Q])
    order = sorted(range(len(cells)), key=lambda i: (cells[i]["band"], i))
    done = []
    for i in order:
        c = cells[i]; depth, land = grids[i]; res = c["res"]
        bx = c["box"]; W = min(width_nm, 0.25 * min(bx[2] - bx[0], bx[3] - bx[1]))
        cands = [k for k in done if (cells[k]["band"] < c["band"] or k < i)]
        if not cands or W <= res: done.append(i); continue
        X = c["x0"] + np.arange(c["nx"])[None, :] * res; Y = c["y0"] + np.arange(c["ny"])[:, None] * res
        X = np.broadcast_to(X, depth.shape); Y = np.broadcast_to(Y, depth.shape)
        edge = np.minimum.reduce([X - bx[0], bx[2] - X, Y - bx[1], bx[3] - Y])
        band = (edge < W) & ~land
        if not band.any(): done.append(i); continue
        tgt = np.full(depth.shape, np.nan); best = np.full(depth.shape, -1)
        px, py = X[band], Y[band]; tv = np.full(px.shape, np.nan); tb = np.full(px.shape, -1)
        for k in cands:   # the cell shown under/next to this one: highest band, then earliest
            o = cells[k]; ob = o["box"]
            m = (px >= ob[0]) & (px <= ob[2]) & (py >= ob[1]) & (py <= ob[3]) & (o["band"] > tb)
            if not m.any(): continue
            d2, l2 = grids[k]
            fi = (px[m] - o["x0"]) / o["res"]; fj = (py[m] - o["y0"]) / o["res"]
            v = ndimage.map_coordinates(np.where(l2, np.nan, d2), [fj, fi], order=1, mode="nearest")
            sel = np.where(m)[0]; tv[sel] = v; tb[sel] = o["band"]
        tgt[band] = tv
        w = np.clip(1 - edge / W, 0, 1)
        ok = band & np.isfinite(tgt)
        new = depth.copy(); new[ok] = w[ok] * tgt[ok] + (1 - w[ok]) * depth[ok]
        new = np.where(land, depth, new)
        grids[i][0] = new.astype(np.float32); done.append(i)
    blobs = []
    for i, c in enumerate(cells):
        depth, land = grids[i]
        c["cont"] = contours(depth, land, c["x0"], c["y0"], c["res"], BAND_LEVELS[c["band"]], c["res"] * 0.6)
        blobs.append(encode(depth, land))
    o = [0]
    for b in blobs: o.append(o[-1] + len(b))
    js["offs"] = o[:-1]; js["seams"] = width_nm
    with gzip.open(cf, "wb", compresslevel=9) as f: f.write(json.dumps(js, separators=(",", ":")).encode())
    with gzip.open(df, "wb", compresslevel=9) as f:
        for b in blobs: f.write(b)
    print(f"  {pid}: {len(cells)} cells, seams blended ({width_nm} NM)")


if __name__ == "__main__":
    a = sys.argv[1:]; sigma = 2.5; adir = os.path.join(HERE, "..", "assets")
    if "--sigma" in a: i = a.index("--sigma"); sigma = float(a[i + 1]); del a[i:i + 2]
    if "--dir" in a: i = a.index("--dir"); adir = a[i + 1]; del a[i:i + 2]
    do_seams = "--seams" in a; a = [x for x in a if x != "--seams"]
    for pid in a: seams(pid, adir) if do_seams else process(pid, adir, sigma)
