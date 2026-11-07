#!/usr/bin/env python3
"""ECADEMY ECDIS · published routeing measures that are not in OpenSeaMap, added to a chart pack.

IRTC, Gulf of Aden (Internationally Recommended Transit Corridor), from IMO SN.1/Circ.281 and the MSCHOA
/ BMP corridor description: two 5 NM lanes with a 2 NM buffer between them.
  eastbound lane (south): 045°00'E 11°48'N-11°53'N  ->  053°00'E 14°18'N-14°23'N, course 072°
  westbound lane (north): 053°00'E 14°25'N-14°30'N  ->  045°00'E 11°55'N-12°00'N, course 252°
It is a recommended transit corridor, not a traffic separation scheme. Training use only: check the current
BMP edition, UKHO chart Q6099 and MSCHOA before relying on it.

usage: python3 -I routes.py irtc <chart.gz>      # e.g. assets/ecdis_gulf_chart.gz (idempotent)
       python3 -I routes.py vts sea nweu med       # published VTS reporting lines and pilot boarding places
"""
import gzip, json, math, os, sys

SRC = "IMO SN.1/Circ.281, MSCHOA/BMP IRTC description"


def lane(lat45_s, lat45_n, lat53_s, lat53_n, orient, name, n_arrows=8):
    ring = [[45.0, lat45_s], [53.0, lat53_s], [53.0, lat53_n], [45.0, lat45_n]]
    arrows = []
    for k in range(n_arrows):
        t = (k + 0.5) / n_arrows
        lon = 45.0 + 8.0 * t
        lat = (lat45_s + lat45_n) / 2 + ((lat53_s + lat53_n) / 2 - (lat45_s + lat45_n) / 2) * t
        arrows.append([round(lon, 4), round(lat, 4), orient])
    C = math.cos(math.radians(13.2))
    length = math.hypot(8.0 * 60 * C, ((lat53_s + lat53_n) / 2 - (lat45_s + lat45_n) / 2) * 60)
    return dict(c="TSSLPT", ring=ring, name=name, orient=orient, len=round(length, 1), arrows=arrows, src="irtc", osm="irtc",
                att={"OBJNAM": name, "ORIENT": f"{orient:03d}°", "CATTSS": "recommended transit corridor (not a TSS)", "SORIND": SRC,
                     "INFORM": "Transit inside the IRTC; register with MSCHOA and report to UKMTO (BMP)."},
                why="IRTC, Gulf of Aden: recommended transit corridor for the high-risk area. Keep to the lane for your direction "
                    "(eastbound in the southern lane, westbound in the northern lane), register with MSCHOA and report to UKMTO "
                    "as required by BMP. It is not a traffic separation scheme.")


def irtc(chart_gz):
    js = json.load(gzip.open(chart_gz))
    F = js.setdefault("feat", {})
    F["areas"] = [a for a in F.get("areas", []) if a.get("src") != "irtc"]
    F["areas"] += [
        lane(11 + 48 / 60, 11 + 53 / 60, 14 + 18 / 60, 14 + 23 / 60, 72, "IRTC eastbound lane"),
        lane(11 + 55 / 60, 12 + 0 / 60, 14 + 25 / 60, 14 + 30 / 60, 252, "IRTC westbound lane"),
    ]
    with gzip.open(chart_gz, "wb", compresslevel=9) as f: f.write(json.dumps(js, separators=(",", ":")).encode())
    print(f"  IRTC lanes written to {chart_gz} ({os.path.getsize(chart_gz) / 1e6:.2f} MB)")


