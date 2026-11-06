#!/usr/bin/env python3
"""ECADEMY ECDIS · world chart-pack generator.

Builds training ENC packs (same schema as the Philippines pack read by the ECDIS trainer)
from open data: OSM-derived coastline (geo-maps, ODbL), Natural Earth bathymetry / ports /
names (public domain). Depths, aids to navigation, traffic and notices are SIMULATED, except
where real OpenSeaMap seamarks are available (tools/osm_seamarks.py: Singapore Strait).

usage: python3 -I gen_pack.py <region-id> [--out DIR]
"""
import json, gzip, math, os, sys, struct, hashlib, random, time
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage
from skimage import measure, draw
from skimage.graph import route_through_array
from shapely.geometry import shape, box, Polygon, MultiPolygon, Point, LineString, mapping
from shapely.strtree import STRtree
from shapely.ops import unary_union
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from osm_seamarks import AREAS as OSM_AREAS, apply_real_seamarks, CREDIT_ADD as OSM_CREDIT

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
LEVELS = [0, 2, 5, 10, 15, 20, 30, 50, 100, 200, 500, 1000, 2000]
BAND_LEVELS = {1: [0, 20, 50, 100, 200, 500, 1000, 2000], 2: [0, 5, 10, 20, 30, 50, 100, 200, 500, 1000, 2000],
               3: [0, 2, 5, 10, 15, 20, 30, 50, 100, 200, 500, 1000], 4: [0, 2, 5, 10, 15, 20, 30, 50, 100, 200], 5: [0, 2, 5, 10, 15, 20, 30, 50]}
LAND_Q = 104  # grid value flagging land (engine: q/10-10 = 0.4 m)

# ----------------------------------------------------------------------------- regions
# lon0, lat0, lon1, lat1 ; iala ; tz ; start port ; destination port (sample route) ; ENC prefix
REGIONS = {
  "sea":  dict(name="Singapore, Malacca Strait & Indonesia", bb=(94, -11, 121, 13), iala="A", tz=8, start="Singapore", dest="Jakarta", pfx="SE", desc="Singapore Strait, Malacca Strait, Java Sea, Gulf of Thailand, Vietnam coast"),
  "ea":   dict(name="China, Korea & Japan", bb=(114, 19, 147, 46), iala="B", tz=9, start="Busan", dest="Yokohama", pfx="EA", desc="East China Sea, Yellow Sea, Sea of Japan, Taiwan Strait"),
  "ina":  dict(name="India, Bay of Bengal & Arabian Sea", bb=(58, -2, 96, 26), iala="A", tz=5.5, start="Mumbai", dest="Colombo", pfx="IN", desc="Arabian Sea, Bay of Bengal, Sri Lanka, Andaman Sea"),
  "gulf": dict(name="Persian Gulf & Red Sea", bb=(30, 9, 63, 32), iala="A", tz=4, start="Dubai", dest="Jeddah", pfx="GF", desc="Persian Gulf, Strait of Hormuz, Gulf of Aden, Red Sea, Suez"),
  "med":  dict(name="Mediterranean & Black Sea", bb=(-9, 29, 42, 47.5), iala="A", tz=1, start="Piraeus", dest="Valencia", pfx="MD", desc="Gibraltar to the Levant, Adriatic, Aegean, Black Sea"),
  "nweu": dict(name="North-West Europe, North Sea & Baltic", bb=(-13, 47, 31, 66), iala="A", tz=1, start="Rotterdam", dest="Hamburg", pfx="NW", desc="English Channel, North Sea, Irish Sea, Baltic Sea, Norway south"),
  "wafr": dict(name="West Africa & Canary Islands", bb=(-26, -6, 16, 37), iala="A", tz=0, start="Lagos", dest="Dakar", pfx="WA", desc="Gulf of Guinea, Senegal, Morocco, Canary Islands"),
  "safr": dict(name="Southern & East Africa", bb=(9, -37, 52, 1), iala="A", tz=2, start="Durban", dest="Cape Town", pfx="SA", desc="Cape of Good Hope, Mozambique Channel, Madagascar, Mombasa"),
  "aus":  dict(name="Australia & Papua New Guinea", bb=(108, -45, 156, -8), iala="A", tz=10, start="Sydney", dest="Melbourne", pfx="AU", desc="Great Barrier Reef, Bass Strait, Torres Strait, Port Hedland"),
  "nz":   dict(name="New Zealand & South-West Pacific", bb=(158, -48, 180, -15), iala="A", tz=12, start="Auckland", dest="Wellington", pfx="NZ", desc="New Zealand, Tasman Sea, New Caledonia, Fiji (west)"),
  "usec": dict(name="US East Coast & Canada Atlantic", bb=(-84, 24, -52, 51), iala="B", tz=-5, start="New York", dest="Savannah", pfx="UE", desc="Chesapeake Bay, Delaware Bay, Boston, Halifax, Florida east coast"),
  "carib":dict(name="Gulf of Mexico & Caribbean", bb=(-100, 7, -58, 31.5), iala="B", tz=-5, start="Houston", dest="Kingston", pfx="CB", desc="Houston Ship Channel, Mississippi, Panama Canal, Caribbean islands"),
  "usw":  dict(name="US West Coast & Mexico Pacific", bb=(-132, 15, -104, 50), iala="B", tz=-8, start="Los Angeles", dest="Seattle", pfx="UW", desc="San Francisco Bay, Puget Sound, Columbia River, Baja California"),
  "alsk": dict(name="Alaska & British Columbia", bb=(-172, 48, -124, 72), iala="B", tz=-9, start="Vancouver", dest="Anchorage", pfx="AK", desc="Inside Passage, Gulf of Alaska, Aleutian Islands, Bering Sea"),
  "bra":  dict(name="Brazil & Uruguay", bb=(-58, -36, -32, 6), iala="B", tz=-3, start="Santos", dest="Rio de Janeiro", pfx="BR", desc="Santos, Rio de Janeiro, Salvador, Recife, Amazon mouth"),
  "sams": dict(name="Southern South America", bb=(-80, -58, -50, -20), iala="B", tz=-3, start="Valparaiso", dest="Antofagasta", pfx="SS", desc="Rio de la Plata, Strait of Magellan, Cape Horn, Chilean channels"),
  "samw": dict(name="Pacific South America & Panama", bb=(-93, -20, -65, 15), iala="B", tz=-5, start="Callao", dest="Guayaquil", pfx="SW", desc="Panama Canal Pacific side, Guayaquil, Callao, Galapagos"),
  "ruse": dict(name="Russian Far East & Okhotsk Sea", bb=(130, 42, 165, 62), iala="A", tz=10, start="Vladivostok", dest="Petropavlovsk-Kamchatsky", pfx="RF", desc="Sea of Okhotsk, Sakhalin, Kamchatka, Tatar Strait"),
}


# ----------------------------------------------------------------------------- worldwide general coverage
LAT_BANDS = [(-80, -68), (-68, -55), (-55, -30), (-30, -5), (-5, 20), (20, 45), (45, 65), (65, 75), (75, 84)]
IALA_B_LON = (-170, -30)  # the Americas (plus JP/KR/PH handled by the detailed regions)
def gap_regions():
    from shapely.geometry import box as _box
    from shapely.ops import unary_union as _uu
    cov = _uu([_box(*R["bb"]) for R in REGIONS.values()] + [_box(116.8, 4.5, 126.8, 21.2)])
    out = {}
    for la0, la1 in LAT_BANDS:
        for lo0 in range(-180, 180, 30):
            lo1 = lo0 + 30; t = _box(lo0, la0, lo1, la1)
            if t.difference(cov).area < 0.08 * t.area: continue
            ns = lambda v: f"{abs(v)}°{'N' if v >= 0 else 'S'}"; ew = lambda v: f"{abs(v)}°{'E' if v >= 0 else 'W'}"
            rid = f"g{'n' if la0 >= 0 else 's'}{abs(la0)}{'e' if lo0 >= 0 else 'w'}{abs(lo0)}"
            out[rid] = dict(name=f"General {ns(la0)}–{ns(la1)} {ew(lo0)}–{ew(lo1)}", bb=(lo0, la0, lo1, la1), iala="B" if IALA_B_LON[0] <= (lo0 + lo1) / 2 <= IALA_B_LON[1] else "A",
                            tz=int(round((lo0 + lo1) / 2 / 15)), start=None, dest=None, pfx="G" + "ABCDEFGHIJKLMNOPQRSTUVWXYZ"[len(out) % 26], desc="", gen=True)
    return out

