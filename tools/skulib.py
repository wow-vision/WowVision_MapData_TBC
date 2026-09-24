"""Shared parsers for the map data tooling: the shipped map files, Sku's route
data (waypoints and links) and its creature and object spawn tables.

Paths: the data addon is the parent of this tools/ directory unless --data is
given. The Sku addon folder (the one holding Sku.toc, an extracted Sku TBC
release) comes from --sku or the SKU_DIR environment variable. Both are shared
by every script here through argparser() and paths().
"""
import re, glob, os, sys, argparse, collections

DEFAULT_DATA = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


def argparser(description):
    ap = argparse.ArgumentParser(description=description)
    ap.add_argument("--sku", default=os.environ.get("SKU_DIR"), metavar="DIR",
                    help="Sku addon folder, the one holding Sku.toc (default: $SKU_DIR)")
    ap.add_argument("--data", default=DEFAULT_DATA, metavar="DIR",
                    help="WowVision_MapData_TBC folder (default: the parent of tools/)")
    return ap


def paths(args):
    """Resolve the input files from parsed arguments; exits with a message when one is missing."""
    if not args.sku:
        sys.exit("Sku addon folder not given: use --sku <dir> or set SKU_DIR (the folder holding Sku.toc)")
    p = argparse.Namespace(DATA=args.data, MAPS=os.path.join(args.data, "maps"), SKU=args.sku)
    p.ERA = os.path.join(args.sku, "SkuDB", "assets", "routedata_global.lua")   # Era survey: waypoints + links
    p.LK = os.path.join(args.sku, "routedata_global_wotlk.lua")                 # WotLK survey: waypoints + links
    p.CRE = os.path.join(args.sku, "SkuDB", "assets", "creatures.lua")          # creature spawns
    p.OBJ = os.path.join(args.sku, "SkuDB", "assets", "objects.lua")            # object spawns
    for f in (p.ERA, p.LK, p.CRE, p.OBJ):
        if not os.path.isfile(f):
            sys.exit("missing " + f)
    if not glob.glob(os.path.join(p.MAPS, "*.lua")):
        sys.exit("no map files in " + p.MAPS)
    return p


# ---------------------------------------------------------------- shipped map files

WP_RE = re.compile(r'^(\s*)\{id="([^"]+)",x=([-\d.e]+),y=([-\d.e]+),(?:mapId=(\d+),)?(?:cId=(-?\d+),)?n="((?:[^"\\]|\\.)*)",(?:r="((?:[^"\\]|\\.)*)",)?(?:t=(\d+),)?(?:links=\{(.*?)\},)?\},\s*$')
LINK_RE = re.compile(r'\["([^"]+)"\]=(true|1)')


def load_wv(mapsdir):
    """id -> record for every waypoint in maps/*.lua, plus file -> [ids] in file order.
    Coordinates are kept both as the source text (xs, ys) and as floats."""
    wv = {}
    order = collections.defaultdict(list)
    for f in sorted(glob.glob(os.path.join(mapsdir, "*.lua"))):
        b = os.path.basename(f)
        for line in open(f, encoding="utf-8"):
            if not line.lstrip().startswith("{id="):
                continue
            m = WP_RE.match(line)
            assert m, line[:200]
            _, wid, x, y, mid, cid, n, r, t, links = m.groups()
            w = dict(id=wid, xs=x, ys=y, x=float(x), y=float(y), mapId=mid, cId=cid, n=n, r=r, t=int(t),
                     links=dict(LINK_RE.findall(links or "")), file=b)
            wv[wid] = w
            order[b].append(wid)
    return wv, order


def fmt_line(w):
    """One map file record, byte-identical to the shipped format."""
    s = '\t{id="%s",x=%s,y=%s,' % (w["id"], w["xs"], w["ys"])
    if w["mapId"] is not None:
        s += "mapId=%s," % w["mapId"]
    if w["cId"] is not None:
        s += "cId=%s," % w["cId"]
    s += 'n="%s",' % w["n"]
    if w["r"] is not None:
        s += 'r="%s",' % w["r"]
    s += "t=%d," % w["t"]
    if w["links"]:
        s += "links={" + "".join('["%s"]=%s,' % (k, v) for k, v in w["links"].items()) + "},"
    return s + "},\n"


# ---------------------------------------------------------------- Sku route data

