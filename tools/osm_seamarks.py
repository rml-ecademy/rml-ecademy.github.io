#!/usr/bin/env python3
"""ECADEMY ECDIS · real OpenSeaMap seamarks for a chart pack.

Fetches OpenStreetMap / OpenSeaMap `seamark:*` objects (buoys, beacons, lights, TSS, anchorages,
wrecks, rocks, obstructions, pilot boarding places) from the Overpass API and converts them to the
chart-pack feature schema read by the ECDIS trainer (feat.obj / feat.areas / feat.lines).
Inside each real-data box the simulated aids, dangers and areas are removed and replaced.

Data: (c) OpenStreetMap contributors, ODbL. Training use only, NOT for navigation.

usage:
  python3 -I osm_seamarks.py fetch  <area-id>             # download (cache in tools/osm_cache/)
  python3 -I osm_seamarks.py patch  <area-id> <chart.gz>  # put the real seamarks into an existing pack
gen_pack.py calls apply_real_seamarks() automatically for regions listed in AREAS.
"""
import json, gzip, math, os, sys, time, urllib.parse, urllib.request
from shapely.geometry import Polygon, LineString, Point, box
from shapely.ops import unary_union, polygonize

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "osm_cache")
MIRRORS = ["https://overpass-api.de/api/interpreter", "https://overpass.private.coffee/api/interpreter", "https://overpass.kumi.systems/api/interpreter"]   # main server first, then mirrors
UA = "ecademy-ecdis-pack-generator/1.0"

# real-data areas: id -> (region id in gen_pack, bbox lon0, lat0, lon1, lat1, label)
AREAS = {
    "sgstrait": dict(region="sea", bb=(103.35, 1.05, 104.55, 1.50), name="Singapore Strait"),
    # Sumatra / Peninsular Malaysia: One Fathom Bank TSS, Port Klang, Penang, Dumai, Belawan, Malacca; stops where sgstrait starts
    "malacca": dict(region="sea", bb=(98.0, 0.9, 103.349, 6.6), name="Malacca Strait", tile=0.75, land_from="ecdis_sea_chart.gz",
                    axis=[(98.3, 5.9), (100.3, 3.4), (101.3, 2.6), (102.3, 1.9), (103.35, 1.2)]),   # traffic route through the strait
    # Philippines pack (hand-built Manila-Cebu features in the trainer; real seamarks replace them inside these boxes)
    "manila": dict(region="ph", bb=(120.4, 14.15, 121.1, 14.85), name="Manila Bay", tile=0.75, land_from="ecdis_chart.gz"),
    "verde": dict(region="ph", bb=(120.5, 13.35, 121.7, 13.95), name="Verde Island Passage", tile=0.75, land_from="ecdis_chart.gz"),
    "cebu": dict(region="ph", bb=(123.6, 10.05, 124.2, 10.6), name="Cebu and Mactan", tile=0.75, land_from="ecdis_chart.gz"),
    # North-West Europe pack
    "dover": dict(region="nweu", bb=(0.8, 50.6, 2.3, 51.45), name="Dover Strait", tile=0.75, land_from="ecdis_nweu_chart.gz"),
    # other major straits (each in the pack that covers it; Suez and Gibraltar are also inside a neighbouring pack's box)
    "hormuz": dict(region="gulf", bb=(55.8, 25.8, 57.2, 27.0), name="Strait of Hormuz", tile=0.75, land_from="ecdis_gulf_chart.gz"),
    "babelmandeb": dict(region="gulf", bb=(42.9, 12.2, 43.8, 13.2), name="Bab-el-Mandeb", tile=0.75, land_from="ecdis_gulf_chart.gz"),
    "suez": dict(region="gulf", bb=(32.2, 29.85, 32.65, 31.35), name="Suez Canal and Gulf of Suez", tile=0.75, land_from="ecdis_gulf_chart.gz"),
    "gibraltar": dict(region="med", bb=(-6.1, 35.75, -5.2, 36.2), name="Strait of Gibraltar", tile=0.75, land_from="ecdis_med_chart.gz"),
    "bosporus": dict(region="med", bb=(28.9, 40.95, 29.2, 41.3), name="Bosporus", tile=0.75, land_from="ecdis_med_chart.gz"),
    "dardanelles": dict(region="med", bb=(26.1, 40.0, 26.7, 40.5), name="Dardanelles", tile=0.75, land_from="ecdis_med_chart.gz"),
    "messina": dict(region="med", bb=(15.5, 37.9, 15.75, 38.3), name="Strait of Messina", tile=0.75, land_from="ecdis_med_chart.gz"),
    "oresund": dict(region="nweu", bb=(12.4, 55.4, 13.0, 56.15), name="Oresund", tile=0.75, land_from="ecdis_nweu_chart.gz"),
    "korea": dict(region="ea", bb=(128.7, 34.6, 129.5, 35.3), name="Korea Strait (Busan)", tile=0.75, land_from="ecdis_ea_chart.gz"),
    "sunda": dict(region="sea", bb=(105.0, -6.6, 106.3, -5.5), name="Sunda Strait", tile=0.75, land_from="ecdis_sea_chart.gz"),
    "lombok": dict(region="sea", bb=(115.4, -9.0, 116.1, -8.2), name="Lombok Strait", tile=0.75, land_from="ecdis_sea_chart.gz"),
    "torres": dict(region="aus", bb=(141.8, -11.0, 143.0, -9.8), name="Torres Strait", tile=0.75, land_from="ecdis_aus_chart.gz"),
}
SRC = "OpenStreetMap / OpenSeaMap (ODbL)"

