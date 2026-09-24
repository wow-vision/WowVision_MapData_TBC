-- Route between waypoints offline with WowVision's real Router, to check the
-- data without logging in. Loads the map files the way the addon does.
--
-- Usage, from the repo root:
--   lua tools/route-by-name.lua <continentId> "<from name fragment>" "<to name fragment>" ...
-- Example (Eastern Kingdoms, from Light's Hope Chapel):
--   lua tools/route-by-name.lua 0 "central location;Light's Hope" "stratholme dungeon" "naxx teleport"
--
-- WowVision's checkout is taken from the WOWVISION_DIR environment variable, or
-- from a WowVision folder next to this repo.

local root = arg[0]:match("^(.*)[/\\]tools[/\\][^/\\]+$") or "."
local wvdir = os.getenv("WOWVISION_DIR") or (root .. "/../WowVision")
local cont = tonumber(arg[1])
if not cont or not arg[3] then
    print("usage: lua tools/route-by-name.lua <continentId> \"<from>\" \"<to>\" ...")
    os.exit(2)
end

WowVision = {}
tinsert = table.insert
local ok, err = pcall(dofile, wvdir .. "/core/navigation/maps/Router.lua")
if not ok then
    print("cannot load WowVision's Router from " .. wvdir .. " (set WOWVISION_DIR): " .. tostring(err))
    os.exit(2)
end
local Router = WowVision.Router

-- load the map files in modules.xml order, keeping this continent
local all = {}
local ds = {}
function ds:addWaypoints(list)
    for _, wp in ipairs(list) do
        if wp.cId == cont then all[wp.id] = wp end
    end
end
for line in io.lines(root .. "/modules.xml") do
    local f = line:match('file="([^"]+)"')
    if f then assert(loadfile(root .. "/" .. f:gsub("\\", "/")))("WowVision_MapData_TBC", { dataset = ds }) end
end

-- materialize reverse edges (same rule as the dataset loader: true = two-way, stored once)
local count = 0
for id, wp in pairs(all) do
    count = count + 1
    if wp.links then
        for tid, kind in pairs(wp.links) do
            local t = all[tid]
            if kind == true and t then
                t.links = t.links or {}
                if t.links[id] == nil then t.links[id] = 1 end
            end
        end
    end
end
print(string.format("continent %d: %d waypoints loaded", cont, count))

-- first waypoint (alphabetically) whose name contains the fragment
local function find(frag)
    frag = frag:lower()
    local best
    for _, wp in pairs(all) do
        if wp.n:lower():find(frag, 1, true) and (best == nil or wp.n < best.n) then best = wp end
    end
    return best
end

local from = find(arg[2])
if not from then
    print("no waypoint matches " .. arg[2])
    os.exit(1)
end
print("FROM " .. from.n .. (from.links and "" or "  (has no links)"))
local failed = 0
for i = 3, #arg do
    local to = find(arg[i])
    if not to then
        print("TO " .. arg[i] .. ": no waypoint with that name")
        failed = failed + 1
    else
        local res, why = Router.route(all, from.x, from.y, to.id, { entryId = from.id })
        local straight = math.sqrt((from.x - to.x) ^ 2 + (from.y - to.y) ^ 2)
        if res then
            print(string.format("TO %s: ok, %d hops, %.0f yards, straight %.0f", to.n, #res.waypoints, res.distance, straight))
        else
            print(string.format("TO %s: FAILED (%s)%s, straight %.0f", to.n, tostring(why),
                to.links and "" or " - destination has no links", straight))
            failed = failed + 1
        end
    end
end
os.exit(failed > 0 and 1 or 0)
