"""Localized waypoint names: generates locale/<locale>.lua from the Sku data.

    py tools/names.py --sku <Sku folder>            dry run, prints the measurements
    py tools/names.py --sku <Sku folder> --write    writes locale/deDE.lua and locale/frFR.lua

Builds, per locale, a dictionary of NAME PARTS (the ';'-separated segments of a
waypoint name: creature, role, zone, landmark words) plus a small table of
whole-name overrides for names the parts cannot reproduce. Keyed by English
text, never by waypoint id, so the output is valid for any export of the data.

Sources, all inside the Sku addon folder: the route waypoint names carry
English, German and French side by side; creature and object names come from
the per-locale name tables; roles from SkuNav's npc-flag table; zone names from
the map table. Game tables outrank hand-typed route names when they disagree.
"""
import re, sys, os, collections
import skulib

ap = skulib.argparser(__doc__.split("\n\n")[0])
ap.add_argument("--write", action="store_true", help="write the locale files (default: dry run)")
args = ap.parse_args()
P = skulib.paths(args)
OUT = os.path.join(P.DATA, "locale")

LOCALES = {"deDE": 1, "frFR": 2}  # index into the "en§de§fr" route names
STR = r'"((?:[^"\\]|\\.)*)"'


def unesc(s):
    return re.sub(r"\\(.)", r"\1", s)