# ----------------------------------------------------------------------------- fetch
def fetch(aid, refresh=False):
    A = AREAS[aid]; lo0, la0, lo1, la1 = A["bb"]
    fn = os.path.join(CACHE, f"{aid}.json.gz")
    if os.path.exists(fn) and not refresh:
        return json.load(gzip.open(fn))
    T = A.get("tile")
    if T:   # big area: one Overpass query per tile, merged (an object on a tile edge is kept once)
        seen, els, base = set(), [], ""
        land = pack_land(A["land_from"]) if A.get("land_from") else None
        tiles = []
        lo = lo0
        while lo < lo1 - 1e-9:
            la = la0
            while la < la1 - 1e-9:
                tb = (round(lo, 3), round(la, 3), round(min(lo + T, lo1), 3), round(min(la + T, la1), 3))
                if land is None or box(*tb).difference(land).area >= 0.005 * box(*tb).area: tiles.append(tb)   # all land in the pack: skipped
                la += T
            lo += T
        if A.get("axis"):   # fetch the main shipping corridor first
            ax = LineString(A["axis"]); tiles.sort(key=lambda tb: ax.distance(box(*tb)))
        for tb in tiles:
            tf = os.path.join(CACHE, "tiles", f"{aid}_{tb[0]}_{tb[1]}.json.gz")
            if os.path.exists(tf): js = json.load(gzip.open(tf))           # resume an interrupted download
            else:
                js = query(tb); os.makedirs(os.path.dirname(tf), exist_ok=True)
                with gzip.open(tf, "wt") as f: json.dump(js, f, separators=(",", ":"))
            b = js.get("osm3s", {}).get("timestamp_osm_base", "")
            base = min(base, b) if base and b else (base or b)          # mirrors differ: keep the oldest snapshot date
            for e in js["elements"]:
                if (e["type"], e["id"]) not in seen: seen.add((e["type"], e["id"])); els.append(e)
        js = {"osm3s": {"timestamp_osm_base": base, "copyright": "OpenStreetMap contributors, ODbL"}, "elements": els}
    else:
        js = query(A["bb"])
    os.makedirs(CACHE, exist_ok=True)
    with gzip.open(fn, "wt") as f: json.dump(js, f, separators=(",", ":"))
    print(f"  {aid}: {len(js['elements'])} seamark elements (OSM base {js['osm3s'].get('timestamp_osm_base', '?')})")
    return js

def pack_land(name):
    """land of an existing chart pack (overview rings, NM grid) as lon/lat polygons"""
    j = json.load(gzip.open(os.path.join(HERE, "..", "assets", name)))
    ps = []
    for r in j["general"]:
        pts = [(j["lon0"] + r[i] / (60 * j["C"]), j["lat0"] + r[i + 1] / 60) for i in range(0, len(r) - 1, 2)]
        if len(pts) >= 3:
            p = Polygon(pts).buffer(0)
            if not p.is_empty: ps.append(p)
    return unary_union(ps)