# curated major ports (lon, lat, rank): rank 3 = hub, 4 = major, 5 = regional. Positions are approximate; each is snapped to the nearest water.
PORTS = {
 "sea": [("Singapore",103.75,1.25,3),("Port Klang",101.33,2.98,4),("Tanjung Pelepas",103.55,1.36,4),("Penang",100.35,5.41,5),("Jakarta (Tanjung Priok)",106.88,-6.10,3),("Surabaya",112.73,-7.20,4),("Semarang",110.42,-6.95,5),("Makassar",119.40,-5.12,5),("Belawan",98.70,3.78,5),("Balikpapan",116.82,-1.27,5),("Laem Chabang",100.88,13.08,4),("Bangkok",100.58,13.55,5),("Vung Tau",107.07,10.35,4),("Hai Phong",106.72,20.85,4),("Da Nang",108.22,16.10,5),("Sihanoukville",103.52,10.63,5),("Kuching",110.35,1.56,5),("Kota Kinabalu",116.06,5.98,5),("Bintulu",113.05,3.22,5),("Benoa (Bali)",115.22,-8.75,5),("Batam",104.03,1.15,5),("Dumai",101.45,1.68,5),("Songkhla",100.57,7.23,5),("Phuket",98.40,7.83,5),("Kuantan",103.43,3.97,5),("Banjarmasin",114.56,-3.32,5),("Pontianak",109.33,-0.03,5),("Tanjung Pandan",107.63,-2.75,5),("Cilacap",109.00,-7.73,5)],
 "ea": [("Shanghai",121.80,31.20,3),("Ningbo-Zhoushan",121.90,29.90,3),("Hong Kong",114.15,22.30,3),("Shenzhen (Yantian)",114.27,22.57,3),("Guangzhou (Nansha)",113.60,22.75,4),("Xiamen",118.10,24.45,4),("Qingdao",120.30,36.05,3),("Tianjin",117.78,38.98,3),("Dalian",121.65,38.92,4),("Busan",129.05,35.08,3),("Incheon",126.60,37.45,4),("Ulsan",129.40,35.50,4),("Gwangyang",127.72,34.90,4),("Kaohsiung",120.27,22.60,3),("Keelung",121.75,25.15,4),("Taichung",120.50,24.28,5),("Tokyo",139.80,35.60,3),("Yokohama",139.68,35.43,3),("Nagoya",136.85,35.05,4),("Osaka",135.42,34.63,4),("Kobe",135.20,34.67,4),("Hakata (Fukuoka)",130.40,33.62,5),("Nagasaki",129.85,32.73,5),("Kitakyushu",130.92,33.93,5),("Sendai",141.02,38.27,5),("Tomakomai",141.63,42.63,5),("Niigata",139.07,37.95,5),("Yantai",121.40,37.55,5),("Fuzhou",119.45,26.05,5),("Haikou",110.30,20.07,5),("Zhanjiang",110.42,21.18,5),("Manila",120.95,14.58,4),("Subic Bay",120.25,14.80,5),("Cebu",123.90,10.30,5),("Davao",125.63,7.07,5),("Lianyungang",119.35,34.72,5),("Rizhao",119.55,35.38,5),("Pyeongtaek",126.82,36.97,5),("Mokpo",126.37,34.78,5),("Hualien",121.62,23.98,5)],
 "ina": [("Mumbai",72.85,18.95,3),("Nhava Sheva (JNPT)",72.95,18.95,3),("Kandla",70.22,23.02,4),("Mundra",69.70,22.75,4),("Cochin",76.25,9.97,4),("Chennai",80.30,13.10,3),("Visakhapatnam",83.30,17.68,4),("Haldia",88.10,22.03,5),("Paradip",86.68,20.27,5),("Tuticorin",78.17,8.75,5),("New Mangalore",74.80,12.93,5),("Colombo",79.83,6.95,3),("Hambantota",81.12,6.12,5),("Chittagong",91.80,22.30,4),("Karachi",66.97,24.80,3),("Port Qasim",67.35,24.77,4),("Gwadar",62.33,25.12,5),("Male",73.50,4.18,5),("Yangon",96.17,16.78,5),("Port Blair",92.75,11.68,5),("Phuket",98.40,7.83,5),("Mormugao (Goa)",73.80,15.42,5),("Ennore (Kamarajar)",80.33,13.25,5),("Krishnapatnam",80.13,14.25,5),("Mongla",89.60,22.48,5),("Trincomalee",81.23,8.57,5),("Kakinada",82.27,16.95,5),("Sittwe",92.90,20.15,5)],
 "gulf": [("Dubai (Jebel Ali)",55.05,25.02,3),("Port Rashid",55.28,25.27,5),("Abu Dhabi (Khalifa)",54.65,24.80,4),("Fujairah",56.37,25.13,4),("Khor Fakkan",56.37,25.35,5),("Doha (Hamad)",51.60,25.02,4),("Dammam",50.20,26.45,4),("Ras Tanura",50.17,26.65,4),("Jubail",49.67,27.05,5),("Kuwait (Shuwaikh)",47.93,29.37,4),("Bahrain (Khalifa Bin Salman)",50.65,26.17,5),("Bandar Abbas",56.27,27.13,4),("Bushehr",50.83,28.98,5),("Umm Qasr",47.92,30.03,5),("Sohar",56.65,24.52,4),("Muscat (Sultan Qaboos)",58.57,23.63,5),("Salalah",54.00,16.95,4),("Aden",45.02,12.78,4),("Djibouti",43.15,11.60,4),("Jeddah",39.15,21.47,3),("Yanbu",38.05,24.08,5),("Port Sudan",37.22,19.62,5),("Suez",32.55,29.93,4),("Port Said",32.30,31.27,4),("Aqaba",35.00,29.52,5),("Massawa",39.45,15.62,5),("Hodeidah",42.92,14.80,5),("Berbera",45.02,10.43,5),("Duqm",57.70,19.67,5),("Kharg Island",50.32,29.23,5),("Ain Sukhna",32.37,29.60,5),("Safaga",33.95,26.73,5)],
 "med": [("Piraeus",23.63,37.93,3),("Thessaloniki",22.92,40.62,4),("Istanbul (Ambarli)",28.68,40.97,3),("Izmir",27.12,38.43,4),("Mersin",34.63,36.78,4),("Haifa",35.00,32.82,4),("Ashdod",34.63,31.82,4),("Beirut",35.50,33.90,4),("Limassol",33.02,34.65,5),("Alexandria",29.87,31.18,4),("Port Said",32.30,31.27,4),("Tripoli",13.18,32.90,5),("Tunis (Rades)",10.28,36.80,5),("Algiers",3.07,36.78,4),("Oran",-0.63,35.72,5),("Tangier Med",-5.50,35.88,3),("Casablanca",-7.62,33.60,4),("Gibraltar",-5.35,36.13,4),("Algeciras",-5.43,36.13,3),("Malaga",-4.42,36.72,5),("Valencia",-0.32,39.45,3),("Barcelona",2.17,41.35,3),("Tarragona",1.22,41.10,5),("Marseille (Fos)",4.90,43.35,3),("Genoa",8.92,44.40,3),("La Spezia",9.83,44.10,4),("Livorno",10.30,43.55,4),("Civitavecchia",11.78,42.10,5),("Naples",14.27,40.83,4),("Gioia Tauro",15.90,38.45,4),("Palermo",13.37,38.13,5),("Augusta",15.22,37.22,5),("Taranto",17.22,40.47,5),("Bari",16.87,41.13,5),("Ancona",13.50,43.62,5),("Venice",12.35,45.42,4),("Trieste",13.77,45.65,4),("Koper",13.73,45.55,4),("Rijeka",14.43,45.32,5),("Split",16.43,43.50,5),("Bar",19.08,42.08,5),("Durres",19.45,41.32,5),("Patras",21.73,38.25,5),("Heraklion",25.13,35.35,5),("Constanta",28.65,44.17,4),("Varna",27.92,43.20,5),("Odessa",30.75,46.48,4),("Novorossiysk",37.78,44.72,4),("Batumi",41.65,41.65,5),("Samsun",36.33,41.30,5),("Marsaxlokk (Malta)",14.53,35.83,4),("Palma",2.65,39.55,5),("Cagliari",9.10,39.20,5),("Toulon",5.93,43.10,5),("Benghazi",20.05,32.12,5),("Sfax",10.77,34.73,5),("Misrata",15.22,32.37,5),("Damietta",31.78,31.47,5),("Iskenderun",36.17,36.60,5),("Poti",41.65,42.15,5)],
 "nweu": [("Rotterdam",4.05,51.95,3),("Antwerp",4.30,51.30,3),("Zeebrugge",3.20,51.35,4),("IJmuiden (Amsterdam)",4.58,52.47,4),("Hamburg",9.95,53.55,3),("Bremerhaven",8.55,53.55,3),("Wilhelmshaven",8.15,53.52,4),("Le Havre",0.10,49.48,3),("Dunkirk",2.37,51.05,4),("Calais",1.85,50.97,4),("Cherbourg",-1.62,49.65,5),("Brest",-4.48,48.38,4),("Saint-Nazaire",-2.20,47.27,4),("Dover",1.33,51.12,4),("Felixstowe",1.32,51.95,3),("London Gateway",0.45,51.47,4),("Southampton",-1.40,50.90,3),("Portsmouth",-1.10,50.80,4),("Plymouth",-4.15,50.35,5),("Bristol (Avonmouth)",-2.72,51.50,4),("Liverpool",-3.02,53.43,3),("Belfast",-5.90,54.62,4),("Dublin",-6.20,53.35,4),("Cork",-8.30,51.85,5),("Clyde (Greenock)",-4.75,55.95,5),("Aberdeen",-2.07,57.15,4),("Leith (Edinburgh)",-3.17,55.98,5),("Immingham",-0.20,53.63,4),("Teesport",-1.15,54.62,4),("Tyne (Newcastle)",-1.42,55.00,5),("Milford Haven",-5.05,51.70,4),("Esbjerg",8.43,55.47,5),("Copenhagen",12.62,55.70,4),("Aarhus",10.23,56.15,4),("Gothenburg",11.90,57.70,3),("Stockholm",18.10,59.33,4),("Malmo",13.00,55.62,5),("Helsinki",24.95,60.15,4),("Kotka",26.95,60.45,5),("Tallinn",24.75,59.45,4),("Riga",24.10,57.05,4),("Klaipeda",21.10,55.72,4),("Gdansk",18.68,54.40,3),("Gdynia",18.55,54.53,4),("Swinoujscie",14.27,53.92,5),("Rostock",12.10,54.17,5),("Kiel",10.15,54.35,5),("Lubeck",10.87,53.95,5),("Oslo",10.72,59.90,4),("Bergen",5.30,60.40,4),("Stavanger",5.70,58.97,5),("Kristiansand",8.00,58.13,5),("Trondheim",10.40,63.43,5),("St Petersburg",30.20,59.90,3),("Kaliningrad",20.35,54.65,5),("Harwich",1.28,51.95,5),("Hull",-0.33,53.73,5),("Holyhead",-4.63,53.32,5),("Rosyth",-3.43,56.02,5),("Lerwick",-1.15,60.15,5),("Torshavn",-6.77,62.00,5),("Alesund",6.15,62.47,5),("Turku",22.25,60.43,5),("Ventspils",21.55,57.40,5),("Liepaja",21.00,56.52,5),("Aalborg",9.92,57.05,5),("Fredericia",9.75,55.57,5),("Brunsbuttel",9.13,53.88,5),("Emden",7.20,53.33,5),("Vlissingen",3.58,51.45,5),("Ghent",3.72,51.10,5)],
 "wafr": [("Lagos (Apapa)",3.37,6.43,3),("Lekki",3.95,6.42,4),("Onne (Port Harcourt)",7.05,4.72,4),("Tema",-0.02,5.63,4),("Takoradi",-1.73,4.88,5),("Abidjan",-4.02,5.30,3),("Dakar",-17.43,14.68,3),("Nouakchott",-16.03,18.03,5),("Conakry",-13.72,9.52,4),("Freetown",-13.23,8.48,5),("Monrovia",-10.80,6.35,5),("Lome",1.28,6.13,4),("Cotonou",2.43,6.35,4),("Douala",9.68,4.05,4),("Libreville",9.42,0.40,5),("Pointe-Noire",11.85,-4.78,4),("Luanda",13.23,-8.80,4),("Casablanca",-7.62,33.60,3),("Agadir",-9.63,30.42,5),("Tangier Med",-5.50,35.88,3),("Las Palmas",-15.42,28.13,3),("Santa Cruz de Tenerife",-16.23,28.47,4),("Praia",-23.50,14.92,5),("Bissau",-15.58,11.85,5),("Banjul",-16.58,13.45,5),("Sao Tome",6.73,0.33,5),("Malabo",8.78,3.75,5),("Nouadhibou",-17.05,20.90,5),("Dakhla",-15.93,23.70,5),("Safi",-9.25,32.30,5),("Jorf Lasfar",-8.63,33.12,5),("Kribi",9.90,2.93,5),("San Pedro",-6.62,4.73,5),("Calabar",8.32,4.95,5),("Warri",5.75,5.52,5),("Mindelo",-25.00,16.88,5),("Funchal",-16.90,32.63,5)],
 "safr": [("Durban",31.05,-29.87,3),("Cape Town",18.43,-33.90,3),("Port Elizabeth (Gqeberha)",25.63,-33.97,4),("Richards Bay",32.08,-28.80,4),("East London",27.92,-33.02,5),("Saldanha Bay",17.95,-33.03,4),("Ngqura",25.70,-33.80,5),("Mossel Bay",22.15,-34.18,5),("Walvis Bay",14.50,-22.95,4),("Luderitz",15.15,-26.65,5),("Maputo",32.58,-25.98,4),("Beira",34.85,-19.83,4),("Nacala",40.68,-14.52,5),("Dar es Salaam",39.30,-6.82,3),("Zanzibar",39.18,-6.17,5),("Mombasa",39.65,-4.07,3),("Toamasina",49.42,-18.15,4),("Antsiranana",49.30,-12.28,5),("Pemba",40.52,-12.97,5),("Mtwara",40.18,-10.27,5),("Tanga",39.10,-5.07,5),("Lobito",13.55,-12.35,5),("Namibe",12.15,-15.20,5),("Luanda",13.23,-8.80,4),("Mahajanga",46.32,-15.72,5),("Toliara",43.67,-23.37,5),("Quelimane",36.88,-17.88,5),("Lamu",40.90,-2.27,5),("Moroni",43.25,-11.70,5),("Port Nolloth",16.87,-29.25,5)],
 "aus": [("Sydney",151.22,-33.85,3),("Port Botany",151.22,-33.97,4),("Melbourne",144.92,-37.83,3),("Brisbane",153.17,-27.38,3),("Fremantle",115.73,-32.05,3),("Adelaide",138.50,-34.78,4),("Newcastle",151.80,-32.92,4),("Port Kembla",150.90,-34.47,4),("Gladstone",151.25,-23.83,4),("Townsville",146.83,-19.25,4),("Cairns",145.78,-16.92,5),("Darwin",130.85,-12.47,4),("Port Hedland",118.58,-20.30,3),("Dampier",116.70,-20.65,4),("Geelong",144.38,-38.12,5),("Hobart",147.33,-42.88,4),("Mackay",149.23,-21.10,5),("Hay Point",149.30,-21.27,4),("Port Moresby",147.15,-9.47,4),("Lae",147.00,-6.73,5),("Bunbury",115.63,-33.32,5),("Geraldton",114.60,-28.77,5),("Albany",117.90,-35.03,5),("Esperance",121.90,-33.87,5),("Whyalla",137.60,-33.03,5),("Port Lincoln",135.87,-34.73,5),("Burnie",145.90,-41.05,5),("Bell Bay",146.87,-41.13,5),("Weipa",141.87,-12.67,5),("Gove",136.70,-12.20,5),("Kupang",123.58,-10.17,5),("Dili",125.57,-8.55,5),("Abbot Point",148.08,-19.87,5),("Broome",122.22,-18.00,5),("Devonport",146.37,-41.17,5),("Portland (Vic)",141.62,-38.35,5),("Eden",149.90,-37.07,5),("Bundaberg",152.38,-24.77,5),("Rabaul",152.18,-4.20,5),("Madang",145.80,-5.22,5)],
 "nz": [("Auckland",174.78,-36.83,3),("Tauranga",176.17,-37.65,3),("Wellington",174.80,-41.28,4),("Lyttelton",172.72,-43.60,4),("Port Chalmers (Dunedin)",170.62,-45.82,4),("Napier",176.92,-39.48,5),("New Plymouth",174.05,-39.05,5),("Nelson",173.27,-41.27,5),("Bluff",168.35,-46.60,5),("Marsden Point (Whangarei)",174.50,-35.85,5),("Timaru",171.25,-44.38,5),("Picton",174.00,-41.28,5),("Noumea",166.45,-22.27,4),("Suva",178.42,-18.13,4),("Lautoka",177.45,-17.60,5),("Port Vila",168.32,-17.75,5),("Honiara",159.95,-9.43,5),("Gisborne",178.03,-38.67,5),("Westport",171.60,-41.75,5),("Greymouth",171.20,-42.45,5),("Luganville",167.17,-15.52,5)],
 "usec": [("New York",-74.05,40.65,3),("Newark (Port Elizabeth)",-74.15,40.68,3),("Boston",-71.03,42.35,4),("Philadelphia",-75.13,39.90,4),("Baltimore",-76.55,39.25,4),("Norfolk",-76.30,36.90,3),("Charleston",-79.92,32.78,3),("Savannah",-81.08,32.08,3),("Jacksonville",-81.60,30.40,4),("Miami",-80.17,25.77,3),("Port Everglades",-80.12,26.10,4),("Wilmington (NC)",-77.95,34.23,5),("Halifax",-63.57,44.63,3),("Saint John",-66.07,45.27,4),("Portland (ME)",-70.25,43.65,5),("Providence",-71.40,41.80,5),("New Haven",-72.92,41.30,5),("Port Canaveral",-80.60,28.42,4),("Palm Beach",-80.05,26.77,5),("Sydney (NS)",-60.20,46.15,5),("St. John's",-52.70,47.57,5),("Hamilton (Bermuda)",-64.78,32.30,5),("Nassau",-77.35,25.08,4),("Freeport (Bahamas)",-78.70,26.52,5),("Morehead City",-76.70,34.72,5),("Brunswick (GA)",-81.50,31.13,5),("Fernandina Beach",-81.47,30.67,5),("Cape Canaveral",-80.60,28.40,5),("Wilmington (DE)",-75.52,39.72,5),("New London",-72.10,41.35,5),("Portsmouth (NH)",-70.75,43.08,5),("Yarmouth",-66.12,43.83,5),("Charlottetown",-63.12,46.23,5),("Corner Brook",-57.95,48.95,5)],
 "carib": [("Houston",-95.02,29.73,3),("Galveston",-94.80,29.30,4),("Corpus Christi",-97.40,27.80,4),("New Orleans",-90.05,29.95,3),("Mobile",-88.03,30.68,4),("Tampa",-82.45,27.92,4),("Pensacola",-87.22,30.40,5),("Port Arthur",-93.92,29.87,4),("Lake Charles",-93.22,30.22,5),("Veracruz",-96.13,19.20,4),("Altamira (Tampico)",-97.85,22.40,4),("Progreso",-89.67,21.30,5),("Havana",-82.35,23.15,4),("Santiago de Cuba",-75.83,20.00,5),("Kingston",-76.80,17.97,3),("Santo Domingo",-69.88,18.47,4),("Port-au-Prince",-72.35,18.55,5),("San Juan",-66.12,18.47,4),("Bridgetown",-59.62,13.10,5),("Port of Spain",-61.52,10.65,4),("Point Lisas",-61.47,10.40,5),("Cartagena",-75.53,10.40,3),("Barranquilla",-74.77,11.00,5),("Santa Marta",-74.22,11.25,5),("Colon (Cristobal)",-79.90,9.37,3),("Puerto Limon",-83.03,10.00,5),("Puerto Cortes",-87.95,15.85,5),("Belize City",-88.18,17.50,5),("Willemstad",-68.93,12.10,4),("Oranjestad",-70.03,12.52,5),("La Guaira",-66.93,10.60,5),("Puerto Cabello",-68.02,10.48,5),("Maracaibo",-71.60,10.65,5),("Georgetown",-58.17,6.82,5),("Fort-de-France",-61.07,14.60,5),("Pointe-a-Pitre",-61.53,16.23,5),("Castries",-60.98,14.02,5),("Nassau",-77.35,25.08,4),("Freeport (Bahamas)",-78.70,26.52,5),("Key West",-81.80,24.55,5),("Miami",-80.17,25.77,3),("Caucedo",-69.63,18.42,4),("Kingstown",-61.23,13.15,5),("Cozumel",-86.95,20.50,5),("Mariel",-82.75,23.00,5),("Gulfport",-89.08,30.35,5),("Freeport (TX)",-95.32,28.95,5),("Brownsville",-97.40,26.00,5),("Coatzacoalcos",-94.42,18.15,5),("Puerto Barrios",-88.60,15.73,5),("Roatan",-86.50,16.32,5)],
 "usw": [("Los Angeles",-118.25,33.72,3),("Long Beach",-118.20,33.75,3),("San Diego",-117.17,32.70,4),("San Francisco",-122.40,37.80,3),("Oakland",-122.30,37.80,3),("Seattle",-122.35,47.60,3),("Tacoma",-122.42,47.27,4),("Vancouver",-123.10,49.30,3),("Victoria",-123.37,48.42,5),("Port Hueneme",-119.22,34.15,5),("Eureka",-124.17,40.80,5),("Coos Bay",-124.22,43.37,5),("Astoria",-123.83,46.19,5),("Ensenada",-116.62,31.85,4),("Manzanillo",-104.32,19.05,3),("Mazatlan",-106.42,23.20,5),("Guaymas",-110.90,27.92,5),("La Paz",-110.32,24.15,5),("Cabo San Lucas",-109.90,22.88,5),("Topolobampo",-109.07,25.60,5),("Everett",-122.22,47.98,5),("Port Angeles",-123.43,48.12,5),("Bellingham",-122.50,48.75,5),("Richmond (CA)",-122.37,37.92,5),("Monterey",-121.88,36.60,5),("Santa Barbara",-119.68,34.40,5),("Avalon",-118.33,33.35,5),("Crescent City",-124.20,41.75,5),("Newport (OR)",-124.07,44.63,5),("Nanaimo",-123.93,49.17,5)],
 "alsk": [("Anchorage",-149.90,61.22,3),("Valdez",-146.35,61.12,4),("Seward",-149.43,60.12,4),("Kodiak",-152.40,57.78,4),("Dutch Harbor",-166.53,53.88,4),("Juneau",-134.42,58.30,4),("Ketchikan",-131.65,55.33,4),("Sitka",-135.33,57.05,5),("Prince Rupert",-130.33,54.32,3),("Vancouver",-123.10,49.30,3),("Nome",-165.40,64.50,5),("Homer",-151.55,59.63,5),("Whittier",-148.68,60.78,5),("Kitimat",-128.65,54.00,5),("Skagway",-135.32,59.45,5),("Cordova",-145.75,60.55,5),("Nikiski",-151.40,60.68,5),("Petersburg",-132.95,56.82,5),("Wrangell",-132.38,56.47,5),("Port Hardy",-127.48,50.72,5),("Campbell River",-125.25,50.03,5),("Kenai",-151.27,60.55,5),("Unalaska",-166.53,53.88,5),("Bethel",-161.75,60.80,5),("Kotzebue",-162.60,66.90,5),("Sand Point",-160.50,55.33,5),("Prince William Sound (Tatitlek)",-146.68,60.87,5)],
 "bra": [("Santos",-46.30,-23.97,3),("Rio de Janeiro",-43.17,-22.88,3),("Paranagua",-48.52,-25.50,3),("Itajai",-48.65,-26.90,4),("Rio Grande",-52.08,-32.12,4),("Vitoria (Tubarao)",-40.28,-20.30,4),("Salvador",-38.52,-12.97,4),("Suape (Recife)",-34.95,-8.38,4),("Pecem (Fortaleza)",-38.80,-3.55,4),("Belem",-48.50,-1.45,5),("Itaqui (Sao Luis)",-44.37,-2.57,4),("Natal",-35.20,-5.78,5),("Maceio",-35.72,-9.68,5),("Ilheus",-39.03,-14.78,5),("Sao Sebastiao",-45.40,-23.80,5),("Sao Francisco do Sul",-48.58,-26.23,5),("Montevideo",-56.20,-34.90,3),("Macapa",-51.05,0.03,5),("Cabedelo",-34.83,-6.97,5),("Aracaju",-37.03,-10.92,5),("Imbituba",-48.65,-28.23,5),("Itaguai (Sepetiba)",-43.83,-22.93,4),("Angra dos Reis",-44.32,-23.00,5),("Fortaleza (Mucuripe)",-38.48,-3.72,5),("Navegantes",-48.65,-26.88,5),("Vila do Conde",-48.75,-1.53,5),("Ponta da Madeira",-44.37,-2.57,5)],
 "sams": [("Buenos Aires",-58.37,-34.58,3),("Bahia Blanca",-62.27,-38.78,4),("Mar del Plata",-57.53,-38.03,5),("Montevideo",-56.20,-34.90,3),("Puerto Madryn",-65.03,-42.77,5),("Comodoro Rivadavia",-67.47,-45.87,5),("Ushuaia",-68.30,-54.80,5),("Punta Arenas",-70.92,-53.15,4),("Puerto Montt",-72.93,-41.48,5),("San Vicente (Talcahuano)",-73.12,-36.72,4),("Valparaiso",-71.62,-33.03,3),("San Antonio",-71.62,-33.58,3),("Coquimbo",-71.33,-29.95,5),("Antofagasta",-70.40,-23.65,4),("Iquique",-70.15,-20.20,4),("Rio Gallegos",-69.22,-51.62,5),("Stanley",-57.85,-51.70,5),("Quintero",-71.53,-32.77,5),("Puerto Deseado",-65.90,-47.75,5),("Mejillones",-70.45,-23.10,5),("Puerto Chacabuco",-72.82,-45.47,5),("Punta Loyola",-69.00,-51.62,5),("Quequen",-58.70,-38.58,5),("San Antonio Este",-64.73,-40.80,5),("Puerto Williams",-67.62,-54.93,5),("Chanaral",-70.62,-26.35,5),("Caldera",-70.83,-27.07,5),("Puerto Natales",-72.50,-51.72,5),("Castro",-73.77,-42.48,5),("Corral",-73.43,-39.87,5)],
 "samw": [("Callao",-77.15,-12.05,3),("Guayaquil",-79.90,-2.28,3),("Manta",-80.72,-0.95,4),("Esmeraldas",-79.65,0.98,5),("Buenaventura",-77.08,3.88,4),("Balboa (Panama)",-79.57,8.95,3),("Puerto Quetzal",-90.78,13.92,4),("Acajutla",-89.83,13.58,5),("Corinto",-87.18,12.48,5),("Caldera (CR)",-84.72,9.92,5),("Paita",-81.10,-5.08,5),("Salaverry",-78.98,-8.22,5),("Chimbote",-78.60,-9.08,5),("Pisco",-76.22,-13.72,5),("Matarani",-72.10,-17.00,4),("Ilo",-71.35,-17.65,5),("Puerto Bolivar",-80.00,-3.27,5),("Arica",-70.33,-18.47,4),("Tumaco",-78.78,1.80,5),("Puerto Baquerizo (Galapagos)",-89.60,-0.90,5),("La Libertad",-80.90,-2.22,5),("Posorja",-80.25,-2.70,5),("Cartagena",-75.53,10.40,3),("Colon (Cristobal)",-79.90,9.37,3),("Puerto Armuelles",-82.87,8.27,5),("San Lorenzo (Honduras)",-87.45,13.42,5),("Puerto San Jose",-90.83,13.92,5),("Golfito",-83.17,8.63,5),("Puntarenas",-84.83,9.97,5),("Turbo",-76.73,8.10,5),("Barranquilla",-74.77,11.00,5)],
 "ruse": [("Vladivostok",131.88,43.10,3),("Nakhodka",132.88,42.80,4),("Vostochny",133.07,42.75,4),("Vanino",140.27,49.08,4),("Korsakov",142.75,46.63,5),("Kholmsk",142.05,47.05,5),("Magadan",150.80,59.55,4),("Petropavlovsk-Kamchatsky",158.65,53.00,4),("Okhotsk",143.25,59.37,5),("Sovetskaya Gavan",140.30,48.97,5),("Nikolayevsk-na-Amure",140.70,53.15,5),("Otaru",141.00,43.20,4),("Wakkanai",141.68,45.42,5),("Hakodate",140.72,41.78,5),("Kushiro",144.37,42.98,4),("Chongjin",129.78,41.77,5),("Rason",130.40,42.25,5),("Posyet",130.80,42.65,5),("De-Kastri",140.78,51.47,5),("Prigorodnoye (Sakhalin LNG)",142.90,46.63,5),("Nemuro",145.58,43.33,5),("Abashiri",144.28,44.02,5),("Rumoi",141.63,43.93,5),("Muroran",140.97,42.33,4),("Okhotsk (Ayan)",138.17,56.45,5),("Ust-Kamchatsk",162.47,56.22,5)],
}

