"""Bring the map files up to what Sku TBC navigates today: the Era route
waypoints with the UNION of the Era and WotLK link sets.

    py tools/generate.py --sku <Sku folder>            dry run, prints what would change
    py tools/generate.py --sku <Sku folder> --write    updates maps/*.lua in place

The run is incremental and idempotent. Every shipped record is kept as it is
(ids, names, coordinates, links). Route waypoints that exist in Sku's Era set but
not here are added with a deterministic uuid5 id, links present in either Sku link
set but missing here are added as two-way `true` entries, and a second run
changes nothing. Waypoints that end up without a link stay out, as in Sku.

Link ends on creature and object spawns are resolved to the shipped spawn records
through the Sku spawn tables (see skulib.build_resolver). Northrend and the death
knight start area are never added to.
"""
import sys, uuid, math, os, collections
import skulib
from skulib import fmt_line

ap = skulib.argparser(__doc__.split("\n\n")[0])
ap.add_argument("--write", action="store_true", help="update the map files (default: dry run)")
args = ap.parse_args()
P = skulib.paths(args)

CONTS = {"0", "1", "530", "369"}          # continents added to: Eastern Kingdoms, Kalimdor, Outland, Deeprun Tram
NS = uuid.UUID("6f1d2c1e-5b0a-4c55-9d6e-0a57b0c0e001")   # namespace for the ids of added waypoints

wv, order = skulib.load_wv(P.MAPS)

# 1. round trip guard: rebuilt lines must equal the shipped bytes, or the writer is not safe
for b, ids in order.items():
    src = [l for l in open(os.path.join(P.MAPS, b), encoding="utf-8") if l.lstrip().startswith("{id=")]
    assert len(src) == len(ids)
    for l, i in zip(src, ids):
        assert fmt_line(wv[i]) == l, (b, l[:160], fmt_line(wv[i])[:160])
print("round trip ok:", len(wv), "waypoints in", len(order), "files")

eraW, eraL = skulib.parse_sku(P.ERA)
lkW, lkL = skulib.parse_sku(P.LK)
resolve = skulib.build_resolver(wv, P.CRE, P.OBJ)


def norm(s):
    return s.strip().lower()


name2id = {}
for w in wv.values():
    if w["t"] == 1:
        name2id.setdefault(norm(w["n"]), w["id"])


def num(s):
    f = ("%.4f" % float(s)).rstrip("0").rstrip(".")
    return "0" if f in ("-0", "") else f


# 2. route waypoint identity: Era index -> uuid (existing record by name, else a candidate new waypoint)
area_votes = collections.defaultdict(collections.Counter)
for i, e in eraW.items():
    u = name2id.get(norm(e["name"]))
    if u and wv[u]["mapId"]:
        area_votes[e["area"]][wv[u]["mapId"]] += 1
cand = {}
era_idx2id = {}
era_name2idx = {}
for i, e in eraW.items():
    era_name2idx.setdefault(norm(e["name"]), i)
    u = name2id.get(norm(e["name"]))
    if u:
        era_idx2id[i] = u
        continue
    if e["cont"] not in CONTS or not norm(e["name"]):
        continue
    nid = str(uuid.uuid5(NS, "era:%d:%s" % (i, e["name"])))
    cand[nid] = dict(id=nid, xs=num(e["xs"]), ys=num(e["ys"]), x=e["x"], y=e["y"], mapId=None, cId=e["cont"],
                     n=e["name"], r=None, t=1, links={}, area=e["area"], new=True)
    era_idx2id[i] = nid
print("candidate new route waypoints:", len(cand))

# WotLK indices are resolved through the WotLK list BY NAME into the Era identity, and only
# when the two surveys agree on the position (an index can mean a different waypoint per file).
lk_idx2id = {}
mism = 0
for i, l in lkW.items():
    j = era_name2idx.get(norm(l["name"]))
    if j is None or j not in era_idx2id:
        continue
    e = eraW[j]
    if math.hypot(e["x"] - l["x"], e["y"] - l["y"]) > 1.0:
        mism += 1
        continue
    lk_idx2id[i] = era_idx2id[j]
print("WotLK route indices usable:", len(lk_idx2id), "skipped for position mismatch:", mism)

allw = dict(wv)
allw.update(cand)