def query(bb):
    lo0, la0, lo1, la1 = bb
    q = f'[out:json][timeout:240];nwr["seamark:type"]({la0},{lo0},{la1},{lo1});out body geom;'
    data = urllib.parse.urlencode({"data": q}).encode()
    last = None
    for attempt in range(5):
        for url in MIRRORS:
            try:
                req = urllib.request.Request(url, data=data, headers={"User-Agent": UA})
                with urllib.request.urlopen(req, timeout=300) as r: js = json.loads(r.read())
                if "elements" not in js: raise ValueError("no elements in reply")
                if "error" in js.get("remark", "").lower(): raise ValueError("overpass: " + js["remark"][:120])   # timeout/out-of-memory: partial reply
                print(f"  overpass {bb}: {len(js['elements'])} elements from {url.split('/')[2]}")
                return js
            except Exception as e:
                last = e; print(f"  overpass {url.split('/')[2]}: {e}")
        time.sleep(10 * (attempt + 1))
    raise RuntimeError(f"Overpass download failed: {last}")

# ----------------------------------------------------------------------------- helpers
COL = {"white": "W", "red": "R", "green": "G", "yellow": "Y", "blue": "Bu", "orange": "Or", "violet": "Vi", "amber": "Am"}

def num(v):
    try: return float(str(v).replace(",", ".").split(";")[0])
    except (TypeError, ValueError): return None

def fmt(v):
    return ("%g" % v) if v is not None else ""

def light_chr(t, pre="seamark:light:"):
    """List-of-Lights style character, e.g. 'Fl(3) W 15s 15M'"""
    ch = t.get(pre + "character")
    if not ch: return ""
    grp = t.get(pre + "group"); per = num(t.get(pre + "period")); rng = num(t.get(pre + "range"))
    cols = "".join(COL.get(c.strip(), "") for c in t.get(pre + "colour", "").split(";"))
    s = ch + (f"({grp})" if grp else "")
    if cols: s += " " + cols
    if per: s += f" {fmt(per)}s"
    if rng: s += f" {fmt(rng)}M"
    return s.strip()

def lights_of(t):
    """the light(s) on an object: plain seamark:light:* or numbered seamark:light:N:*"""
    out = []
    if t.get("seamark:light:character"): out.append("seamark:light:")
    k = 1
    while any(x.startswith(f"seamark:light:{k}:") for x in t): out.append(f"seamark:light:{k}:"); k += 1
    return out

def first_col(t, pre):
    c = t.get(pre + "colour", "white").split(";")[0].strip()
    return {"white": "W", "red": "R", "green": "G", "yellow": "Y"}.get(c, "W")

def centroid(e):
    g = e.get("geometry")
    if e["type"] == "node": return e["lon"], e["lat"]
    if g:
        pts = [(p["lon"], p["lat"]) for p in g]
        c = (Polygon(pts) if len(pts) >= 4 and pts[0] == pts[-1] else LineString(pts)).centroid if len(pts) > 1 else Point(pts[0])
        return c.x, c.y
    b = e.get("bounds")
    if b: return (b["minlon"] + b["maxlon"]) / 2, (b["minlat"] + b["maxlat"]) / 2
    return None

def rings(e):
    """closed rings (lon,lat) of a way or multipolygon relation (outer members joined)"""
    if e["type"] == "way":
        g = [(p["lon"], p["lat"]) for p in e.get("geometry", [])]
        return [g] if len(g) >= 4 and g[0] == g[-1] else []
    if e["type"] == "relation":
        seg = lambda roles: [LineString([(p["lon"], p["lat"]) for p in m["geometry"]]) for m in e.get("members", []) if m.get("role") in roles and m.get("geometry") and len(m["geometry"]) > 1]
        outer = list(polygonize(unary_union(seg(("outer", ""))))); inner = list(polygonize(unary_union(seg(("inner",))))) if seg(("inner",)) else []
        out = []
        for o in outer:
            g = o.difference(unary_union(inner)) if inner else o
            out += [list(p.exterior.coords) for p in no_holes(g)]
        return out
    return []