GAPS = gap_regions(); REGIONS.update(GAPS)

# ----------------------------------------------------------------------------- helpers
def vnoise(x, y, scale, seed):
    """deterministic smooth value noise in [0,1] for arrays x,y (NM) at given lattice scale (NM)"""
    fx, fy = x / scale, y / scale
    ix, iy = np.floor(fx).astype(np.int64), np.floor(fy).astype(np.int64)
    tx, ty = fx - ix, fy - iy
    tx = tx * tx * (3 - 2 * tx); ty = ty * ty * (3 - 2 * ty)
    def h(i, j):
        v = (i * 374761393 + j * 668265263 + seed * 982451653) & 0xffffffff
        v = (v ^ (v >> 13)) * 1274126177 & 0xffffffff
        return ((v ^ (v >> 16)) & 0xffff) / 65535.0
    a, b, c, d = h(ix, iy), h(ix + 1, iy), h(ix, iy + 1), h(ix + 1, iy + 1)
    return (a * (1 - tx) + b * tx) * (1 - ty) + (c * (1 - tx) + d * tx) * ty

def fbm(x, y, seed):
    return 0.5 * vnoise(x, y, 24, seed) + 0.3 * vnoise(x, y, 7, seed + 1) + 0.2 * vnoise(x, y, 2.2, seed + 2)

