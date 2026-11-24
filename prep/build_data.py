"""Pack the street graph + weekday GTFS (OASA buses/trolleys, STASY metro/tram) into
binary files the browser can route on.

Output (site/data/):
  net.b64.json street graph: nodes (x,y metres), edges (u,v,len), edge polylines
  pt.b64.json stops, connections (sorted by departure), stop footpaths, trip modes
  meta.json projection, counts, rail line drawings, landmarks
"""
import os, json, struct
import numpy as np, pandas as pd, osmnx as ox
from scipy.spatial import cKDTree

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "site", "data"); os.makedirs(OUT, exist_ok=True)
BUS, RAIL = os.path.join(ROOT, "dl", "bus"), os.path.join(ROOT, "dl", "rail")
BUS_SERVICE = {"day_2"}            # Tuesday
RAIL_SERVICE = {"8"}               # Tuesday 2026-07-07
T_MIN, T_MAX = 6 * 3600 + 30 * 60, 10 * 3600 + 30 * 60   # connections departing in this window
LAT0, LON0 = 37.9755, 23.7348      # Syntagma, projection origin
M_PER_DEG_LAT = 111_320.0
M_PER_DEG_LON = 111_320.0 * np.cos(np.radians(LAT0))

def proj(lon, lat):
    return (np.asarray(lon) - LON0) * M_PER_DEG_LON, (np.asarray(lat) - LAT0) * M_PER_DEG_LAT

# ---------------- streets ----------------
G = ox.load_graphml(os.path.join(HERE, "roads2.graphml"))   # directed: one-way streets kept
nodes = list(G.nodes)
nid = {n: i for i, n in enumerate(nodes)}
nlon = np.array([G.nodes[n]["x"] for n in nodes]); nlat = np.array([G.nodes[n]["y"] for n in nodes])
nx_, ny_ = proj(nlon, nlat)

# road class: 0 motorway, 1 trunk, 2 primary, 3 secondary, 4 tertiary, 5 residential/unclassified, 6 living street, 7 pedestrian
CLS = {"motorway": 0, "trunk": 1, "primary": 2, "secondary": 3, "tertiary": 4, "residential": 5,
       "unclassified": 5, "road": 5, "living_street": 6, "pedestrian": 7}
def first(v): return v if isinstance(v, list) else [v]
def road_class(d):
    return min(CLS.get(str(h).replace("_link", ""), 5) for h in first(d.get("highway", "residential")))
eu, ev, elen, eoff, pts, ecls, eflag = [], [], [], [0], [], [], []
seen = {}
def simplify(coords, tol=4.0):
    # Douglas-Peucker on projected coords (metres)
    if len(coords) <= 2: return coords
    a, b = np.array(coords[0]), np.array(coords[-1])
    d = b - a; L = np.hypot(*d)
    arr = np.array(coords[1:-1])
    if L == 0: dist = np.hypot(*(arr - a).T)
    else: dist = np.abs(d[0] * (arr[:, 1] - a[1]) - d[1] * (arr[:, 0] - a[0])) / L
    i = int(np.argmax(dist))
    if dist[i] < tol: return [coords[0], coords[-1]]
    return simplify(coords[: i + 2], tol)[:-1] + simplify(coords[i + 1 :], tol)

for u, v, k, d in G.edges(keys=True, data=True):
    key = (min(u, v), max(u, v), round(d.get("length", 0), 1))
    car = "no" not in [str(x) for x in first(d.get("motor_vehicle", ""))]
    if key in seen:
        i = seen[key]
        if car: eflag[i] |= 2 if eu[i] == nid[u] else 4
        continue
    seen[key] = len(eu)
    ui, vi = nid[u], nid[v]
    if "geometry" in d:
        lo, la = np.array(d["geometry"].coords).T
        x, y = proj(lo, la)
        c = list(zip(x.tolist(), y.tolist()))
        # orient geometry from u to v
        if np.hypot(c[0][0] - nx_[ui], c[0][1] - ny_[ui]) > np.hypot(c[-1][0] - nx_[ui], c[-1][1] - ny_[ui]):
            c = c[::-1]
        c = simplify(c)[1:-1]
    else:
        c = []
    rc = road_class(d)
    walk = rc != 0 and "no" not in [str(x) for x in first(d.get("foot", ""))]
    eu.append(ui); ev.append(vi); elen.append(d.get("length", 0.0))
    ecls.append(rc); eflag.append((1 if walk else 0) | (2 if car and rc != 7 else 0))
    pts.extend(c); eoff.append(len(pts))