def no_holes(g):
    """the renderer has no polygon holes: cut a holed polygon across each hole until no holes remain"""
    from shapely.ops import split
    todo = list(getattr(g, "geoms", [g])); done = []
    while todo:
        p = todo.pop()
        if p.geom_type != "Polygon" or p.is_empty: continue
        if not p.interiors: done.append(p); continue
        hc = Polygon(p.interiors[0]).centroid; x0, y0, x1, y1 = p.bounds
        todo += [q for q in split(p, LineString([(hc.x, y0 - 1), (hc.x, y1 + 1)])).geoms]
    return done

def line_pts(e):
    if e["type"] == "way": return [(p["lon"], p["lat"]) for p in e.get("geometry", [])]
    return []

def brg(a, b):
    """true bearing a->b (lon/lat, small distances)"""
    C = math.cos(math.radians((a[1] + b[1]) / 2))
    return (math.degrees(math.atan2((b[0] - a[0]) * C, b[1] - a[1])) + 360) % 360

r5 = lambda v: round(float(v), 5)
pt5 = lambda p: [r5(p[0]), r5(p[1])]

# ----------------------------------------------------------------------------- convert
CAT_LAT = {"port": "can", "starboard": "cone", "preferred_channel_starboard": "can", "preferred_channel_port": "cone"}
CARD = {"north": "N", "east": "E", "south": "S", "west": "W"}