def simplify_ring(pts, tol):
    if len(pts) < 4: return pts
    p = Polygon(pts).simplify(tol, preserve_topology=True)
    if p.is_empty or p.geom_type != "Polygon": return pts
    return list(p.exterior.coords)[:-1]

def simplify_line(pts, tol):
    if len(pts) < 3: return pts
    return list(LineString(pts).simplify(tol, preserve_topology=False).coords)

def flat(pts, nd=3):
    return [round(float(v), nd) for p in pts for v in p]

def load_json(name):
    with open(os.path.join(DATA, name)) as f: return json.load(f)

class Pack:
    def __init__(self, rid, R):
        self.rid, self.R = rid, R
        self.lon0, self.lat0, self.lon1, self.lat1 = R["bb"]
        self.C = math.cos(math.radians((self.lat0 + self.lat1) / 2))
        self.WX = (self.lon1 - self.lon0) * 60 * self.C; self.WY = (self.lat1 - self.lat0) * 60
        self.rng = random.Random(rid)
        self.cells = []; self.depth_blobs = []; self.feat = dict(obj=[], areas=[], lines=[], names=[], drg=[]); self.shoals = []
        self.enc = []; self.ais = []; self.aio = []; self.ports = []

    # --- projection (same as the engine's LL)
    def xy(self, lon, lat): return ((lon - self.lon0) * 60 * self.C, (lat - self.lat0) * 60)
    def ll(self, x, y): return (self.lon0 + x / (60 * self.C), self.lat0 + y / 60)

    # --- data
    def load(self):
        t = time.time()
        bbox = box(self.lon0 - 0.5, self.lat0 - 0.5, self.lon1 + 0.5, self.lat1 + 0.5)
        coast = load_json("coast10m.geo.json")["geometries"][0]["coordinates"]
        polys = []
        for p in coast:
            ring = p[0]
            xs = [q[0] for q in ring]; ys = [q[1] for q in ring]
            if max(xs) < bbox.bounds[0] or min(xs) > bbox.bounds[2] or max(ys) < bbox.bounds[1] or min(ys) > bbox.bounds[3]: continue
            g = Polygon(ring)
            if not g.is_valid: g = g.buffer(0)
            g = g.intersection(bbox)
            if g.is_empty: continue
            gs = [g] if g.geom_type == "Polygon" else [q for q in g.geoms if q.geom_type == "Polygon"] if hasattr(g, "geoms") else []
            polys.extend(gs)
        self.land_ll = polys  # lon/lat polygons (exterior only)
        # land in NM space
        self.land = []
        for g in polys:
            ext = [self.xy(x, y) for x, y in g.exterior.coords[:-1]]
            if len(ext) >= 3: self.land.append(ext)
        self.land_tree = STRtree([Polygon(r) for r in self.land])
        self.land_polys = [Polygon(r) for r in self.land]
        print(f"  land polygons: {len(self.land)}  ({time.time()-t:.1f}s)")
        # bathymetry base levels (NE): deepest polygon containing a point wins
        self.bathy = []
        for lvl, fn in [(200, "ne_10m_bathymetry_K_200"), (1000, "ne_10m_bathymetry_J_1000"), (2000, "ne_10m_bathymetry_I_2000"), (3000, "ne_10m_bathymetry_H_3000"), (4000, "ne_10m_bathymetry_G_4000")]:
            fc = load_json(fn + ".geojson")
            gs = []
            for f in fc["features"]:
                g = shape(f["geometry"])
                if not g.intersects(bbox): continue
                g = g.intersection(bbox)
                if not g.is_empty: gs.append(g)
            arrs = []
            for g in gs:
                for poly in (g.geoms if g.geom_type == "MultiPolygon" else [g]):
                    if poly.geom_type != "Polygon": continue
                    ext = np.array([self.xy(x, y) for x, y in poly.exterior.coords]); holes = [np.array([self.xy(x, y) for x, y in h.coords]) for h in poly.interiors]
                    arrs.append((ext, holes, (ext[:, 0].min(), ext[:, 1].min(), ext[:, 0].max(), ext[:, 1].max())))
            self.bathy.append((lvl, arrs))
        # reefs
        self.reefs = [shape(f["geometry"]) for f in load_json("ne_10m_reefs.geojson")["features"] if shape(f["geometry"]).intersects(bbox)]
        # ports
        ports = []
        for nm, lon, lat, rk in PORTS.get(self.rid, []):
            if self.lon0 + 0.2 < lon < self.lon1 - 0.2 and self.lat0 + 0.2 < lat < self.lat1 - 0.2:
                ports.append(dict(name=nm, rank=rk, lon=lon, lat=lat, curated=True))
        for f in load_json("ne_10m_ports.geojson")["features"]:
            lon, lat = f["geometry"]["coordinates"]; nm = f["properties"]["name"]
            if self.lon0 + 0.3 < lon < self.lon1 - 0.3 and self.lat0 + 0.3 < lat < self.lat1 - 0.3:
                if any(abs(p["lon"] - lon) < 0.25 and abs(p["lat"] - lat) < 0.25 for p in ports): continue
                ports.append(dict(name=nm, rank=max(6, f["properties"]["scalerank"]), lon=lon, lat=lat, curated=False))
        self.ports = ports
        print(f"  ports: {len(ports)}  major(≤5): {sum(1 for p in ports if p['rank'] <= 5)}  ({time.time()-t:.1f}s)")

    # --- rasters
    def land_mask(self, x0, y0, res, nx, ny):
        """rasterise the land polygons (PIL scanline fill: fast even for the continental polygons)"""
        img = Image.new("1", (nx, ny), 0); dr = ImageDraw.Draw(img)
        cell = box(x0, y0, x0 + nx * res, y0 + ny * res)
        for i in self.land_tree.query(cell):
            r = self.land[i]
            if len(r) < 3: continue
            pts = [((p[0] - x0) / res, (p[1] - y0) / res) for p in r]
            dr.polygon(pts, fill=1, outline=1)
        return np.array(img, dtype=bool)

    def bathy_base(self, x0, y0, res, nx, ny, step=None):
        """base depth level per pixel from NE bathymetry polygons (rasterised at coarse step then upsampled)"""
        st = step or max(1, int(round(2.0 / res)))  # ~2 NM sampling
        sx, sy = (nx + st - 1) // st, (ny + st - 1) // st
        base = np.zeros((sy, sx), dtype=np.float32)
        cell = box(x0, y0, x0 + nx * res, y0 + ny * res)
        X1, Y1 = x0 + nx * res, y0 + ny * res
        for lvl, arrs in self.bathy:
            for ext, holes, bb in arrs:
                if bb[2] < x0 or bb[0] > X1 or bb[3] < y0 or bb[1] > Y1: continue
                xs = (ext[:, 0] - x0) / res / st; ys = (ext[:, 1] - y0) / res / st
                rr, cc = draw.polygon(ys, xs, shape=base.shape)
                base[rr, cc] = np.maximum(base[rr, cc], lvl)
                for h in holes:
                    hx = (h[:, 0] - x0) / res / st; hy = (h[:, 1] - y0) / res / st
                    rr, cc = draw.polygon(hy, hx, shape=base.shape)
                    base[rr, cc] = np.minimum(base[rr, cc], lvl - 1)  # hole = shallower than lvl
        if st > 1:
            base = ndimage.zoom(base, st, order=1)[:ny, :nx]
            if base.shape != (ny, nx):
                pad = np.zeros((ny, nx), dtype=np.float32); pad[:base.shape[0], :base.shape[1]] = base
                b2 = pad; b2[base.shape[0]:, :] = base[-1:, :][:, :nx] if base.shape[0] < ny else 0; base = pad
        return base

    def depth_grid(self, x0, y0, res, nx, ny, drg_lines):
        """returns (depth float32 array, land mask). depth in metres; drying = negative"""
        land = self.land_mask(x0, y0, res, nx, ny)
        d = ndimage.distance_transform_edt(~land) * res if land.any() else np.full(land.shape, 500.0)  # NM to nearest land
        din = ndimage.distance_transform_edt(land) * res if (~land).any() else np.full(land.shape, 500.0)
        X = x0 + np.arange(nx)[None, :] * res; Y = y0 + np.arange(ny)[:, None] * res
        X = np.broadcast_to(X, (ny, nx)); Y = np.broadcast_to(Y, (ny, nx))
        n1 = fbm(X, Y, 11); n2 = vnoise(X, Y, 1.1, 77)
        # shelf profile (metres) vs distance from coast (NM)
        shelf = np.where(d < 0.3, 1.0 + 20 * d,
                np.where(d < 1.5, 7 + 11 * (d - 0.3),
                np.where(d < 5, 20.2 + 4.3 * (d - 1.5),
                np.where(d < 20, 35.3 + 1.7 * (d - 5),
                np.where(d < 80, 60.8 + 0.9 * (d - 20), 114.8 + 0.6 * (d - 80))))))
        shelf = shelf * (0.72 + 0.56 * n1) + (n2 - 0.5) * np.minimum(3.0, 0.4 * shelf)
        shelf = np.minimum(shelf, 260)
        base = self.bathy_base(x0, y0, res, nx, ny)
        steep = np.where(d < 1, shelf * (1 + 3 * d), np.maximum(base * (0.85 + 0.3 * n1), shelf * 4))
        depth = np.where(base > 0, steep, shelf)
        depth = np.maximum(depth, 0.3)
        # drying / intertidal strip right at the coast (small)
        depth = np.where((d < 0.08 * max(1, 0.25 / res)) & (n2 > 0.72), -0.6, depth)
        # reefs: shallow coral
        cell = box(x0, y0, x0 + nx * res, y0 + ny * res)
        for g in self.reefs:
            pts = [self.xy(x, y) for x, y in (g.coords if g.geom_type == "LineString" else [])]
            if not pts: continue
            ln = LineString(pts)
            if not ln.intersects(cell): continue
            for a, b in zip(pts[:-1], pts[1:]):
                rr, cc = draw.line(int((a[1] - y0) / res), int((a[0] - x0) / res), int((b[1] - y0) / res), int((b[0] - x0) / res))
                ok = (rr >= 0) & (rr < ny) & (cc >= 0) & (cc < nx)
                depth[rr[ok], cc[ok]] = np.minimum(depth[rr[ok], cc[ok]], 1.8)
            if res <= 0.3:
                m = np.zeros_like(land);
                for a, b in zip(pts[:-1], pts[1:]):
                    rr, cc = draw.line(int((a[1] - y0) / res), int((a[0] - x0) / res), int((b[1] - y0) / res), int((b[0] - x0) / res))
                    ok = (rr >= 0) & (rr < ny) & (cc >= 0) & (cc < nx); m[rr[ok], cc[ok]] = True
                m = ndimage.binary_dilation(m, iterations=max(1, int(0.3 / res)))
                depth = np.where(m & ~land, np.minimum(depth, 2.5 + 6 * n2), depth)
        # dredged channels: maintained depth
        for dr in drg_lines:
            pts = [(p[0], p[1]) for p in dr["pts"]]
            if not LineString(pts).intersects(cell): continue
            m = np.zeros_like(land)
            for a, b in zip(pts[:-1], pts[1:]):
                rr, cc = draw.line(int(round((a[1] - y0) / res)), int(round((a[0] - x0) / res)), int(round((b[1] - y0) / res)), int(round((b[0] - x0) / res)))
                ok = (rr >= 0) & (rr < ny) & (cc >= 0) & (cc < nx); m[rr[ok], cc[ok]] = True
            m = ndimage.binary_dilation(m, iterations=max(1, int(round(dr["hw"] / res))))
            depth = np.where(m & ~land, np.maximum(depth, dr["dv"] + 0.3), depth)
        return depth.astype(np.float32), land, din

    def encode_grid(self, depth, land):
        dq_ = np.where(depth < 30, 0.1, np.where(depth < 100, 0.5, np.where(depth < 300, 2.0, np.where(depth < 1000, 10.0, 50.0))))
        depth = np.round(depth / dq_) * dq_
        q = np.clip(np.round((depth + 10) * 10), 1, 65000).astype(np.int64)
        q[land] = LAND_Q
        q[(q >= 102) & (q <= 106) & ~land] = 107  # keep 104 unique to land
        flat_q = q.ravel()
        dq = np.diff(flat_q, prepend=0) & 0xffff
        return dq.astype("<u2").tobytes()

    def contours(self, depth, land, x0, y0, res, levels, tol):
        out = {}
        dd = np.where(land, -5.0, depth)
        for L in levels:
            thr = 0.0 if L == 0 else L
            lines = []
            for c in measure.find_contours(dd, thr - (0.001 if L == 0 else 0)):
                if len(c) < 3: continue
                pts = [(x0 + p[1] * res, y0 + p[0] * res) for p in c]
                pts = simplify_line(pts, tol)
                if len(pts) >= 2: lines.append(flat(pts))
            if lines: out[str(L)] = lines
        return out

    def land_contours(self, din, land, x0, y0, res, tol, levels=(100, 300, 500, 1000)):
        X = x0 + np.arange(din.shape[1])[None, :] * res; Y = y0 + np.arange(din.shape[0])[:, None] * res
        X = np.broadcast_to(X, din.shape); Y = np.broadcast_to(Y, din.shape)
        elev = 90 * np.power(np.maximum(din, 0), 0.85) * (0.6 + 0.9 * fbm(X, Y, 5))
        elev = np.where(land, elev, -1)
        out = {}
        for L in levels:
            lines = []
            for c in measure.find_contours(elev, L):
                if len(c) < 4: continue
                pts = simplify_line([(x0 + p[1] * res, y0 + p[0] * res) for p in c], tol)
                if len(pts) >= 2: lines.append(flat(pts))
            if lines: out[str(L)] = lines
        return out

    def land_rings(self, x0, y0, x1, y1, tol):
        cell = box(x0, y0, x1, y1)
        rings = []
        for i in self.land_tree.query(cell):
            g = self.land_polys[i]
            if not g.intersects(cell): continue
            gi = g.intersection(cell)
            for poly in (gi.geoms if gi.geom_type == "MultiPolygon" else [gi]):
                if poly.geom_type != "Polygon" or poly.area < (tol * tol * 2): continue
                pts = list(poly.simplify(tol, preserve_topology=True).exterior.coords)[:-1]
                if len(pts) >= 3: rings.append(flat(pts))
        return rings

    # --- cells
    def add_cell(self, cid, band, name, x0, y0, x1, y1, res, drg):
        nx, ny = int(math.ceil((x1 - x0) / res)) + 1, int(math.ceil((y1 - y0) / res)) + 1
        t = time.time()
        depth, land, din = self.depth_grid(x0, y0, res, nx, ny, drg)
        tol = res * 0.6
        cell = dict(id=cid, band=band, name=name, box=[round(x0, 3), round(y0, 3), round(x0 + (nx - 1) * res, 3), round(y0 + (ny - 1) * res, 3)], res=res, nx=nx, ny=ny, x0=round(x0, 3), y0=round(y0, 3),
                    land=self.land_rings(x0, y0, x0 + (nx - 1) * res, y0 + (ny - 1) * res, tol),
                    cont=self.contours(depth, land, x0, y0, res, BAND_LEVELS[band], tol),
                    lcont=self.land_contours(din, land, x0, y0, res, tol * 1.5, (100, 300, 1000) if band <= 2 else (100, 300, 500, 1000)))
        self.cells.append(cell); self.depth_blobs.append(self.encode_grid(depth, land))
        print(f"  cell {cid} band{band} {nx}x{ny} res{res}  land rings {len(cell['land'])}  ({time.time()-t:.1f}s)")
        self._last = (depth, land, x0, y0, res)
        return depth, land

    # --- coarse grid for routing / sea direction
    def coarse(self):
        res = 1.0
        nx, ny = int(self.WX / res) + 1, int(self.WY / res) + 1
        depth, land, _ = self.depth_grid(0, 0, res, nx, ny, [])
        # islands smaller than a pixel: mark any pixel touched by a land vertex as land too
        for r in self.land:
            for p in r[::2]:
                i, j = int(round(p[0] / res)), int(round(p[1] / res))
                if 0 <= i < nx and 0 <= j < ny: land[j, i] = True
        self.cg = dict(depth=depth, land=land, res=res, nx=nx, ny=ny)
        self.cg["dist"] = ndimage.distance_transform_edt(~land) * res if land.any() else np.full(land.shape, 500.0)

    def port_local(self, x, y):
        """fine local land/distance grid (0.25 NM, ±30 NM) around a port for water snapping and sea direction"""
        res, R = 0.25, 30.0
        x0, y0 = max(0, x - R), max(0, y - R); nx, ny = int((min(self.WX, x + R) - x0) / res) + 1, int((min(self.WY, y + R) - y0) / res) + 1
        land = self.land_mask(x0, y0, res, nx, ny)
        dist = ndimage.distance_transform_edt(~land) * res if land.any() else np.full(land.shape, 500.0)
        return dict(x0=x0, y0=y0, res=res, nx=nx, ny=ny, land=land, dist=dist)

    def lg_water_near(self, g, x, y, maxr=20, mind=0.3):
        """water point for the port: close to the port, but with a usable clear run to sea (not a creek on the wrong side)"""
        r = g["res"]; i, j = int(round((x - g["x0"]) / r)), int(round((y - g["y0"]) / r)); R = int(maxr / r)
        jj0, jj1 = max(0, j - R), min(g["ny"], j + R + 1); ii0, ii1 = max(0, i - R), min(g["nx"], i + R + 1)
        sub = g["dist"][jj0:jj1, ii0:ii1]; ok = np.argwhere(sub >= mind)
        if not len(ok): return None
        d = np.sqrt((ok[:, 0] + jj0 - j) ** 2 + (ok[:, 1] + ii0 - i) ** 2) * r
        order = np.argsort(d); cands = []
        for k in order:
            p = (g["x0"] + (ok[k, 1] + ii0) * r, g["y0"] + (ok[k, 0] + jj0) * r)
            if any(math.hypot(p[0] - q[0], p[1] - q[1]) < 1.5 for q in cands): continue
            cands.append(p)
            if len(cands) >= 10 or d[k] > min(maxr, d[order[0]] + 12): break
        best = None
        for p in cands:
            brg, run = self.lg_sea_dir(g, p[0], p[1])
            score = math.hypot(p[0] - x, p[1] - y) + 1.2 * max(0, 8 - run)
            if best is None or score < best[0]: best = (score, p, brg, run)
        self._lastdir = (best[2], best[3])
        return best[1]

    def lg_sea_dir(self, g, x, y, mind=0.45, maxrun=25):
        r = g["res"]; best = (0, 0)
        for b in range(0, 360, 5):
            ux, uy = math.sin(math.radians(b)), math.cos(math.radians(b)); run = 0
            for k in range(1, int(maxrun / r)):
                i, j = int(round((x + ux * k * r - g["x0"]) / r)), int(round((y + uy * k * r - g["y0"]) / r))
                if not (0 <= i < g["nx"] and 0 <= j < g["ny"]): break
                if g["land"][j, i] or g["dist"][j, i] < mind: break
                run += 1
            if run > best[0]: best = (run, b)
        # prefer directions whose neighbours are also clear (a wide fairway, not a crack between islands)
        return best[1], best[0] * r

    def water_near(self, x, y, maxr=12):
        """nearest sea point (≥1 NM from land) to x,y on the coarse grid"""
        cg = self.cg; r = cg["res"]
        i, j = int(round(x / r)), int(round(y / r))
        best = None
        R = int(maxr / r)
        for dj in range(-R, R + 1):
            for di in range(-R, R + 1):
                ii, jj = i + di, j + dj
                if 0 <= ii < cg["nx"] and 0 <= jj < cg["ny"] and not cg["land"][jj, ii] and cg["dist"][jj, ii] >= 1.0:
                    dd = di * di + dj * dj
                    if best is None or dd < best[0]: best = (dd, ii * r, jj * r)
        return (best[1], best[2]) if best else None

    def sea_dir(self, x, y):
        """bearing (deg true) from x,y with the longest clear-water run"""
        cg = self.cg; r = cg["res"]; best = (0, 0)
        for b in range(0, 360, 10):
            ux, uy = math.sin(math.radians(b)), math.cos(math.radians(b)); run = 0
            for k in range(1, 40):
                px, py = x + ux * k * r, y + uy * k * r
                i, j = int(round(px / r)), int(round(py / r))
                if not (0 <= i < cg["nx"] and 0 <= j < cg["ny"]) or cg["land"][j, i] or cg["dist"][j, i] < 0.8: break
                run += 1
            if run > best[0]: best = (run, b)
        return best[1], best[0] * r

    def route(self, a, b):
        """sea route a→b (NM points) on the coarse grid; returns simplified list of (x,y)"""
        cg = self.cg; r = cg["res"]
        cost = np.where(cg["land"], 1e6, np.where(cg["dist"] < 1.6, 120, np.where(cg["dist"] < 2.6, 12, np.where(cg["dist"] < 4, 2.5, 1.0))) * np.where(cg["depth"] < 12, 6, np.where(cg["depth"] < 25, 2.5, 1.0))).astype(np.float32)
        wa, wb = self.water_near(a[0], a[1]), self.water_near(b[0], b[1])
        if not wa or not wb: return None
        A = (int(round(wa[1] / r)), int(round(wa[0] / r))); B = (int(round(wb[1] / r)), int(round(wb[0] / r)))
        A = (min(max(A[0], 0), cg["ny"] - 1), min(max(A[1], 0), cg["nx"] - 1)); B = (min(max(B[0], 0), cg["ny"] - 1), min(max(B[1], 0), cg["nx"] - 1))
        try:
            path, c = route_through_array(cost, A, B, fully_connected=True, geometric=True)
        except Exception:
            return None
        if c > 5e5: return None
        pts = [a] + [(p[1] * r, p[0] * r) for p in path] + [b]
        return self.simplify_safe(pts)

    def seg_safe(self, a, b, mind=1.5, minz=12):
        """leg clear of the real land polygons (≥ mind NM except at its ends) and of coarse shallows"""
        ln = LineString([a, b])
        for i in self.land_tree.query(ln.buffer(mind)):
            g = self.land_polys[i]
            if g.intersects(ln): return False
            if g.distance(ln) < mind and g.distance(Point(a)) > mind * 0.5 and g.distance(Point(b)) > mind * 0.5: return False
        cg = self.cg; r = cg["res"]; L = ln.length; n = max(2, int(L / (r * 0.5)))
        for k in range(1, n):
            x, y = a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n
            i, j = int(round(x / r)), int(round(y / r))
            if not (0 <= i < cg["nx"] and 0 <= j < cg["ny"]): return False
            if cg["depth"][j, i] < minz and not cg["land"][j, i]: return False
        return True

    def fine_route(self, a, b):
        """re-route one leg on a 0.25 NM local grid built from the land polygons"""
        res, m = 0.25, 8.0
        x0, y0 = max(0, min(a[0], b[0]) - m), max(0, min(a[1], b[1]) - m); x1, y1 = min(self.WX, max(a[0], b[0]) + m), min(self.WY, max(a[1], b[1]) + m)
        nx, ny = int((x1 - x0) / res) + 1, int((y1 - y0) / res) + 1
        if nx * ny > 6e6: return None
        land = self.land_mask(x0, y0, res, nx, ny)
        for i in self.land_tree.query(box(x0, y0, x1, y1)):
            for p in self.land[i]:
                ii, jj = int(round((p[0] - x0) / res)), int(round((p[1] - y0) / res))
                if 0 <= ii < nx and 0 <= jj < ny: land[jj, ii] = True
        dist = ndimage.distance_transform_edt(~land) * res
        cost = np.where(land, 1e6, np.where(dist < 0.6, 80, np.where(dist < 1.2, 6, 1.0))).astype(np.float32)
        A = (min(max(int(round((a[1] - y0) / res)), 0), ny - 1), min(max(int(round((a[0] - x0) / res)), 0), nx - 1)); B = (min(max(int(round((b[1] - y0) / res)), 0), ny - 1), min(max(int(round((b[0] - x0) / res)), 0), nx - 1))
        for Q in (A, B):
            if land[Q]:
                ok = np.argwhere(dist >= 0.5); d2 = (ok[:, 0] - Q[0]) ** 2 + (ok[:, 1] - Q[1]) ** 2; k = int(np.argmin(d2)); Q2 = (int(ok[k, 0]), int(ok[k, 1]))
                if Q is A: A = Q2
                else: B = Q2
        try: path, c = route_through_array(cost, A, B, fully_connected=True, geometric=True)
        except Exception: return None
        if c > 5e5: return None
        pts = [a] + [(x0 + p[1] * res, y0 + p[0] * res) for p in path] + [b]
        out = [pts[0]]; i = 0
        while i < len(pts) - 1:
            j = len(pts) - 1
            while j > i + 1 and not self.seg_safe(pts[i], pts[j], mind=0.6, minz=0): j -= 1
            out.append(pts[j]); i = j
        return out

    def simplify_safe(self, pts):
        """drop intermediate points while the straight leg stays clear of land / shallows on the coarse grid"""
        pts = [tuple(p) for p in pts]
        out = [pts[0]]; i = 0
        while i < len(pts) - 1:
            j = len(pts) - 1
            while j > i + 1 and not (self.seg_safe(pts[i], pts[j]) and math.hypot(pts[j][0] - pts[i][0], pts[j][1] - pts[i][1]) < 220): j -= 1
            out.append(pts[j]); i = j
        # repair legs that still touch small islands the coarse grid cannot see
        fixed = [out[0]]
        for a, b in zip(out[:-1], out[1:]):
            if self.seg_safe(a, b, mind=0.6, minz=0): fixed.append(b); continue
            fr = self.fine_route(a, b)
            if fr and len(fr) > 2: fixed.extend(fr[1:])
            else: fixed.append(b)
        return fixed