eflag = np.array(eflag, "u1"); ecls = np.array(ecls, "u1")
walk_node = np.zeros(len(nodes), bool)
walk_node[np.array(eu)[eflag & 1 > 0]] = True; walk_node[np.array(ev)[eflag & 1 > 0]] = True
print("edges by class", np.bincount(ecls), "walkable", int((eflag & 1).sum()), "car both ways", int(((eflag & 6) == 6).sum()),
      "car one-way", int(((eflag & 6) == 2).sum()))

print(f"streets: {len(nodes)} nodes, {len(eu)} edges, {len(pts)} shape points")
with open(os.path.join(OUT, "net.bin"), "wb") as f:
    f.write(struct.pack("<III", len(nodes), len(eu), len(pts)))
    f.write(np.column_stack([nx_, ny_]).astype("<f4").tobytes())
    f.write(np.array(eu, "<u4").tobytes()); f.write(np.array(ev, "<u4").tobytes())
    f.write(np.array(elen, "<f4").tobytes())
    f.write(np.array(eoff, "<u4").tobytes())
    f.write(np.array(pts, "<f4").reshape(-1, 2).tobytes() if pts else b"")
    f.write(ecls.tobytes()); f.write(eflag.tobytes())

# ---------------- transit ----------------
def tsec(s):
    h, m, x = s.str.split(":", expand=True).astype(int).T.values
    return h * 3600 + m * 60 + x

def load(folder, services, prefix):
    trips = pd.read_csv(os.path.join(folder, "trips.txt"), dtype=str)
    routes = pd.read_csv(os.path.join(folder, "routes.txt"), dtype=str)
    trips = trips[trips.service_id.isin(services)].merge(routes[["route_id", "route_short_name", "route_type"]], on="route_id")
    st = pd.read_csv(os.path.join(folder, "stop_times.txt"), dtype=str,
                     usecols=["trip_id", "arrival_time", "departure_time", "stop_id", "stop_sequence"])
    st = st[st.trip_id.isin(set(trips.trip_id))].copy()
    st["arr"], st["dep"] = tsec(st.arrival_time), tsec(st.departure_time)
    st["seq"] = st.stop_sequence.astype(int)
    st["stop_id"] = prefix + st.stop_id; st["trip_id"] = prefix + st.trip_id
    trips["trip_id"] = prefix + trips.trip_id
    stops = pd.read_csv(os.path.join(folder, "stops.txt"), dtype=str)
    stops["stop_id"] = prefix + stops.stop_id
    return trips, st[["trip_id", "stop_id", "seq", "arr", "dep"]], stops

bt, bst, bstops = load(BUS, BUS_SERVICE, "b")
rt, rst, rstops = load(RAIL, RAIL_SERVICE, "r")

# Hellenic Train feed (community-built, jbb.ghsq.de): Proastiakos = route_type 109; keep rail trips through Athens
HT, HT_DATE = os.path.join(ROOT, "dl", "ht"), "20261201"   # Tuesday
cd = pd.read_csv(os.path.join(HT, "calendar_dates.txt"), dtype=str)
hsvc = set(cd[(cd.date == HT_DATE) & (cd.exception_type == "1")].service_id)
ht, hst, hstops = load(HT, hsvc, "h")
hroutes = pd.read_csv(os.path.join(HT, "routes.txt"), dtype=str)
ht = ht.merge(hroutes[["route_id", "agency_id"]], on="route_id")
ht = ht[(ht.agency_id == "hellenic-train") & ht.route_type.isin(["2", "100", "101", "102", "103", "106", "109"])]
hstops["lat"], hstops["lon"] = hstops.stop_lat.astype(float), hstops.stop_lon.astype(float)
athens = set(hstops[hstops.lon.between(23.58, 23.97) & hstops.lat.between(37.84, 38.13)].stop_id)
n_in = hst[hst.stop_id.isin(athens)].groupby("trip_id").size()
ht = ht[ht.trip_id.isin(n_in[n_in >= 2].index)]
hst = hst[hst.trip_id.isin(set(ht.trip_id))]
print(f"suburban/regional rail trips through Athens: {len(ht)} ({(ht.route_type=='109').sum()} Proastiakos)")
trips = pd.concat([bt, rt, ht]); st = pd.concat([bst, rst, hst]); stops = pd.concat([bstops, rstops, hstops])
print(f"trips: {len(bt)} bus, {len(rt)} rail; stop_times {len(st)}")

