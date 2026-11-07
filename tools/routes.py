#!/usr/bin/env python3
"""ECADEMY ECDIS · published routeing measures that are not in OpenSeaMap, added to a chart pack.

IRTC, Gulf of Aden (Internationally Recommended Transit Corridor), from IMO SN.1/Circ.281 and the MSCHOA
/ BMP corridor description: two 5 NM lanes with a 2 NM buffer between them.
  eastbound lane (south): 045°00'E 11°48'N-11°53'N  ->  053°00'E 14°18'N-14°23'N, course 072°
  westbound lane (north): 053°00'E 14°25'N-14°30'N  ->  045°00'E 11°55'N-12°00'N, course 252°
It is a recommended transit corridor, not a traffic separation scheme. Training use only: check the current
BMP edition, UKHO chart Q6099 and MSCHOA before relying on it.

usage: python3 -I routes.py irtc <chart.gz>      # e.g. assets/ecdis_gulf_chart.gz (idempotent)
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


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) == 2 and a[0] == "irtc": irtc(a[1])
    else: print(__doc__)