def convert(js, iala="A", bb=None):
    obj, areas, lines = [], [], []
    els = js["elements"]
    inside = (lambda lo, la: bb[0] <= lo <= bb[2] and bb[1] <= la <= bb[3]) if bb else (lambda lo, la: True)

    def add(c, e, **k):
        p = centroid(e)
        if not p or not inside(*p): return
        t = e["tags"]
        d = dict(c=c, lon=r5(p[0]), lat=r5(p[1]))
        d.update(k)
        att = d.setdefault("att", {})
        if t.get("seamark:name"): att.setdefault("OBJNAM", t["seamark:name"])
        att["SORIND"] = f"{SRC}, {e['type']} {e['id']}"
        if t.get("seamark:light:reference"): att["LITREF"] = t["seamark:light:reference"]
        d["src"] = "osm"
        obj.append(d)

    for e in els:
        t = e.get("tags", {}); ty = t.get("seamark:type", "")
        nm = t.get("seamark:name", "")
        lts = lights_of(t); chr_ = light_chr(t, lts[0]) if lts else ""
        litatt = {"LITCHR": chr_} if chr_ else {}
        kind = ty.split("_", 1)[0]                       # buoy / beacon / light ...
        sub = ty.split("_", 1)[1] if "_" in ty else ""
        bn = kind == "beacon"
        if ty in ("buoy_lateral", "beacon_lateral"):
            cat = t.get(f"seamark:{ty}:category", "")
            shape = CAT_LAT.get(cat)
            if not shape: continue
            side = "port" if shape == "can" else "starboard"
            pref = cat.startswith("preferred")
            add("BOYLAT", e, name=nm or f"{side.title()}-hand {'beacon' if bn else 'buoy'}", shape=shape, chr=chr_, bn=bn,
                att={"CATLAM": cat.replace("_", " ") if pref else f"{side}-hand", "BOYSHP" if not bn else "BCNSHP": t.get(f"seamark:{ty}:shape", ""), "COLOUR": t.get(f"seamark:{ty}:colour", "").replace(";", "/"), "MARSYS": t.get(f"seamark:{ty}:system", f"iala-{iala.lower()}").upper().replace("IALA-", "IALA "), **litatt},
                why=(f"Preferred-channel mark: the main channel is on the other side; treat it as a {side}-hand mark when following the main channel." if pref else
                     f"{side.title()}-hand lateral mark (IALA {iala}): following the direction of buoyage, keep it on your {side.upper()} side."))
        elif ty in ("buoy_cardinal", "beacon_cardinal"):
            card = CARD.get(t.get(f"seamark:{ty}:category", ""))
            if not card: continue
            opp = {"N": "south", "E": "west", "S": "north", "W": "east"}[card]
            add("BOYCAR", e, name=nm or f"{card} cardinal {'beacon' if bn else 'buoy'}", card=card, shape="pillar", chr=chr_, bn=bn,
                att={"CATCAM": {"N": "north", "E": "east", "S": "south", "W": "west"}[card] + " cardinal", "COLOUR": t.get(f"seamark:{ty}:colour", "black;yellow").replace(";", "/"), **litatt},
                why=f"{card} cardinal mark: the safest water is to the {card} of it; the danger lies to the {opp}. Pass on its {card} side.")
        elif ty in ("buoy_isolated_danger", "beacon_isolated_danger"):
            add("BOYISD", e, name=nm or f"Isolated danger {'beacon' if bn else 'buoy'}", shape="pillar", chr=chr_, bn=bn,
                att={"CATSPM": "isolated danger", "COLOUR": "black/red/black", **litatt}, why="Isolated danger mark: erected on a danger with navigable water all round. Do not pass close.")
        elif ty in ("buoy_safe_water", "beacon_safe_water"):
            add("BOYSAW", e, name=nm or "Safe-water mark", shape="sph", chr=chr_, bn=bn,
                att={"CATSPM": "safe water", "COLOUR": "red/white", **litatt}, why="Safe-water mark: navigable water all round; marks a fairway, mid-channel or landfall.")
        elif ty in ("buoy_special_purpose", "beacon_special_purpose"):
            cat = t.get(f"seamark:{ty}:category", "").replace("_", " ")
            add("BOYSPP", e, name=nm or f"Special mark{(' (' + cat + ')') if cat else ''}", chr=chr_, bn=bn, scamin=180000,
                att={"CATSPM": cat or "special purpose", "COLOUR": t.get(f"seamark:{ty}:colour", "yellow").replace(";", "/"), **litatt},
                why="Special mark (yellow): not primarily a navigation mark. It shows a special area or feature (spoil ground, cable, outfall, recreation zone, boundary). Check the chart and Sailing Directions.")
        elif ty in ("light_major", "light_minor", "light", "light_vessel", "light_float"):
            if not chr_: continue
            major = ty in ("light_major", "light_vessel")
            secs = []
            for pre in lts:
                a, b = num(t.get(pre + "sector_start")), num(t.get(pre + "sector_end"))
                if a is not None and b is not None and a != b: secs.append(dict(a=a % 360, b=b % 360, col=first_col(t, pre)))
            ht, rg = num(t.get(lts[0] + "height")), num(t.get(lts[0] + "range"))
            d = dict(name=nm or ("Light" if not major else "Lighthouse"), chr=chr_, col=first_col(t, lts[0]), major=major,
                     att={"CATLIT": t.get("seamark:light:category", "major light" if major else "minor light").replace("_", " "), "LITCHR": chr_, "COLOUR": t.get(lts[0] + "colour", "white").replace(";", "/"),
                          **({"HEIGHT": f"{fmt(ht)} m"} if ht else {}), **({"VALNMR": f"{fmt(rg)} M"} if rg else {})},
                     why=("Major light: identify it by its character and check it against the List of Lights. Use it for a visual bearing or range." if major else
                          "Minor light: harbour, pier or channel light. Check its character to identify it."))
            if secs: d["sectors"] = secs; d["why"] += " Sector light: the colour you see tells you which sector you are in."
            if not major: d["scamin"] = 260000
            add("LIGHTS", e, **d)
        elif ty == "wreck":
            cat = t.get("seamark:wreck:category", "")
            z = num(t.get("seamark:wreck:valsou") or t.get("seamark:wreck:depth"))
            safe = cat in ("non-dangerous", "distributed_remains")
            add("WRECKS", e, name=nm or ("Wreck" if not safe else "Wreck (non-dangerous)"), depth=z, safe=safe, scamin=None if not safe else 350000,
                att={"CATWRK": cat.replace("_", " ") or "unknown", "VALSOU": f"{fmt(z)} m" if z is not None else "unknown"},
                why=("Non-dangerous wreck: you can pass over it, but do not anchor or trawl here." if safe else
                     "Dangerous wreck" + (f", {fmt(z)} m over it" if z is not None else ", depth unknown") + ": treat it as a danger to navigation and keep clear."))
        elif ty == "rock":
            z = num(t.get("seamark:rock:valsou")); wl = t.get("seamark:rock:water_level", "").replace("_", " ")
            add("UWTROC", e, name=nm or "Rock", depth=z, cat="base", scamin=260000,
                att={"VALSOU": f"{fmt(z)} m" if z is not None else "unknown", "WATLEV": wl or "unknown", "NATSUR": "rock"},
                why="Rock" + (f" ({wl})" if wl else "") + ": a danger to navigation. Keep well clear.")
        elif ty == "obstruction":
            z = num(t.get("seamark:obstruction:valsou")); cat = t.get("seamark:obstruction:category", "").replace("_", " ")
            add("OBSTRN", e, name=nm or ("Obstruction" + (f" ({cat})" if cat else "")), depth=z, scamin=120000,
                att={"CATOBS": cat or "obstruction", "VALSOU": f"{fmt(z)} m" if z is not None else "unknown"},
                why="Obstruction: do not anchor or trawl here; check the least depth.")
        elif ty == "pilot_boarding":
            add("PILBOP", e, name=nm or "Pilot boarding place", att={"CATPIL": t.get("seamark:pilot_boarding:category", "").replace("_", " ") or "pilot boarding place", "COMCHA": t.get("seamark:pilot_boarding:channel", "")},
                why="Pilot boarding place: arrive at the agreed time, make a lee and rig the pilot ladder correctly.")
        elif ty == "anchorage":
            for rg_ in rings(e):
                c = Polygon(rg_).centroid
                if not inside(c.x, c.y): continue
                cat = t.get("seamark:anchorage:category", "").replace("_", " ")
                areas.append(dict(c="ACHARE", ring=[pt5(p) for p in rg_[:-1]], name=nm or "Anchorage", src="osm",
                                  att={"OBJNAM": nm, "CATACH": cat or "anchorage", "SORIND": f"{SRC}, {e['type']} {e['id']}"},
                                  why="Designated anchorage" + (f" ({nm})" if nm else "") + ": anchor only in the anchorage meant for your vessel type, as given in the port regulations."))
        elif ty == "separation_zone":
            for rg_ in rings(e):
                c = Polygon(rg_).centroid
                if not inside(c.x, c.y): continue
                areas.append(dict(c="TSEZNE", ring=[pt5(p) for p in rg_[:-1]], name=nm or "TSS separation zone", src="osm",
                                  att={"CATTSS": "separation zone", "SORIND": f"{SRC}, {e['type']} {e['id']}"},
                                  why="Separation zone: do not enter it except to cross, in an emergency or to fish within it (COLREG Rule 10)."))
        elif ty in ("separation_line", "separation_boundary"):
            p = line_pts(e)
            if len(p) < 2 or not any(inside(*q) for q in p): continue
            lines.append(dict(c="TSELNE" if ty == "separation_line" else "TSSBND", pts=[pt5(q) for q in p], name="TSS separation line" if ty == "separation_line" else "TSS boundary", src="osm",
                              att={"SORIND": f"{SRC}, way {e['id']}"},
                              why="Separation line: it divides the traffic lanes of opposite direction. Keep to the lane on your starboard side (Rule 10)." if ty == "separation_line" else
                                  "Outer boundary of the traffic separation scheme. Join or leave a lane at its termination, or from the side at as small an angle as practicable (Rule 10)."))
    lanes = build_lanes(els, inside)
    areas.extend(lanes)
    return dict(obj=obj, areas=areas, lines=lines)