# ----------------------------------------------------------------------------- feature synthesis
LIGHT_CHR = ["Fl 5s", "Fl 10s", "Fl(2) 10s", "Fl(3) 15s", "LFl 10s", "Iso 4s", "Oc 6s", "Fl(2) 12s", "Fl 7.5s", "Fl(4) 20s"]

def build_port_features(P: Pack, port, big):
    """aids, areas and names for one port. big = approach cell + full set of aids"""
    name = port["name"]; x, y = P.xy(port["lon"], port["lat"])
    rng = random.Random(name)
    g = P.port_local(x, y)
    w = P.lg_water_near(g, x, y)
    if not w: return None
    wx, wy = w
    brg, run = P._lastdir
    ux, uy = math.sin(math.radians(brg)), math.cos(math.radians(brg)); px, py = uy, -ux  # starboard-hand side when inbound = port side of outbound... keep simple
    out = []
    def ll(xx, yy): return P.ll(xx, yy)
    def o(c, xx, yy, **k):
        lo, la = ll(xx, yy); d = dict(c=c, lon=round(lo, 5), lat=round(la, 5)); d.update(k); P.feat["obj"].append(d)
    # harbour light at the water-side point near the port
    o("LIGHTS", wx - ux * 0.25, wy - uy * 0.25, name=f"{name} Harbour Light", chr=rng.choice(["Fl G 3s 8M", "Fl R 3s 8M", "Oc 4s 10M", "Fl 2.5s 9M"]), col="W", major=False,
      att={"CATLIT": "harbour light"}, why="Harbour entrance light: confirms the entrance and gives a visual bearing on the final approach.")
    P.feat["names"].append(dict(lon=port["lon"], lat=port["lat"], t=name.upper() if big else name, s=11 if big else 9.5, land=True, rot=0))
    # built-up area
    ring = [ll(x + 1.6 * math.cos(a), y + 1.6 * math.sin(a)) for a in np.linspace(0, 2 * math.pi, 14, endpoint=False)]
    P.feat["areas"].append(dict(c="BUAARE", ring=[[round(a, 4), round(b, 4)] for a, b in ring], name=name, att={}, why="Built-up area."))
    if not big or run < 2.5: return dict(name=name, x=wx, y=wy, brg=brg, run=run, L=min(4.0, max(0.5, run - 0.5)))
    L = min(6.0, run - 0.5); ext = max(0.0, min(3.0, run - L - 0.3))
    # pilot boarding + fairway buoy + VTS line
    o("PILBOP", wx + ux * L, wy + uy * L, name=f"{name} Pilot", att={"CATPIL": "pilot boarding place", "COMCHA": "VHF 12/16"}, why="Pilot boarding place: arrive at the time agreed, make a lee, rig the ladder correctly.")
    o("BOYSAW", wx + ux * (L - 0.9), wy + uy * (L - 0.9), name=f"{name} Fairway", shape="sph", chr=rng.choice(["Mo(A) 10s", "LFl 10s", "Iso 4s"]), att={"CATSPM": "safe water", "COLOUR": "red/white"}, why="Safe-water (fairway) buoy: the start of the buoyed channel.")
    lo1, la1 = ll(wx + ux * (L + 0.8) + px * 2.0, wy + uy * (L + 0.8) + py * 2.0); lo2, la2 = ll(wx + ux * (L + 0.8) - px * 2.0, wy + uy * (L + 0.8) - py * 2.0)
    P.feat["lines"].append(dict(c="RDOCAL", pts=[[round(lo1, 4), round(la1, 4)], [round(lo2, 4), round(la2, 4)]], name=f"{name} VTS reporting line", att={"COMCHA": "VHF 12", "INFORM": "Report name, position, ETA, draught"}, why="Report to VTS when crossing the line."))
    # lateral buoys (inbound: starboard-hand = cone, port-hand = can)
    n = 0
    for k in np.arange(L - 1.8, 0.35, -0.9):
        n += 1
        bx, by = wx + ux * k, wy + uy * k
        o("BOYLAT", bx - px * 0.14, by - py * 0.14, name=f"{name} No.{2*n-1}", shape="cone", chr=rng.choice(["Fl G 3s", "Fl G 5s", "Q G"]), att={"CATLAM": "starboard-hand", "BOYSHP": "conical"}, why="Starboard-hand buoy (inbound): keep it to starboard.")
        o("BOYLAT", bx + px * 0.14, by + py * 0.14, name=f"{name} No.{2*n}", shape="can", chr=rng.choice(["Fl R 3s", "Fl R 5s", "Q R"]), att={"CATLAM": "port-hand", "BOYSHP": "can"}, why="Port-hand buoy (inbound): keep it to port.")
    # dredged channel (depth grids are carved before encoding)
    dv = rng.choice([11.0, 12.5, 14.0, 15.5, 16.0])
    pts = [(wx + ux * (L + ext + 0.3), wy + uy * (L + ext + 0.3)), (wx + ux * 0.3, wy + uy * 0.3), (wx - ux * 0.25, wy - uy * 0.25)]
    P.feat["drg"].append(dict(name=f"{name} approach channel (dredged)", hw=0.16, dv=dv, pts=[[round(a, 3), round(b, 3)] for a, b in pts]))
    # anchorage
    ax, ay = wx + ux * (L - 2.2) + px * 1.3, wy + uy * (L - 2.2) + py * 1.3
    ring = [ll(ax - 0.5, ay - 0.5), ll(ax + 0.5, ay - 0.5), ll(ax + 0.5, ay + 0.5), ll(ax - 0.5, ay + 0.5)]
    P.feat["areas"].append(dict(c="ACHARE", ring=[[round(a, 4), round(b, 4)] for a, b in ring], name=f"{name} anchorage", att={"CATACH": "general anchorage", "INFORM": "Vessels awaiting berth or pilot."}, why="Designated anchorage: wait here for the pilot or the berth."))
    # precautionary area at the fairway start
    P.feat["areas"].append(dict(c="PRCARE", circle=[round(v, 5) for v in ll(wx + ux * L, wy + uy * L)], r=1.2, name=f"{name} precautionary area", att={"INFORM": "Converging traffic at the pilot station. Keep listening watch VHF 12."}, why="Traffic converges at the pilot station: extra lookout, safe speed."))
    # landfall light on a prominent coastline point within 18 NM
    best = None
    for i in P.land_tree.query(Point(wx, wy).buffer(18)):
        for q in P.land[i][::3]:
            d = math.hypot(q[0] - wx, q[1] - wy)
            if d < 3 or d > 18: continue
            score = (q[0] - wx) * ux + (q[1] - wy) * uy + 0.4 * d
            if best is None or score > best[0]: best = (score, q)
    if best:
        q = best[1]
        o("LIGHTS", q[0], q[1], name=f"{name} Point Lighthouse", chr=rng.choice(["Fl 10s 25M", "Fl(2) 15s 22M", "Fl(3) 20s 20M", "LFl 12s 18M"]) , col="W", major=True, att={"CATLIT": "landfall light"}, why="Landfall light: the first light identified when approaching from sea. Check its character against the List of Lights.")
    res = dict(name=name, x=wx, y=wy, brg=brg, run=run, L=L, ext=ext)
    if port.get("rank", 9) <= 4: build_tss(P, res, name)
    return res

