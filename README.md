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

The map files are generated with the wow-vision map tooling. Edit them there rather than by hand.