def build_lanes(els, inside):
    """traffic lanes as polygons: faces formed by the TSS boundaries, separation lines and zones that
    contain an OSM `separation_lane` direction line; orient = its direction (OSM way direction = traffic flow)"""
    work, zones, arrows = [], [], []
    for e in els:
        t = e.get("tags", {}); ty = t.get("seamark:type", "")
        if ty in ("separation_boundary", "separation_line") and e["type"] == "way":
            p = line_pts(e)
            if len(p) >= 2: work.append(LineString(p))
        elif ty == "separation_zone":
            for rg_ in rings(e): work.append(LineString(rg_)); zones.append(Polygon(rg_))
        elif ty == "separation_lane" and e["type"] == "way":
            p = line_pts(e)
            if len(p) >= 2: arrows.append(p)
    if not work or not arrows: return []
    faces = list(polygonize(unary_union(work)))
    zu = unary_union(zones).buffer(1e-6) if zones else None
    out = []
    for f in faces:
        if zu is not None and zu.contains(f.representative_point()): continue
        inA = []
        for p in arrows:
            for a, b in zip(p, p[1:]):
                m = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
                if f.contains(Point(m)): inA.append((m, brg(a, b), math.hypot((b[0] - a[0]) * math.cos(math.radians(m[1])), b[1] - a[1])))
        c = f.centroid
        if not inside(c.x, c.y): continue
        if not inA: continue           # direction not mapped in OSM: no lane (never guessed)
        # dominant direction (length-weighted circular mean)
        sx = sum(w * math.sin(math.radians(b)) for _, b, w in inA); sy = sum(w * math.cos(math.radians(b)) for _, b, w in inA)
        orient = (math.degrees(math.atan2(sx, sy)) + 360) % 360
        ring = list(f.simplify(0.0002, preserve_topology=True).exterior.coords)[:-1]
        L = max(LineString(list(f.minimum_rotated_rectangle.exterior.coords)).length / 2 * 60 * 0.5, 1.0)   # rough NM
        out.append(dict(c="TSSLPT", ring=[pt5(p) for p in ring], name=f"Traffic lane {round(orient):03d}°", orient=round(orient), len=round(L, 1), src="osm",
                        arrows=[[r5(m[0]), r5(m[1]), round(b)] for m, b, _ in inA],
                        att={"ORIENT": f"{round(orient):03d}°", "CATTSS": "traffic lane", "SORIND": SRC + " (lane outline from the TSS boundary and separators; direction from OSM separation_lane)"},
                        why="Traffic lane: proceed in the general direction of traffic flow shown by the arrows (COLREG Rule 10). Join or leave at a termination, or from the side at a small angle."))
    return out

