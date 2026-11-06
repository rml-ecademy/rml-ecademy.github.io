"""copy generated packs + manifest into the repo, encrypt the ECDIS trainer"""
import json, gzip, os, shutil, subprocess, sys
sys.path.insert(0, "/home/claude/work")
from gen_pack import REGIONS
OUT, REPO = "/home/claude/work/out_all", "/home/claude/ecademy"
GROUP = {"sea": "Asia", "ea": "Asia", "ina": "Asia", "ruse": "Asia", "gulf": "Middle East & Africa", "wafr": "Middle East & Africa", "safr": "Middle East & Africa",
         "med": "Europe", "nweu": "Europe", "aus": "Oceania", "nz": "Oceania", "usec": "Americas", "carib": "Americas", "usw": "Americas", "alsk": "Americas", "bra": "Americas", "sams": "Americas", "samw": "Americas"}
ORDER = ["sea", "ea", "ina", "ruse", "gulf", "med", "nweu", "wafr", "safr", "aus", "nz", "usec", "carib", "usw", "alsk", "bra", "sams", "samw"] + [r for r in REGIONS if REGIONS[r].get("gen")]
man = []
for rid in ORDER:
    cf, df = f"{OUT}/ecdis_{rid}_chart.gz", f"{OUT}/ecdis_{rid}_depth.gz"
    if not (os.path.exists(cf) and os.path.exists(df)): print("missing", rid); continue
    js = json.load(gzip.open(cf))
    shutil.copy(cf, f"{REPO}/assets/"); shutil.copy(df, f"{REPO}/assets/")
    man.append(dict(id=rid, gen=bool(js.get("gen")), name=js["name"], desc=js["desc"], group=GROUP.get(rid, "Worldwide general coverage"), chart=f"ecdis_{rid}_chart.gz", depth=f"ecdis_{rid}_depth.gz", cells=len(js["cells"]), start=js["start"]["port"], dest=js["dest"], mb=round((os.path.getsize(cf) + os.path.getsize(df)) / 1e6, 1)))
    if False: print(rid, man[-1]["mb"], "MB", len(js["cells"]), "cells", len(js["feat"]["obj"]), "objects", len(js["ais"]), "AIS")
json.dump(man, open(f"{REPO}/assets/ecdis_packs.json", "w"), indent=0)
json.dump(man, open("/home/claude/work/site/assets/ecdis_packs.json", "w"))
print("manifest:", len(man), "packs, total", round(sum(m["mb"] for m in man), 1), "MB")

# world basemap regions (for the coverage boxes, globe and automatic loading)
import gzip as _gz
W = json.load(_gz.open(f"{REPO}/assets/ecdis_world.gz"))
byid = {m["id"]: m for m in man}
W["regions"] = [dict(id=m["id"], name=m["name"], bb=list(REGIONS[m["id"]]["bb"]), gen=m["gen"]) for m in man] + [dict(id="ph", name="Philippines · Manila – Cebu", bb=[116.8, 4.5, 126.8, 21.2], gen=False)]
with _gz.open(f"{REPO}/assets/ecdis_world.gz", "wb", compresslevel=9) as f: f.write(json.dumps(W, separators=(",", ":")).encode())
shutil.copy(f"{REPO}/assets/ecdis_world.gz", "/home/claude/work/site/assets/")
print("world regions:", len(W["regions"]))