def to_id(wpid, idxmap):
    t, dbi, sp, ar = skulib.decode(wpid)
    if t == 1:
        return idxmap.get(dbi)
    return resolve(t, dbi, sp, ar)[0]


# 3. union of links; an edge is added once, as a two-way `true` entry on the source side
have = set()
for w in wv.values():
    for k in w["links"]:
        have.add(frozenset((w["id"], k)))
added = collections.Counter()
long_edges = []
for label, L, idxmap in (("Era", eraL, era_idx2id), ("WotLK", lkL, lk_idx2id)):
    for s_, ns in L.items():
        a = to_id(s_, idxmap)
        if not a:
            continue
        for n in ns:
            b = to_id(n, idxmap)
            if not b or a == b:
                continue
            k = frozenset((a, b))
            if k in have:
                continue
            wa, wb = allw[a], allw[b]
            if wa["cId"] != wb["cId"]:
                added["skipped cross-continent"] += 1
                continue
            d = math.hypot(wa["x"] - wb["x"], wa["y"] - wb["y"])
            if d > 500:
                long_edges.append((round(d), wa["n"], wb["n"]))
                added["skipped over 500 yards"] += 1
                continue
            have.add(k)
            src, dst = (wa, wb) if wa["t"] == 1 or wb["t"] != 1 else (wb, wa)
            src["links"][dst["id"]] = "true"
            src["touched"] = True
            added[label + (" involving a new waypoint" if wa.get("new") or wb.get("new") else " between existing waypoints")] += 1
print("edges added:", dict(added))
print("sample long edges skipped:", long_edges[:5])

# 4. keep only new waypoints that ended up linked (Sku's cleanup drops linkless ones too)
linked = set()
for k in have:
    for i in k:
        linked.add(i)
new = {i: w for i, w in cand.items() if i in linked}
dz = collections.Counter()
for i, w in cand.items():
    if i not in linked:
        v = area_votes.get(w["area"])
        dz[v.most_common(1)[0][0] if v else "area" + str(w["area"])] += 1
print("dropped linkless by map:", dz.most_common(8))
print("new route waypoints kept (linked):", len(new), "dropped linkless:", len(cand) - len(new))

# 5. map ids for the new waypoints: area vote, else nearest shipped route waypoint on the continent
by_cont = collections.defaultdict(list)
for w in wv.values():
    if w["t"] == 1 and w["mapId"]:
        by_cont[w["cId"]].append(w)
fallback = 0
for w in new.values():
    v = area_votes.get(w["area"])
    if v:
        w["mapId"] = v.most_common(1)[0][0]
    else:
        fallback += 1
        near = min(by_cont[w["cId"]], key=lambda o: (o["x"] - w["x"]) ** 2 + (o["y"] - w["y"]) ** 2) if by_cont[w["cId"]] else None
        w["mapId"] = near["mapId"] if near else None
    f = (w["mapId"] or "0") + ".lua"
    assert f in order, f
    w["file"] = f
print("map id by area vote:", len(new) - fallback, "by nearest neighbour:", fallback)
per_map = collections.Counter(w["mapId"] for w in new.values())
print("new waypoints per map (top 12):", per_map.most_common(12))

# 6. write: touched records are rewritten in place, new records go before the closing `})`
if args.write:
    add_by_file = collections.defaultdict(list)
    for w in new.values():
        add_by_file[w["file"]].append(w)
    changed = 0
    for b, ids in order.items():
        touched = any(wv[i].get("touched") for i in ids) or b in add_by_file
        if not touched:
            continue
        path = os.path.join(P.MAPS, b)
        lines = open(path, encoding="utf-8", newline="").read().split("\n")
        out = []
        it = iter(ids)
        for l in lines:
            cr = "\r" if l.endswith("\r") else ""   # keep the working copy's line endings
            if l.lstrip().startswith("{id="):
                out.append(fmt_line(wv[next(it)]).rstrip("\n") + cr)
            elif l.strip() == "})":
                for w in add_by_file.get(b, []):
                    out.append(fmt_line(w).rstrip("\n") + cr)
                out.append(l)
            else:
                out.append(l)
        open(path, "w", encoding="utf-8", newline="").write("\n".join(out))
        changed += 1
    print("files written:", changed)
else:
    print("dry run: nothing written (add --write)")
