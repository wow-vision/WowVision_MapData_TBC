# WowVision Map Data: TBC

Map waypoint data for [WowVision](https://github.com/wow-vision/WowVision) on The Burning Crusade anniversary realms. WowVision uses it for beacon navigation and pathfinding.

## Installing

1. Install WowVision first. This addon depends on it and does nothing on its own.
2. Download the latest zip from the releases page and extract it into your anniversary client's addons folder, so the files sit at `World of Warcraft\_anniversary_\Interface\AddOns\WowVision_MapData_TBC`.
3. Log in. WowVision picks the dataset up automatically.

## Layout

- `WowVision_MapData_TBC.toc` declares the addon and its dependency on WowVision.
- `main.lua` registers the dataset with WowVision's atlas.
- `modules.xml` lists the map files.
- `maps/` holds one file per map id with that map's waypoints.
- `tools/` holds the generator, an offline routing check and the protected-id guard (see below).

The map files are generated. Edit them through the generator rather than by hand.

## Regenerating from Sku

The waypoints and links come from the Sku addon's survey data. `tools/generate.py` (Python 3, no packages needed) brings `maps/` up to what Sku TBC navigates: the Era route waypoints with the union of the Era and WotLK link sets, with link ends on creature and object spawns resolved to the shipped spawn records. Point it at an extracted Sku TBC release, the folder holding `Sku.toc`:

```
python3 tools/generate.py --sku /path/to/Sku            # dry run, prints what would change
python3 tools/generate.py --sku /path/to/Sku --write    # updates maps/*.lua in place
```

The run is incremental and idempotent: every shipped record keeps its id, name, coordinates and links, only missing waypoints (with deterministic uuid5 ids) and missing links are added, and a second run changes nothing. It starts with a round-trip check that its writer reproduces the shipped bytes exactly, and refuses to continue when that fails. Northrend and the death knight start area are never added to; waypoints that end up without a link stay out, as in Sku.

`tools/route-by-name.lua` routes between waypoints offline with WowVision's real `Router`, for checking the data without logging in:

```
WOWVISION_DIR=/path/to/WowVision lua tools/route-by-name.lua 0 "central location;Light's Hope" "stratholme dungeon" "naxx teleport"
```

It exits non-zero when a route fails, so it can serve as a smoke test after a regeneration.

`tools/load-test.lua [deDE|frFR|enUS]` loads the whole addon offline in TOC order under a client locale and prints load time, memory and sample names.

`tools/names.py --sku /path/to/Sku --write` generates the localized name files in `locale/` (German and French) from the same Sku data; see the description of `locale/` above. Like the map generator it is deterministic, so a rerun after a map regeneration only changes what the new names need.

Provenance note: the old-world route waypoints restored in version 1.1.0 (about 2,100 waypoints and 2,500 links, Eastern and Western Plaguelands and Swamp of Sorrows most of all) were produced outside that tooling, by taking the Era waypoint set with the union of the Era and WotLK link sets. `tools/generate.py` reproduces that union: run on the 1.0.0 files it gives the 1.1.0 files byte for byte. A regeneration through other tooling that does not would drop them again.

Two guards stop that happening by accident. The ids of those waypoints are listed in `tools/protected-ids.txt`, and `tools/check-protected.lua` fails when any is missing; it runs on every push and pull request and before every release, so a regeneration that lost them cannot be published. The wvmaps exporter also refuses to overwrite an addon folder when its output would drop waypoint ids that the folder already holds, unless told to with `--allow-drop`.