def lane_ring(P, cx, cy, ux, uy, px, py, off0, off1, a0, a1):
    """rectangle along the axis: across-track offsets off0..off1 (NM, +=starboard of outbound), along-track a0..a1"""
    pts = [(cx + ux * a + px * o, cy + uy * a + py * o) for a, o in ((a0, off0), (a1, off0), (a1, off1), (a0, off1))]
    return pts

def ring_clear(P, pts, margin=0.4):
    g = Polygon(pts).buffer(margin)
    return not any(P.land_polys[i].intersects(g) for i in P.land_tree.query(g))

def build_tss(P: Pack, inf, name):
    """traffic separation scheme on the approach: outbound lane, separation zone, inbound lane"""
    brg, L, run = inf["brg"], inf.get("L", 4), inf["run"]
    if run < L + 10: return False
    ux, uy = math.sin(math.radians(brg)), math.cos(math.radians(brg)); px, py = uy, -ux
    cx, cy = inf["x"], inf["y"]; a0, a1 = L + 1.2, min(L + 12, run - 1.0)
    zone = lane_ring(P, cx, cy, ux, uy, px, py, -0.25, 0.25, a0, a1)
    outl = lane_ring(P, cx, cy, ux, uy, px, py, 0.25, 1.35, a0, a1)
    inl = lane_ring(P, cx, cy, ux, uy, px, py, -1.35, -0.25, a0, a1)
    if not all(ring_clear(P, r) for r in (zone, outl, inl)): return False
    ll = lambda r: [[round(v, 5) for v in P.ll(x, y)] for x, y in r]
    why_l = "Traffic lane: proceed in the general direction of traffic flow (COLREG Rule 10). Join or leave at the termination, or at a small angle."
    P.feat["areas"].append(dict(c="TSEZNE", ring=ll(zone), name=f"{name} TSS separation zone", len=round(a1 - a0, 1), att={"CATTSS": "separation zone"}, why="Do not enter the separation zone except to cross or in an emergency (Rule 10)."))
    P.feat["areas"].append(dict(c="TSSLPT", ring=ll(outl), name=f"{name} TSS outbound lane", orient=round(brg % 360), len=round(a1 - a0, 1), att={"ORIENT": f"{round(brg % 360):03d}°", "CATTSS": "traffic lane"}, why=why_l))
    P.feat["areas"].append(dict(c="TSSLPT", ring=ll(inl), name=f"{name} TSS inbound lane", orient=round((brg + 180) % 360), len=round(a1 - a0, 1), att={"ORIENT": f"{round((brg + 180) % 360):03d}°", "CATTSS": "traffic lane"}, why=why_l))
    return True