def parse_sku(path, want_wps=True):
    """Sku routedata file -> (index -> waypoint, index -> [linked indices]).
    Waypoint indices count every entry of WaypointsNew, including the `false` holes,
    because the Links table refers to them by that position."""
    wps = {}
    links = {}
    section = None
    cur = None
    depth = 0
    idx = 0
    src = None
    for line in open(path, encoding="utf-8-sig", errors="replace"):
        m = re.match(r'^\s*\["(WaypointsNew|Waypoints|Links|WaypointLevels|SequenceNumbers)"\]\s*=\s*\{', line)
        if m:
            section = m.group(1)
            depth = 0
            continue
        s = re.sub(r"\s*--\s*\[\d+\]\s*$", "", line.strip())
        if section == "WaypointsNew" and want_wps:
            if s == "{":
                depth += 1
                if depth == 1:
                    idx += 1
                    cur = {}
            elif s.endswith("= {"):
                depth += 1
            elif s in ("},", "}"):
                if depth == 1 and cur and "names" in cur:
                    wps[idx] = dict(x=float(cur["worldX"]), y=float(cur["worldY"]), xs=cur["worldX"], ys=cur["worldY"],
                                    name=cur["names"].split("§")[0], cont=cur.get("contintentId"), area=cur.get("areaId"))
                depth -= 1
            elif depth == 0 and s.startswith("false"):
                idx += 1
            elif depth == 1:
                mm = re.match(r'\["(\w+)"\]\s*=\s*"?((?:[^"\\]|\\.)*?)"?,?$', s)
                if mm:
                    cur[mm.group(1)] = mm.group(2)
        elif section == "Links":
            mm = re.match(r'^\[(\d+)\]\s*=\s*\{', s)
            if mm:
                src = int(mm.group(1))
                continue
            mm = re.match(r'^\[(\d+)\]\s*=\s*\d+,?$', s)
            if mm and src is not None:
                links.setdefault(src, []).append(int(mm.group(1)))
    return wps, links


def decode(wpid):
    """Sku link id -> (kind, index, spawn, area). kind 1 = route waypoint index,
    2 = creature id, 3 = object id; spawn and area pick the spawn point for kinds 2 and 3."""
    spawn = wpid >> 38
    area = (wpid - (spawn << 38)) >> 20
    i = wpid - (area << 20) - (spawn << 38)
    if i < 200000:
        return 1, i, spawn, area
    if i < 500000:
        return 2, i - 200000, spawn, area
    return 3, i - 500000, spawn, area


# ---------------------------------------------------------------- Sku spawn tables

def parse_db(path, spawn_field):
    """creatures.lua / objects.lua -> id -> (name, {area: [(x, y), ...]})"""
    out = {}
    row = re.compile(r'^\s*\[(\d+)\] = \{(?:\'((?:[^\'\\]|\\.)*)\'|"((?:[^"\\]|\\.)*)"),(.*)$')
    for line in open(path, encoding="utf-8-sig", errors="replace"):
        m = row.match(line)
        if not m:
            continue
        cid = int(m.group(1))
        name = m.group(2) if m.group(2) is not None else m.group(3)
        rest = m.group(4)
        # walk the top-level fields of the row
        fields = []
        depth = 0
        cur = ""
        q = None
        for ch in rest:
            if q:
                cur += ch
                if ch == q:
                    q = None
                continue
            if ch in "'\"":
                q = ch
                cur += ch
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                if depth == 0:
                    break
                depth -= 1
            if ch == "," and depth == 0:
                fields.append(cur)
                cur = ""
            else:
                cur += ch
        fi = spawn_field - 2
        sp = {}
        if 0 <= fi < len(fields) and fields[fi].startswith("{"):
            for zm in re.finditer(r'\[(\d+)\]=\{((?:\{[^{}]*\},?)*)\}', fields[fi]):
                pts = re.findall(r'\{(-?[\d.]+),(-?[\d.]+)', zm.group(2))
                sp[int(zm.group(1))] = [(float(a), float(b)) for a, b in pts]
        if sp or cid not in out:
            out[cid] = (name.replace("\\'", "'"), sp)
    return out


def build_resolver(wv, cre_path, obj_path):
    """Returns resolve(kind, dbId, spawn, area) -> (waypoint id or None, reason).
    Maps a Sku creature or object link end to the shipped spawn record with the same
    name (creatures) or object id, spawn number and map position."""
    cre = parse_db(cre_path, 7)
    obj = parse_db(obj_path, 4)
    idx = {}
    for w in wv.values():
        p = w["n"].split(";")
        try:
            if w["t"] == 2:
                idx.setdefault((2, p[0].lower(), int(p[-3]), round(float(p[-2]), 2), round(float(p[-1]), 2)), []).append(w["id"])
            elif w["t"] == 3 and p[0] == "OBJECT":
                idx.setdefault((3, int(p[1]), int(p[-3]), round(float(p[-2]), 2), round(float(p[-1]), 2)), []).append(w["id"])
        except Exception:
            pass

    def resolve(t, dbi, spawn, area):
        db = cre if t == 2 else obj
        r = db.get(dbi)
        if not r:
            return None, "no db row"
        pts = r[1].get(area)
        if not pts or spawn < 1 or spawn > len(pts):
            return None, "no spawn"
        px, py = round(pts[spawn - 1][0], 2), round(pts[spawn - 1][1], 2)
        k = (2, r[0].lower(), spawn, px, py) if t == 2 else (3, dbi, spawn, px, py)
        v = idx.get(k)
        if not v:
            return None, "not in WV"
        if len(v) > 1:
            return None, "ambiguous"
        return v[0], "ok"

    return resolve