def lua(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def route_names():
    """en -> [en, de, fr]; Era first, it is the origin of the export."""
    out = {}
    for path in (P.ERA, P.LK):
        for line in open(path, encoding="utf-8-sig", errors="replace"):
            m = re.match(r'\s*\["names"\] = ' + STR, line)
            if not m:
                continue
            p = unesc(m.group(1)).split("§")
            out.setdefault(p[0], p)
    return out


def chunked(path, entry):
    """label -> {id: match groups}; later entries override earlier ones."""
    out = collections.defaultdict(dict)
    label = None
    head = re.compile(r'SkuDBChunks\[#SkuDBChunks\+1\] = \{"([^"]+)"')
    for line in open(path, encoding="utf-8-sig", errors="replace"):
        h = head.search(line)
        if h:
            label = h.group(1)
        if label is None:
            continue
        for m in entry.finditer(line):
            out[label][int(m.group(1))] = m.groups()[1:]
    return out


NPC = re.compile(r'\[(\d+)\] = \{(?:' + STR + r'|nil),\s*(?:' + STR + r'|nil),?\}')
OBJE = re.compile(r'\[(\d+)\] = ' + STR + r',')


def roles(loc):
    """Sku's npc-flag role words, en -> loc."""
    tabs = collections.defaultdict(dict)
    cur = None
    for line in open(os.path.join(P.SKU, "SkuNav", "data.lua"), encoding="utf-8-sig", errors="replace"):
        m = re.match(r'\s*\["(\w{4})"\] = \{', line)
        if m:
            cur = m.group(1)
            continue
        m = re.match(r'\s*\[(UNIT_NPC_FLAG_\w+)\]\s*=\s*' + STR, line)
        if m and cur:
            tabs[cur][m.group(1)] = unesc(m.group(2))
    return {en: tabs[loc][k] for k, en in tabs["enUS"].items() if k in tabs[loc]}


def zones(loc):
    out = {}
    for line in open(os.path.join(P.SKU, "SkuDB", "assets", "maps.lua"), encoding="utf-8-sig", errors="replace"):
        en = re.search(r'\["enUS"\] = ' + STR, line)
        lo = re.search(r'\["%s"\] = ' % loc + STR, line)
        if en and lo:
            out.setdefault(unesc(en.group(1)), unesc(lo.group(1)))
    return out


def numeric(s):
    return re.fullmatch(r"-?[\d.]*", s) is not None


class Votes:
    def __init__(self):
        self.v = collections.defaultdict(collections.Counter)

    def add(self, en, lo, w=1):
        if en and lo and not numeric(en):
            self.v[en][lo] += w

    def resolve(self):
        seg = {}
        conflicts = 0
        for en, c in self.v.items():
            if len(c) > 1:
                conflicts += 1
            best = c.most_common(1)[0][0]
            if best != en:
                seg[en] = best
        return seg, conflicts


def translate(n, seg, full):
    if n in full:
        return full[n]
    return ";".join(seg.get(s, s) for s in n.split(";"))


def build(loc, wv, routes):
    idx = LOCALES[loc]
    cre = chunked(P.CRE, NPC)
    obj = chunked(P.OBJ, OBJE)
    if loc == "frFR":
        for f, table, entry in ((os.path.join("SkuDB", "assets", "frFR", "creatures_frFR.lua"), cre, NPC),
                                (os.path.join("SkuDB", "assets", "frFR", "objects_frFR.lua"), obj, OBJE)):
            for k, v in chunked(os.path.join(P.SKU, f), entry).items():
                table[k] = v
    cen = cre["SkuDB.NpcData.Names.enUS"]
    clo = cre["SkuDB.NpcData.Names." + loc]
    oen = obj["SkuDB.objectLookup.enUS"]
    olo = obj["SkuDB.objectLookup." + loc]

    votes = Votes()
    # weights: game databases outrank hand-typed route names on a conflict
    for i, (name, sub) in cen.items():
        l = clo.get(i)
        if not l:
            continue
        if name and l[0]:
            votes.add(unesc(name), unesc(l[0]), 1000)
        if sub and l[1]:
            votes.add(unesc(sub), unesc(l[1]), 1000)
    for i, (name,) in oen.items():
        l = olo.get(i)
        if l and l[0]:
            votes.add(unesc(name), unesc(l[0]), 1000)
    for en, lo in roles(loc).items():
        votes.add(en, lo, 100000)
    for en, lo in zones(loc).items():
        votes.add(en, lo, 100000)
    for en, p in routes.items():
        if len(p) <= idx:
            continue
        a, b = en.split(";"), p[idx].split(";")
        if len(a) == len(b):
            for x, y in zip(a, b):
                votes.add(x, y)
    seg, conflicts = votes.resolve()

    # keep only parts the shipped data actually uses
    used = set()
    for w in wv.values():
        used.update(unesc(w["n"]).split(";"))
    seg = {k: v for k, v in seg.items() if k in used}

    # whole-name overrides: route names with a known translation the parts miss;
    # objects whose id says something else than their (ambiguous) English name
    full = {}
    stats = collections.Counter()
    for w in wv.values():
        n = unesc(w["n"])
        want = None
        if w["t"] == 1:
            p = routes.get(n)
            if p and len(p) > idx:
                want = p[idx]
        elif w["t"] == 3 and n.startswith("OBJECT;"):
            s = n.split(";")
            l = olo.get(int(s[1])) if s[1].isdigit() else None
            if l and l[0]:
                s2 = [seg.get(x, x) for x in s]
                s2[2] = unesc(l[0])
                want = ";".join(s2)
        got = translate(n, seg, {})
        if want is not None and got != want:
            full[n] = want
            got = want
            stats["override t%d" % w["t"]] += 1
        stats["t%d" % w["t"]] += 1
        if got != n:
            stats["changed t%d" % w["t"]] += 1
        elif not re.match(r"^(auto;|quick waypoint)", n):
            stats["unchanged t%d" % w["t"]] += 1
    return seg, full, conflicts, stats


def write(loc, seg, full):
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, loc + ".lua")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("-- GENERATED by tools/names.py - do not hand-edit.\n")
        f.write('if GetLocale() ~= "%s" then\n\treturn\nend\n' % loc)
        f.write("local _, addon = ...\naddon.names = {\n\tparts = {\n")
        for k in sorted(seg):
            f.write("\t\t[%s]=%s,\n" % (lua(k), lua(seg[k])))
        f.write("\t},\n\tfull = {\n")
        for k in sorted(full):
            f.write("\t\t[%s]=%s,\n" % (lua(k), lua(full[k])))
        f.write("\t},\n}\n")
    return path


if __name__ == "__main__":
    wv, _ = skulib.load_wv(P.MAPS)
    routes = route_names()
    print("waypoints", len(wv), "| Sku route names", len(routes))
    for loc in LOCALES:
        seg, full, conflicts, stats = build(loc, wv, routes)
        print("==", loc, "parts", len(seg), "overrides", len(full), "conflicting parts", conflicts)
        for k in sorted(stats):
            print("   ", k, stats[k])
        if args.write:
            p = write(loc, seg, full)
            print("    wrote", p, os.path.getsize(p) // 1024, "KB")
    if not args.write:
        print("dry run: nothing written (add --write)")