def build_dangers(P: Pack, infos):
    """wrecks, obstructions, cardinal and isolated-danger marks: more of them closer in (shown progressively by SCAMIN)"""
    rng = random.Random(P.rid + "dng"); cg = P.cg; r = cg["res"]
    def o(c, x, y, **k):
        lo, la = P.ll(x, y); d = dict(c=c, lon=round(lo, 5), lat=round(la, 5)); d.update(k); P.feat["obj"].append(d)
    def water(x, y, mind=0.3):
        g = Point(x, y).buffer(mind)
        return not any(P.land_polys[i].intersects(g) for i in P.land_tree.query(g))
    # shelf wrecks (sparse, every pack)
    cand = np.argwhere((cg["depth"] > 12) & (cg["depth"] < 80) & (cg["dist"] > 2) & ~cg["land"])
    for j, i in [tuple(c) for c in cand[rng.sample(range(len(cand)), min(len(cand), 120, max(6, len(cand) // 900)))]] if len(cand) else []:
        x, y = i * r + rng.uniform(-.4, .4), j * r + rng.uniform(-.4, .4); z = float(cg["depth"][j, i])
        if rng.random() < 0.6: o("WRECKS", x, y, name="Wreck", depth=round(z * rng.uniform(.4, .8), 1), safe=False, scamin=1100000, att={"CATWRK": "dangerous wreck", "VALSOU": "sounded"}, why="Dangerous wreck: least depth may be less than your safety contour. Keep clear.")
        else: o("WRECKS", x, y, name="Wreck (non-dangerous)", depth=None, safe=True, scamin=350000, att={"CATWRK": "non-dangerous wreck"}, why="Non-dangerous wreck: deep enough for surface navigation, but avoid anchoring or trawling here.")
    # near each equipped port: wrecks, obstructions, cardinal marks, isolated danger mark
    for inf in infos:
        cx, cy, brg, L = inf["x"], inf["y"], inf["brg"], inf.get("L", 4)
        ux, uy = math.sin(math.radians(brg)), math.cos(math.radians(brg)); px, py = uy, -ux
        prng = random.Random(inf["port"]["name"])
        for k in range(prng.randint(3, 6)):
            a, off = prng.uniform(1, L + 8), prng.choice([-1, 1]) * prng.uniform(1.0, 3.5)
            x, y = cx + ux * a + px * off, cy + uy * a + py * off
            if not water(x, y): continue
            kind = prng.random()
            if kind < 0.35: o("WRECKS", x, y, name="Wreck", depth=round(prng.uniform(3, 12), 1), safe=False, scamin=180000, att={"CATWRK": "dangerous wreck", "VALSOU": "sounded"}, why="Dangerous wreck near the approach: check its depth against your safety depth.")
            elif kind < 0.6: o("OBSTRN", x, y, name="Obstruction", depth=round(prng.uniform(2, 9), 1), scamin=120000, att={"CATOBS": "foul ground", "VALSOU": "sounded"}, why="Obstruction: foul ground, do not anchor. Check the least depth.")
            else:
                z = round(prng.uniform(1.2, 6.5), 1)
                o("UWTROC", x, y, name="Rock", depth=z, cat="base", scamin=260000, att={"VALSOU": f"{z} m", "WATLEV": "always under water", "NATSUR": "rock"}, why="Isolated danger: less water than your safety contour. Keep well clear.")
                if prng.random() < 0.5:   # isolated danger mark on it
                    o("BOYISD", x + 0.05, y + 0.05, name=f"{inf['port']['name']} Isolated Danger", shape="pillar", chr="Fl(2) 5s", scamin=180000, att={"CATSPM": "isolated danger", "COLOUR": "black/red/black"}, why="Isolated danger mark: navigable water all round, but do not pass close.")
                else:                     # cardinal mark on the fairway side of the danger
                    side = (x - cx) * px + (y - cy) * py
                    bx, by = x - px * 0.25 * (1 if side > 0 else -1), y - py * 0.25 * (1 if side > 0 else -1)
                    dx, dy = bx - x, by - y; card = ("N" if dy > 0 else "S") if abs(dy) >= abs(dx) else ("E" if dx > 0 else "W")
                    chr_ = {"N": "Q", "E": "Q(3) 10s", "S": "Q(6)+LFl 15s", "W": "Q(9) 15s"}[card]
                    if water(bx, by, 0.15): o("BOYCAR", bx, by, name=f"{inf['port']['name']} {card} Cardinal", card=card, shape="pillar", chr=chr_, scamin=260000, att={"CATCAM": {"N": "north", "E": "east", "S": "south", "W": "west"}[card] + " cardinal", "COLOUR": "black/yellow"}, why=f"{card} cardinal mark: pass on its {card} side; the danger lies to the {'south' if card == 'N' else 'west' if card == 'E' else 'north' if card == 'S' else 'east'}.")
    # cardinal marks on the shallowest shelf shoals (voyage-scale dangers)
    for x, y, top, typ in sorted(P.shoals, key=lambda s: s[2])[: max(4, len(P.shoals) // 6)]:
        card = rng.choice("NESW"); d = 0.35; bx, by = x + {"N": (0, d), "E": (d, 0), "S": (0, -d), "W": (-d, 0)}[card][0], y + {"N": (0, d), "E": (d, 0), "S": (0, -d), "W": (-d, 0)}[card][1]
        if not water(bx, by, 0.1): continue
        o("BOYCAR", bx, by, name=f"{card} Cardinal ({typ})", card=card, shape="pillar", chr={"N": "Q", "E": "Q(3) 10s", "S": "Q(6)+LFl 15s", "W": "Q(9) 15s"}[card], scamin=400000, att={"CATCAM": {"N": "north", "E": "east", "S": "south", "W": "west"}[card] + " cardinal"}, why=f"{card} cardinal mark: pass on its {card} side.")

def build_names(P: Pack):
    bbox = box(P.lon0, P.lat0, P.lon1, P.lat1)
    # seas
    for f in load_json("ne_10m_geography_marine_polys.geojson")["features"]:
        g = shape(f["geometry"])
        if not g.intersects(bbox): continue
        gi = g.intersection(bbox)
        if gi.is_empty or gi.area < 0.3: continue
        p = gi.representative_point(); nm = f["properties"]["name"]
        big = f["properties"].get("scalerank", 5) <= 1
        P.feat["names"].append(dict(lon=round(p.x, 4), lat=round(p.y, 4), t=nm.upper() if big else nm, s=16 if big else 13, land=False, rot=0))
    # countries
    for f in load_json("ne_50m_admin_0_countries.geojson")["features"]:
        g = shape(f["geometry"])
        if not g.intersects(bbox): continue
        gi = g.intersection(bbox)
        if gi.is_empty or gi.area < 0.8: continue
        p = gi.representative_point()
        P.feat["names"].append(dict(lon=round(p.x, 4), lat=round(p.y, 4), t=f["properties"]["NAME"].upper(), s=15, land=True, rot=0))
    # islands / capes
    for f in load_json("ne_10m_geography_regions_polys.geojson")["features"]:
        pr = f["properties"]
        if pr.get("FEATURECLA") not in ("Island", "Island group", "Peninsula") or pr.get("SCALERANK", 9) > 6: continue
        g = shape(f["geometry"])
        if not g.intersects(bbox): continue
        p = g.intersection(bbox).representative_point()
        P.feat["names"].append(dict(lon=round(p.x, 4), lat=round(p.y, 4), t=pr["NAME"], s=10.5, land=True, rot=0))
    for f in load_json("ne_10m_geography_regions_points.geojson")["features"]:
        pr = f["properties"]
        if pr.get("featurecla") != "cape": continue
        lon, lat = f["geometry"]["coordinates"]
        if P.lon0 < lon < P.lon1 and P.lat0 < lat < P.lat1:
            P.feat["names"].append(dict(lon=round(lon, 4), lat=round(lat, 4), t=pr["name"], s=9.5, land=True, rot=0))
    # coastal cities (within ~8 NM of the coast)
    portnames = {p["name"].lower() for p in P.ports}
    for f in load_json("ne_10m_populated_places_simple.geojson")["features"]:
        pr = f["properties"]; lon, lat = f["geometry"]["coordinates"]
        if not (P.lon0 < lon < P.lon1 and P.lat0 < lat < P.lat1): continue
        if pr.get("scalerank", 9) > 6 or pr["name"].lower() in portnames: continue
        if any(abs(p["lon"] - lon) < 0.15 and abs(p["lat"] - lat) < 0.15 for p in P.ports): continue
        x, y = P.xy(lon, lat); r = P.cg["res"]; i, j = int(round(x / r)), int(round(y / r))
        if not (0 <= i < P.cg["nx"] and 0 <= j < P.cg["ny"]): continue
        # near coast: some sea within 8 NM
        win = P.cg["land"][max(0, j - 8):j + 9, max(0, i - 8):i + 9]
        if win.all(): continue
        P.feat["names"].append(dict(lon=round(lon, 4), lat=round(lat, 4), t=pr["name"], s=10 if pr.get("scalerank", 9) <= 3 else 9, land=True, rot=0))

def build_shoals(P: Pack):
    """sparse isolated dangers on the shelf (from the coarse grid) + reef markers"""
    cg = P.cg; rng = P.rng; r = cg["res"]
    cand = np.argwhere((cg["depth"] > 1.5) & (cg["depth"] < 18) & (cg["dist"] > 1.5) & ~cg["land"])
    rng.shuffle(cand := list(map(tuple, cand)))
    n = min(len(cand), max(8, int(len(cand) / 300)))
    for j, i in cand[:n]:
        x, y = i * r + rng.uniform(-0.4, 0.4), j * r + rng.uniform(-0.4, 0.4)
        top = round(max(0.6, float(cg["depth"][j, i]) * rng.uniform(0.25, 0.7)), 1)
        P.shoals.append([round(x, 3), round(y, 3), top, rng.choice(["rock", "shoal", "reef", "shoal"])])

def build_ais(P: Pack, majors):
    rng = P.rng
    names = ["OCEAN PIONEER", "MSC AURORA", "PACIFIC TRADER", "STAR HARMONY", "NORDIC SPIRIT", "GOLDEN WAVE", "ATLANTIC CROWN", "EVER BRIGHT", "SEA DRAGON", "CAPE HORIZON", "BLUE MERIDIAN", "ORIENT GLORY"]
    types = [("Container ship", 17, 300), ("Bulk carrier", 12, 225), ("Tanker", 12, 245), ("Ro-Ro", 16, 180), ("General cargo", 11, 120), ("LNG carrier", 15, 290), ("Passenger", 18, 230)]
    pairs = []
    mj = majors[:]; rng.shuffle(mj)
    for a in mj:
        for b in mj:
            if a is b: continue
            d = math.hypot(a["x"] - b["x"], a["y"] - b["y"])
            if 40 < d < 900: pairs.append((a, b))
    rng.shuffle(pairs)
    k = 0
    for a, b in pairs:
        if k >= 9: break
        def outw(inf):
            ux, uy = math.sin(math.radians(inf["brg"])), math.cos(math.radians(inf["brg"])); L = min(inf.get("L", 3) + 2.0, max(0.5, inf["run"] - 0.3))
            return (inf["x"] + ux * L, inf["y"] + uy * L)
        rt = P.route(outw(a), outw(b))
        if not rt or len(rt) < 2: continue
        rt = [(a["x"] + math.sin(math.radians(a["brg"])) * 0.6, a["y"] + math.cos(math.radians(a["brg"])) * 0.6)] + list(rt) + [(b["x"] + math.sin(math.radians(b["brg"])) * 0.6, b["y"] + math.cos(math.radians(b["brg"])) * 0.6)]
        typ, sog, ln = rng.choice(types)
        P.ais.append(dict(name=names[k % len(names)], mmsi=str(rng.randint(200000000, 775999999)), type=typ, sog=sog, len=ln, path=[[round(v, 5) for v in P.ll(*p)] for p in rt], t=round(rng.random() * 0.8, 2)))
        k += 1
    # anchored + fishing near the start port
    s = majors[0]
    P.ais.append(dict(name="SEA FORTUNE", mmsi=str(rng.randint(200000000, 775999999)), type="Bulk carrier", sog=0, len=190, path=[[round(v, 5) for v in P.ll(s["x"] + math.sin(math.radians(s["brg"])) * 3.2, s["y"] + math.cos(math.radians(s["brg"])) * 3.2)]], anch=True))
    fx, fy = s["x"] + math.sin(math.radians(s["brg"] + 40)) * 7, s["y"] + math.cos(math.radians(s["brg"] + 40)) * 7
    P.ais.append(dict(name="F/V MARIA", mmsi=str(rng.randint(200000000, 775999999)), type="Fishing", sog=3, len=22, path=[[round(v, 5) for v in P.ll(fx, fy)], [round(v, 5) for v in P.ll(fx + 2, fy + 1)], [round(v, 5) for v in P.ll(fx + 1, fy - 1.5)]], t=0))

# ----------------------------------------------------------------------------- main build
def build(rid, outdir):
    R = REGIONS[rid]; P = Pack(rid, R)
    print(f"== {rid}: {R['name']}  bb={R['bb']}  WX={P.WX:.0f} WY={P.WY:.0f} NM")
    P.load(); P.coarse()
    major = [p for p in P.ports if p.get("curated")]
    if R.get("gen"): major = sorted(P.ports, key=lambda p: p["rank"])[:10]
    # order: start, dest first
    def find(nm): return next((p for p in P.ports if p["name"].lower() == nm.lower()), None)
    start, dest = find(R["start"] or ""), find(R["dest"] or "")
    if not start and P.ports: start = sorted(P.ports, key=lambda p: p["rank"])[0]
    if not dest and len(P.ports) > 1: dest = sorted([p for p in P.ports if p is not start], key=lambda p: p["rank"])[0]
    for p in (start, dest):
        if p and p not in major: major.insert(0, p)
    start = start or dict(name=""); dest = dest or dict(name="")
    # port features first (dredged channels must exist before the grids are built)
    infos = []
    seen = set(); equipped = []
    for p in sorted(P.ports, key=lambda p: (p["name"] not in (start["name"], dest["name"]), p["rank"])):
        if p["name"] in seen: continue
        seen.add(p["name"])
        px, py = P.xy(p["lon"], p["lat"])
        big = p in major and not any(math.hypot(px - a, py - b) < 7 for a, b in equipped)
        inf = build_port_features(P, p, big=big)
        if inf and big: inf["port"] = p; infos.append(inf); equipped.append((px, py))
        elif inf and p in major: p["near"] = True
    build_names(P); build_shoals(P); build_dangers(P, infos)
    # real OpenSeaMap seamarks replace the simulated aids/dangers/areas where we have them (tools/osm_seamarks.py)
    real = [a for a, A in OSM_AREAS.items() if A["region"] == rid]
    for a in real: apply_real_seamarks(P.feat, a, iala=R["iala"])
    if real and "OpenSeaMap" not in R.get("desc", ""): R["desc"] += " · real OpenSeaMap seamarks (buoys, lights, TSS, anchorages, wrecks) in the " + ", ".join(OSM_AREAS[a]["name"] for a in real)
    if R.get("gen"):
        seas = [n["t"] for n in P.feat["names"] if not n["land"]][:3]; lands = [n["t"].title() for n in P.feat["names"] if n["land"] and n["s"] >= 15][:4]
        R["desc"] = ", ".join(seas + lands) or "Open ocean"
        if seas: R["name"] = R["name"].replace("General", seas[0].title() + " ·", 1)
    # --- cells
    pfx = R["pfx"]; nid = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    def cid(b): nid[b] += 1; return f"{pfx}{b}{nid[b]:05d}"
    P.add_cell(cid(1), 1, f"{R['name']} overview", 0, 0, P.WX, P.WY, 2.0 if R.get("gen") else 1.0, P.feat["drg"])
    # band 2: 5°x5° tiles that contain coast
    T2 = 5.0
    lon = P.lon0
    while lon < P.lon1 - 0.01:
        lat = P.lat0
        while lat < P.lat1 - 0.01:
            x0, y0 = P.xy(lon, lat); x1, y1 = P.xy(min(lon + T2, P.lon1), min(lat + T2, P.lat1))
            if (~P.cg["land"][int(y0):int(y1) + 1, int(x0):int(x1) + 1]).any():
                coast = P.land_tree.query(box(x0 - 10, y0 - 10, x1 + 10, y1 + 10)).size > 0
                P.add_cell(cid(2), 2, f"General {abs(lat):.0f}°{'N' if lat >= 0 else 'S'} {abs(lon):.0f}°{'E' if lon >= 0 else 'W'}", x0, y0, x1, y1, 0.5 if coast else 1.0, P.feat["drg"])
            lat += T2
        lon += T2
    # band 3: coastal cells around major ports (2.4° x 2.4°)
    done3 = []
    for inf in infos:
        p = inf["port"]; cx, cy = inf["x"], inf["y"]
        if any(math.hypot(cx - a, cy - b) < 45 for a, b in done3): continue
        done3.append((cx, cy))
        x0, y0 = max(0, cx - 40), max(0, cy - 40); x1, y1 = min(P.WX, cx + 40), min(P.WY, cy + 40)
        P.add_cell(cid(3), 3, f"{p['name']} coastal (voyage)", x0, y0, x1, y1, 0.25, P.feat["drg"])
    # band 4: approach cells (20 NM box) for major ports
    for inf in infos:
        p = inf["port"]; cx, cy = inf["x"], inf["y"]
        if any(c["band"] == 4 and c["box"][0] <= cx <= c["box"][2] and c["box"][1] <= cy <= c["box"][3] for c in P.cells): continue
        x0, y0 = max(0, cx - 11), max(0, cy - 11); x1, y1 = min(P.WX, cx + 11), min(P.WY, cy + 11)
        P.add_cell(cid(4), 4, f"{p['name']} approaches", x0, y0, x1, y1, 0.075, P.feat["drg"])
    # band 5: harbour cells (berths, inner channel) for every equipped port
    nid[5] = 0
    for inf in infos:
        p = inf["port"]; cx, cy = inf["x"], inf["y"]
        x0, y0 = max(0, cx - 3.5), max(0, cy - 3.5); x1, y1 = min(P.WX, cx + 3.5), min(P.WY, cy + 3.5)
        P.add_cell(cid(5), 5, f"{p['name']} harbour", x0, y0, x1, y1, 0.02, P.feat["drg"])
    # --- general (overview land), AIS, sample route, AIO, ENC list
    general = P.land_rings(0, 0, P.WX, P.WY, 1.5)
    if len(infos) < 2: return write_pack(P, R, rid, outdir, general, infos)
    s_inf = next((i for i in infos if i["port"] is start), None) or infos[0]; start = s_inf["port"]
    d_inf = next((i for i in infos if i["port"] is dest and i is not s_inf), None) or next(i for i in infos if i is not s_inf); dest = d_inf["port"]
    print(f"  start {start['name']} → dest {dest['name']}")
    build_ais(P, [s_inf, d_inf] + [i for i in infos if i not in (s_inf, d_inf)])
    sx, sy = s_inf["x"] + math.sin(math.radians(s_inf["brg"])) * s_inf.get("L", 4), s_inf["y"] + math.cos(math.radians(s_inf["brg"])) * s_inf.get("L", 4)
    dx, dy = d_inf["x"] + math.sin(math.radians(d_inf["brg"])) * d_inf.get("L", 4), d_inf["y"] + math.cos(math.radians(d_inf["brg"])) * d_inf.get("L", 4)
    def outward(inf, L):
        ux, uy = math.sin(math.radians(inf["brg"])), math.cos(math.radians(inf["brg"]))
        ext = inf.get("ext", max(0.0, min(3.0, inf["run"] - L - 0.3)))
        return (inf["x"] + ux * (L + ext), inf["y"] + uy * (L + ext))
    so, do_ = outward(s_inf, s_inf.get("L", 4)), outward(d_inf, d_inf.get("L", 4))
    mid_rt = P.route(so, do_) or [so, do_]
    rt = [(sx, sy)] + ([so] if math.hypot(so[0] - sx, so[1] - sy) > 0.4 else []) + list(mid_rt[1:-1]) + ([do_] if math.hypot(do_[0] - dx, do_[1] - dy) > 0.4 else []) + [(dx, dy)]
    sample = []
    for k, (x, y) in enumerate(rt):
        lo, la = P.ll(x, y)
        nm = f"{start['name'].upper()} PILOT" if k == 0 else f"{dest['name'].upper()} PILOT" if k == len(rt) - 1 else f"WPT {k+1:02d}"
        near = k <= 1 or k >= len(rt) - 2
        sample.append([round(lo, 4), round(la, 4), nm, 8 if k in (0, len(rt) - 1) else 10 if near else 14, 0.3 if near else 0.5])
    hdg = (math.degrees(math.atan2(rt[1][0] - rt[0][0], rt[1][1] - rt[0][1])) + 360) % 360 if len(rt) > 1 else s_inf["brg"]
    slo, sla = P.ll(sx, sy)
    # AIO notices
    mid = rt[len(rt) // 2]; mlo, mla = P.ll(*mid)
    P.aio = [dict(id="T&P 0211(T)/26", kind="T", circle=[round(v, 4) for v in P.ll(d_inf["x"] + math.sin(math.radians(d_inf["brg"])) * 1.5, d_inf["y"] + math.cos(math.radians(d_inf["brg"])) * 1.5)], r=0.4, title=f"{dest['name']}: dredging in the approach channel", text="Dredging operations in the approach channel. Least depth reduced to 9.0 m. Dredger on station, pass at slow speed, VHF 12.", depth=9.0),
             dict(id="T&P 0237(P)/26", kind="P", circle=[round(mlo + 0.15, 4), round(mla - 0.12, 4)], r=0.5, title="New dangerous wreck reported", text="Sunken vessel reported, depth unknown, not yet surveyed. Give a wide berth (≥ 1 NM).", depth=5)]
    P.enc_build()
    return write_pack(P, R, rid, outdir, general, infos, dict(start=dict(lon=round(slo, 4), lat=round(sla, 4), hdg=round(hdg), port=start["name"]), dest=dest["name"], sample=sample))

def _enc_build(P):
    rng = P.rng
    for k, c in enumerate(P.cells):
        lo0, la0 = P.ll(c["box"][0], c["box"][1]); lo1, la1 = P.ll(c["box"][2], c["box"][3])
        ed, upd = rng.randint(2, 5), rng.randint(4, 14)
        lat = upd + (3 if (c["band"] == 4 and k == len(P.cells) - 2) else 0)
        P.enc.append([c["id"], c["band"], c["name"], [round(lo0, 3), round(la0, 3), round(lo1, 3), round(la1, 3)], ed, upd, lat, f"2026-{rng.randint(6,9):02d}-{rng.randint(1,28):02d}", "2027-06-30"])
Pack.enc_build = _enc_build

def write_pack(P, R, rid, outdir, general, infos, voy=None):
    if voy is None:   # open-ocean / remote pack: start in deep water near the first port, else the middle of the area
        if not P.enc: P.enc_build()
        if infos: inf = infos[0]; x, y, brg = inf["x"] + math.sin(math.radians(inf["brg"])) * inf.get("L", 3), inf["y"] + math.cos(math.radians(inf["brg"])) * inf.get("L", 3), inf["brg"]; port = inf["port"]["name"]
        else:
            w = P.water_near(P.WX / 2, P.WY / 2, maxr=400) or (P.WX / 2, P.WY / 2); x, y = w; brg, _ = P.sea_dir(x, y); port = "open sea"
        lo, la = P.ll(x, y); voy = dict(start=dict(lon=round(lo, 4), lat=round(la, 4), hdg=round(brg), port=port), dest="", sample=[])
    offs = [0]
    for b in P.depth_blobs: offs.append(offs[-1] + len(b))
    chart = dict(pack=rid, name=R["name"], desc=R["desc"], gen=bool(R.get("gen")), lon0=P.lon0, lat0=P.lat0, lon1=P.lon1, lat1=P.lat1, C=P.C, WX=P.WX, WY=P.WY, iala=R["iala"], tz=R["tz"], **voy,
                 cells=P.cells, offs=offs[:-1], general=general, shoals=P.shoals, peaks=[], drg=[], feat=P.feat, ais=P.ais, aio=P.aio, enc=P.enc,
                 credit="Coastline: OpenStreetMap contributors (ODbL) via geo-maps; bathymetry, ports and names: Natural Earth (public domain). Depths, aids, traffic and notices are simulated training data." + (OSM_CREDIT if P.feat.get("real") else ""))
    os.makedirs(outdir, exist_ok=True)
    with gzip.open(os.path.join(outdir, f"ecdis_{rid}_chart.gz"), "wb", compresslevel=9) as f: f.write(json.dumps(chart, separators=(",", ":")).encode())
    with gzip.open(os.path.join(outdir, f"ecdis_{rid}_depth.gz"), "wb", compresslevel=9) as f:
        for b in P.depth_blobs: f.write(b)
    sz = lambda n: os.path.getsize(os.path.join(outdir, n)) / 1e6
    print(f"  wrote ecdis_{rid}_chart.gz {sz(f'ecdis_{rid}_chart.gz'):.1f} MB  ecdis_{rid}_depth.gz {sz(f'ecdis_{rid}_depth.gz'):.1f} MB  cells={len(P.cells)} obj={len(P.feat['obj'])} names={len(P.feat['names'])} ais={len(P.ais)}")
    return chart

if __name__ == "__main__":
    args = sys.argv[1:]
    out = "/home/claude/work/out"
    if "--out" in args: out = args[args.index("--out") + 1]; args = [a for a in args if a not in ("--out", out)]
    for rid in (args or ["sea"]):
        if rid == "all":
            for r in REGIONS: build(r, out)
        else: build(rid, out)
