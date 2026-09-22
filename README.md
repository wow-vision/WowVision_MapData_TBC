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
- `locale/` holds one generated file per client language (German, French). Each maps English name parts (creature, role, zone, landmark words) to the localized text, plus whole-name overrides where the parts are not enough. A file returns on its first line when the client language does not match.
- `names.lua` applies the matching locale file to the waypoint names as the map files load. Names are keyed by their English text, not by waypoint id, so a regenerated export keeps working.

The map files are generated with the wow-vision map tooling. Edit them there rather than by hand.

Provenance note: the old-world route waypoints restored in version 1.1.0 (about 2,100 waypoints and 2,500 links, Eastern and Western Plaguelands and Swamp of Sorrows most of all) were produced outside that tooling, by taking the Era waypoint set with the union of the Era and WotLK link sets. Until the generator reproduces that union, a regeneration from it would drop them again.

Two guards stop that happening by accident. The ids of those waypoints are listed in `tools/protected-ids.txt`, and `tools/check-protected.lua` fails when any is missing; it runs on every push and pull request and before every release, so a regeneration that lost them cannot be published. The wvmaps exporter also refuses to overwrite an addon folder when its output would drop waypoint ids that the folder already holds, unless told to with `--allow-drop`.