# ----------------------------------------------------------------------------- apply to a pack
SIM_OBJ = {"LIGHTS", "BOYLAT", "BOYCAR", "BOYSAW", "BOYISD", "BOYSPP", "PILBOP", "WRECKS", "OBSTRN", "UWTROC"}
SIM_AREA = {"ACHARE", "PRCARE", "TSEZNE", "TSSLPT"}
SIM_LINE = {"RDOCAL"}

def apply_real_seamarks(feat, aid, js=None, iala="A", cover=None):
    """remove the simulated aids/dangers/areas inside the area box (or only inside `cover`, the tiles
    downloaded so far, for a partial update), then add the real OSM seamarks"""
    A = AREAS[aid]; bb = A["bb"]; B = box(*bb) if cover is None else cover
    js = js or fetch(aid)
    inb = (lambda lo, la: bb[0] <= lo <= bb[2] and bb[1] <= la <= bb[3]) if cover is None else (lambda lo, la: cover.covers(Point(lo, la)))
    n0 = len(feat["obj"])
    feat["obj"] = [o for o in feat["obj"] if o.get("src") or not (o["c"] in SIM_OBJ and inb(o["lon"], o["lat"]))]   # never remove real data of another area
    def area_in(a):
        if a.get("circle"): return inb(a["circle"][0], a["circle"][1])
        return Polygon(a["ring"]).intersects(B)
    feat["areas"] = [a for a in feat["areas"] if a.get("src") or not (a["c"] in SIM_AREA and area_in(a))]
    feat["lines"] = [l for l in feat["lines"] if l.get("src") or not (l["c"] in SIM_LINE and any(inb(*p) for p in l["pts"]))]
    removed = n0 - len(feat["obj"])
    R = convert(js, iala, bb)
    have = {x["att"].get("SORIND") for k in ("obj", "areas", "lines") for x in feat[k] if x.get("src") == "osm"}
    R["lines"] = [l for l in R["lines"] if l["att"]["SORIND"] not in have]      # a TSS line crossing into a neighbouring area is kept once
    for k in ("obj", "areas", "lines"):
        for x in R[k]: x["osm"] = aid
        feat[k].extend(R[k])
    feat.setdefault("real", []).append(dict(id=aid, name=A["name"], bb=list(bb), src=SRC, osm=js.get("osm3s", {}).get("timestamp_osm_base", ""), **({"partial": True} if cover is not None else {})))
    from collections import Counter
    print(f"  real seamarks {A['name']}: removed {removed} simulated objects; added {len(R['obj'])} objects {dict(Counter(o['c'] for o in R['obj']))}, "
          f"{len(R['areas'])} areas {dict(Counter(a['c'] for a in R['areas']))}, {len(R['lines'])} lines")
    return R