# ----------------------------------------------------------------------------- VTS reporting lines and pilot boarding
# Published values only (read from the cited documents); [lat, lon] in decimal degrees as published.
MSC73 = "IMO MSC.73(69) STRAITREP; MPA Singapore, Arrivals and Departures"
MSC85 = "UK MGN 364 (M+F) amdt 1 / IMO MSC.85(70) CALDOVREP"
MSC300 = "IMO MSC.300(87) GIBREP"
MSC314 = "IMO MSC.314(88) SOUNDREP"
SJO = "Sjofartsverket, Sound pilotage / Port of Malmo guidelines"
VTS = {
    "sea": {
        "lines": [
            ("STRAITREP entry Tg Piai - P. Karimun Kecil (VTIS West)", "VHF 73", [[1.258333, 103.5125], [1.153333, 103.405833]], MSC73),
        ],
        "meridians": [   # (name, VHF, longitude, latitude window searched for the water crossing, source)
            ("STRAITREP Sector 1 west limit (Klang VTS)", "VHF 66", 100.666667, (1.0, 5.0), MSC73),
            ("STRAITREP Sector 7/8 (VTIS West / Central)", "VHF 73 / 14", 103.741667, (1.0, 1.4), MSC73),
            ("STRAITREP Sector 8/9 (VTIS Central / East)", "VHF 14 / 10", 104.035, (1.0, 1.4), MSC73),
            ("STRAITREP east limit (VTIS East)", "VHF 10", 104.383333, (1.0, 1.6), MSC73),
        ],
        "parallels": [],
        "pilots": [],
    },
    "nweu": {
        "lines": [
            ("CALDOVREP Dover Coastguard, SW-bound", "VHF 11", [[51.383333, 1.45], [51.083333, 2.55]], MSC85),
            ("SOUNDREP north (DK)", "VHF 73", [[56.109667, 12.183333], [56.233333, 12.183333]], MSC314),
            ("SOUNDREP north (SE)", "VHF 73", [[56.301333, 12.289833], [56.301333, 12.448]], MSC314),
            ("SOUNDREP south", "VHF 71", [[55.290667, 12.454667], [55.166667, 12.454667], [55.166667, 12.908333]], MSC314),
            ("SOUNDREP east", "VHF 71", [[55.166667, 12.908333], [55.3815, 13.032167]], MSC314),
            ("SOUNDREP west", "VHF 71", [[55.330167, 12.455], [55.554667, 12.592167]], MSC314),
        ],
        "meridians": [],
        "parallels": [("SOUNDREP sector 1/2 (channel change)", "VHF 73 / 71", 55.833333, (12.5, 13.0), MSC314)],
        "pilots": [
            ("Sound pilot (southbound) Lt buoy M1, Helsingborg", [56.116667, 12.528333], SJO),
            ("Sound pilot (southbound) Malmo road Lt buoy", [55.641667, 12.95], SJO),
            ("Sound pilot (northbound) Trelleborg road", [55.333333, 13.133333], SJO),
            ("Sound pilot (northbound) 3 NM SSW Flintrannan SW", [55.47, 12.716667], SJO),
            ("Malmo Centralhamnen pilot, abeam Malmo Redd buoy (VHF 82)", [55.644, 12.948333], SJO),
            ("Malmo Oljehamn pilot, W of Vikhog W-card buoy (VHF 82)", [55.71, 12.895], SJO),
        ],
    },
    "med": {
        "lines": [],
        "meridians": [
            ("GIBREP Tarifa Traffic, westbound", "VHF 10", -5.25, (35.7, 36.3), MSC300),
            ("GIBREP Tangier Traffic, eastbound", "VHF 69", -5.966667, (35.6, 36.3), MSC300),
        ],
        "parallels": [],
        "pilots": [],
    },
}


def crossing(land, a, b):
    """the longest stretch of water on the segment a-b (lon, lat) between two coasts"""
    from shapely.geometry import LineString
    seg = LineString([a, b]).difference(land)
    parts = list(getattr(seg, "geoms", [seg]))
    parts = [p for p in parts if p.length > 0]
    if not parts: return None
    best = max(parts, key=lambda p: p.length)
    return [[round(x, 5), round(y, 5)] for x, y in best.coords]


def vts(pid):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from osm_seamarks import pack_land
    cf = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", f"ecdis_{pid}_chart.gz")
    js = json.load(gzip.open(cf)); F = js.setdefault("feat", {}); D = VTS[pid]
    for k in ("obj", "lines", "areas"): F[k] = [x for x in F.get(k, []) if x.get("src") != "vts"]
    land = pack_land(f"ecdis_{pid}_chart.gz") if (D["meridians"] or D["parallels"]) else None
    def line(name, ch, pts, src, why):
        F["lines"].append(dict(c="RDOCAL", pts=pts, name=name, src="vts", att={"OBJNAM": name, "COMCHA": ch, "SORIND": src}, why=why))
    for name, ch, ll, src in D["lines"]:
        line(name, ch, [[round(lon, 6), round(lat, 6)] for lat, lon in ll], src, f"Reporting line ({src}): report to the VTS on {ch} when crossing it.")
    for name, ch, lon, (la0, la1), src in D["meridians"]:
        pts = crossing(land, (lon, la0), (lon, la1))
        if pts: line(name, ch, pts, src, f"Reporting / sector line on the meridian {lon:.4f} ({src}): report or change to {ch} when crossing it. Drawn from coast to coast.")
    for name, ch, lat, (lo0, lo1), src in D["parallels"]:
        pts = crossing(land, (lo0, lat), (lo1, lat))
        if pts: line(name, ch, pts, src, f"Sector line on the parallel {lat:.4f} ({src}): change to {ch} when crossing it. Drawn from coast to coast.")
    for name, (lat, lon), src in D["pilots"]:
        F.setdefault("obj", []).append(dict(c="PILBOP", lon=round(lon, 6), lat=round(lat, 6), name=name, src="vts",
                                            att={"OBJNAM": name, "CATPIL": "pilot boarding place", "SORIND": src},
                                            why="Pilot boarding place (published position): arrive at the agreed time, make a lee and rig the pilot ladder correctly."))
    with gzip.open(cf, "wb", compresslevel=9) as f: f.write(json.dumps(js, separators=(",", ":")).encode())
    n = sum(1 for l in F["lines"] if l.get("src") == "vts"); m = sum(1 for o in F["obj"] if o.get("src") == "vts")
    print(f"  {pid}: {n} VTS reporting/sector lines, {m} pilot boarding places")


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) == 2 and a[0] == "irtc": irtc(a[1])
    elif len(a) >= 2 and a[0] == "vts": [vts(p) for p in a[1:]]
    else: print(__doc__)