# mode: 0 bus, 1 trolley, 2 metro, 3 tram, 4 suburban rail
def mode(r):
    if r.trip_id.startswith("h"): return 4
    if r.route_id.startswith("r") or r.trip_id.startswith("r"):
        return 3 if r.route_type == "0" else 2
    return 1 if r.route_type == "11" else 0
trips["mode"] = [mode(r) for r in trips.itertuples()]

st = st.sort_values(["trip_id", "seq"])
nxt = st.groupby("trip_id").shift(-1)
conn = pd.DataFrame({"trip": st.trip_id, "a": st.stop_id, "b": nxt.stop_id, "td": st.dep, "ta": nxt.arr}).dropna()
conn = conn[(conn.td >= T_MIN) & (conn.td <= T_MAX)]
conn["ta"] = conn.ta.astype(int)
conn = conn[conn.ta >= conn.td]

used = pd.unique(pd.concat([conn.a, conn.b]))
stops = stops[stops.stop_id.isin(used)].drop_duplicates("stop_id").reset_index(drop=True)
stops["lat"], stops["lon"] = stops.stop_lat.astype(float), stops.stop_lon.astype(float)
sx, sy = proj(stops.lon.values, stops.lat.values)
sidx = {s: i for i, s in enumerate(stops.stop_id)}

# snap stops to nearest street node
widx = np.flatnonzero(walk_node)
tree = cKDTree(np.column_stack([nx_[widx], ny_[widx]]))
dist, near = tree.query(np.column_stack([sx, sy])); near = widx[near]
print(f"stops: {len(stops)}, snap distance median {np.median(dist):.0f} m, p95 {np.percentile(dist,95):.0f} m")

trip_ids = pd.unique(conn.trip)
tidx = {t: i for i, t in enumerate(trip_ids)}
tmode = trips.set_index("trip_id").loc[trip_ids, "mode"].values.astype("u1")
conn = conn.sort_values(["td", "ta"])
ca = conn.a.map(sidx).values; cb = conn.b.map(sidx).values
ctrip = conn.trip.map(tidx).values
ctd = (conn.td.values - T_MIN).astype("<u2"); cta = (conn.ta.values - T_MIN).astype("<u2")
print(f"connections {len(conn)} for {len(trip_ids)} trips")

# stop-to-stop footpaths (straight line x1.3 detour, <= 350 m)
stree = cKDTree(np.column_stack([sx, sy]))
pairs = stree.query_pairs(270, output_type="ndarray")
pairs = np.vstack([pairs, pairs[:, ::-1]])
fd = np.hypot(sx[pairs[:, 0]] - sx[pairs[:, 1]], sy[pairs[:, 0]] - sy[pairs[:, 1]]) * 1.3
order = np.lexsort((fd, pairs[:, 0])); pairs, fd = pairs[order], fd[order]
foff = np.searchsorted(pairs[:, 0], np.arange(len(stops) + 1)).astype("<u4")
print(f"footpaths {len(pairs)}")

with open(os.path.join(OUT, "pt.bin"), "wb") as f:
    f.write(struct.pack("<IIII", len(stops), len(conn), len(trip_ids), len(pairs)))
    f.write(np.column_stack([sx, sy]).astype("<f4").tobytes())
    f.write(near.astype("<u4").tobytes()); f.write(dist.astype("<f4").tobytes())
    f.write(ca.astype("<u4").tobytes()); f.write(cb.astype("<u4").tobytes())
    f.write(ctrip.astype("<u4").tobytes())
    f.write(ctd.tobytes()); f.write(cta.tobytes())
    f.write(tmode.tobytes())
    f.write(b"\0" * ((-len(tmode)) % 4))
    f.write(foff.tobytes()); f.write(pairs[:, 1].astype("<u4").tobytes()); f.write(fd.astype("<f4").tobytes())

