-- Guard against a regeneration silently dropping waypoints that were added
-- outside the generator (see README, provenance note). Every id listed in
-- tools/protected-ids.txt must still exist in maps/*.lua.
--
-- Usage, from the repo root: lua tools/check-protected.lua
-- Exits non-zero, listing the missing ids, when any are gone.

local root = arg[0]:match("^(.*)[/\\]tools[/\\][^/\\]+$") or "."

local function readLines(path)
    local file = assert(io.open(path, "r"), "cannot open " .. path)
    local lines = {}
    for line in file:lines() do
        line = line:gsub("%s+$", "")
        if line ~= "" then
            tinsert(lines, line)
        end
    end
    file:close()
    return lines
end

tinsert = table.insert

local protected = readLines(root .. "/tools/protected-ids.txt")

-- The map files in load order, from modules.xml.
local xml = assert(io.open(root .. "/modules.xml", "r")):read("*a")
local present = {}
local files = 0
for file in xml:gmatch('file="([^"]+)"') do
    local path = root .. "/" .. file:gsub("\\", "/")
    local text = assert(io.open(path, "r"), "cannot open " .. path):read("*a")
    for id in text:gmatch('id="([0-9a-f%-]+)"') do
        present[id] = true
    end
    files = files + 1
end

local missing = {}
for _, id in ipairs(protected) do
    if not present[id] then
        tinsert(missing, id)
    end
end

print(string.format("%d map files, %d protected ids, %d missing", files, #protected, #missing))
if #missing > 0 then
    for i = 1, math.min(#missing, 20) do
        print("  missing " .. missing[i])
    end
    if #missing > 20 then
        print("  and " .. (#missing - 20) .. " more")
    end
    print("Protected waypoints are gone: a regeneration dropped data added outside the generator. See README.")
    os.exit(1)
end