credit = lambda names: f" Real aids to navigation, lights, TSS, anchorages and wrecks in the {names}: OpenStreetMap / OpenSeaMap contributors (ODbL), training use only."

def partial_tiles(aid):
    """the tiles of an unfinished tiled download: merged elements and the area they cover"""
    A = AREAS[aid]; T = A["tile"]; seen, els, boxes, base = set(), [], [], ""
    for fn in sorted(os.listdir(os.path.join(CACHE, "tiles"))):
        if not fn.startswith(aid + "_"): continue
        try: js = json.load(gzip.open(os.path.join(CACHE, "tiles", fn)))
        except Exception: continue                                   # being written right now
        lo, la = map(float, fn[len(aid) + 1:-len(".json.gz")].split("_"))
        boxes.append(box(lo, la, min(lo + T, A["bb"][2]), min(la + T, A["bb"][3])))
        b = js.get("osm3s", {}).get("timestamp_osm_base", ""); base = min(base, b) if base and b else (base or b)
        for e in js["elements"]:
            if (e["type"], e["id"]) not in seen: seen.add((e["type"], e["id"])); els.append(e)
    print(f"  {aid}: partial, {len(boxes)} tiles, {len(els)} elements")
    return {"osm3s": {"timestamp_osm_base": base}, "elements": els}, unary_union(boxes)

def patch(aid, chart_gz, partial=False):
    js = json.load(gzip.open(chart_gz))
    js.setdefault("feat", {"obj": [], "areas": [], "lines": []})       # the Philippines pack keeps its own features in the trainer
    for k in ("obj", "areas", "lines"): js["feat"].setdefault(k, [])
    iala = js.get("iala") or ("B" if AREAS[aid]["region"] == "ph" else "A")
    for k in ("obj", "areas", "lines"):                                                  # idempotent re-run of this area
        js["feat"][k] = [x for x in js["feat"][k] if not (x.get("src") == "osm" and x.get("osm") == aid)]
    js["feat"]["real"] = [r for r in js["feat"].get("real", []) if r["id"] != aid]
    if partial:
        osm, cover = partial_tiles(aid); apply_real_seamarks(js["feat"], aid, js=osm, iala=iala, cover=cover)
    else: apply_real_seamarks(js["feat"], aid, iala=iala)
    names = " and ".join(r["name"] for r in js["feat"]["real"])
    if "desc" in js: js["desc"] = js["desc"].split(" · real OpenSeaMap")[0] + " · real OpenSeaMap seamarks (buoys, lights, TSS, anchorages, wrecks) in the " + names
    if "credit" in js: js["credit"] = js["credit"].split(" Singapore Strait aids")[0].split(" Real aids")[0].replace(" Depths, aids", " Depths, other aids") + credit(names)
    with gzip.open(chart_gz, "wb", compresslevel=9) as f: f.write(json.dumps(js, separators=(",", ":")).encode())
    print(f"  wrote {chart_gz} {os.path.getsize(chart_gz) / 1e6:.2f} MB")

if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) >= 2 and a[0] == "fetch": fetch(a[1], refresh=True)
    elif len(a) >= 3 and a[0] == "patch": patch(a[1], a[2])
    elif len(a) >= 3 and a[0] == "patch-partial": patch(a[1], a[2], partial=True)   # tiles downloaded so far
    else: print(__doc__)