# rail lines for drawing: stop sequence of the longest trip per route
lines = []
COL = {"M1": "#00a651", "M2": "#ed1c24", "M3": "#0072bc", "T6": "#f7a600", "T7": "#f7a600"}
for rid, grp in rt.groupby("route_short_name"):
    tl = rst[rst.trip_id.isin(grp.trip_id)].groupby("trip_id").size()
    best = tl.idxmax()
    seq = rst[rst.trip_id == best].sort_values("seq").stop_id
    s = rstops.set_index("stop_id").loc[seq]
    x, y = proj(s.stop_lon.astype(float).values, s.stop_lat.astype(float).values)
    lines.append({"name": rid, "color": COL.get(rid, "#999"),
                  "pts": [[round(a, 1), round(b, 1)] for a, b in zip(x, y)]})

sh = pd.read_csv(os.path.join(HT, "shapes.txt"), dtype={"shape_id": str})
sh = sh[sh.shape_id.isin(set(pd.read_csv(os.path.join(HT, "trips.txt"), dtype=str).set_index("trip_id")
                             .loc[[t[1:] for t in ht.trip_id], "shape_id"]))]
sh = sh.sort_values(["shape_id", "shape_pt_sequence"])
segs = set()
for sid, g in sh.groupby("shape_id"):
    x, y = proj(g.shape_pt_lon.values, g.shape_pt_lat.values)
    inside = (g.shape_pt_lon.between(23.55, 24.0) & g.shape_pt_lat.between(37.82, 38.15)).values
    run = []
    for xi, yi, ok in list(zip(x, y, inside)) + [(0, 0, False)]:
        if ok: run.append((xi, yi)); continue
        if len(run) > 1:
            q = simplify(run, 12.0)
            segs.add(tuple((round(a / 10) * 10, round(b / 10) * 10) for a, b in q))
        run = []
for seg in segs:
    lines.append({"name": "Proastiakos", "color": "#7a8a99", "pts": [list(p) for p in seg]})
print("proastiakos drawing segments", len(segs))

marks = [("Syntagma", 37.9755, 23.7348), ("Omonia", 37.9841, 23.7280), ("Monastiraki", 37.9761, 23.7255),
         ("Piraeus", 37.9480, 23.6430), ("Kifisia", 38.0740, 23.8083), ("Marousi", 38.0560, 23.8080),
         ("Glyfada", 37.8650, 23.7530), ("Peristeri", 38.0130, 23.6910), ("Kallithea", 37.9560, 23.7020),
         ("Chalandri", 38.0210, 23.7990), ("Airport", 37.9370, 23.9450), ("Nea Smyrni", 37.9460, 23.7140),
         ("Exarchia", 37.9870, 23.7350), ("Kypseli", 37.9990, 23.7400), ("Ilioupoli", 37.9310, 23.7590),
         ("Faliro", 37.9420, 23.6830), ("Aigaleo", 37.9920, 23.6790), ("Agia Paraskevi", 38.0050, 23.8200)]
mk = []
for name, la, lo in marks:
    x, y = proj(lo, la); mk.append({"name": name, "x": round(float(x), 1), "y": round(float(y), 1)})

meta = {"lat0": LAT0, "lon0": LON0, "mPerDegLat": M_PER_DEG_LAT, "mPerDegLon": float(M_PER_DEG_LON),
        "tMin": T_MIN, "tMax": T_MAX, "day": "a Tuesday: OASA buses/trolleys and STASY metro/tram (summer 2026 timetable), Hellenic Train Proastiakos (1 Dec 2026)",
        "lines": lines, "marks": mk}
json.dump(meta, open(os.path.join(OUT, "meta.json"), "w"))
import base64
for fn in ("net", "pt"):
    src = os.path.join(OUT, fn + ".bin")
    json.dump(base64.b64encode(open(src, "rb").read()).decode(), open(os.path.join(OUT, fn + ".b64.json"), "w"))
    os.remove(src)
for fn in ("net.b64.json", "pt.b64.json", "meta.json"):
    print(fn, os.path.getsize(os.path.join(OUT, fn)) // 1024, "KB")
