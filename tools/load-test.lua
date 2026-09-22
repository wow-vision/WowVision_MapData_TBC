-- Loads the whole addon offline in TOC order under a given client locale and
-- reports load time, memory and a few sample names, so the cost and the effect
-- of the locale files can be measured without logging in.
--
-- Usage, from the repo root:
--   lua tools/load-test.lua [deDE|frFR|enUS]        (default enUS)

local locale = arg[1] or "enUS"
local root = arg[0]:match("^(.*)[/\\]tools[/\\][^/\\]+$") or "."

-- the two globals the addon touches
function GetLocale() return locale end
local all, count = {}, 0
WowVision = { atlas = { createDataset = function()
	return { addWaypoints = function(_, list)
		for _, wp in ipairs(list) do
			all[wp.id] = wp
			count = count + 1
		end
	end }
end } }

-- files in TOC order, xml includes expanded
local files = {}
for line in io.lines(root .. "/WowVision_MapData_TBC.toc") do
	line = line:gsub("%s+$", "")
	if line ~= "" and line:sub(1, 1) ~= "#" then
		if line:match("%.xml$") then
			for l in io.lines(root .. "/" .. line) do
				local f = l:match('file="([^"]+)"')
				if f then files[#files + 1] = f end
			end
		else
			files[#files + 1] = line
		end
	end
end

local addon, localeTime = {}, 0
collectgarbage()
local mem0 = collectgarbage("count")
local t0 = os.clock()
for _, f in ipairs(files) do
	local t = os.clock()
	assert(loadfile(root .. "/" .. f:gsub("\\", "/")))("WowVision_MapData_TBC", addon)
	if f:match("^locale") or f == "names.lua" then localeTime = localeTime + os.clock() - t end
end
local total = os.clock() - t0
collectgarbage()
local mem = collectgarbage("count") - mem0
print(string.format("%s: %d waypoints, load %.2f s (locale files %.3f s), memory %.1f MB", locale, count, total, localeTime, mem / 1024))

-- sample names: a creature, an object and a landmark
local samples = {
	"4dc63ec1-eaee-44b1-9699-d57f752a6147", -- Canaga Earthcaller, Durotar
	"a7f3483e-3555-4a56-aaeb-c080a52497a4", -- Gnomish Toolbox, Durotar
	"898a81c8-f1e2-429c-a2be-595f4a01ebc0", -- Deeprun Tram
}
for _, id in ipairs(samples) do
	print("  " .. (all[id] and all[id].n or (id .. " missing")))
end
for _, needle in ipairs({ "zentralpunkt;dun modr", "todesminen", "deadmines", "mortemines" }) do
	local hits, first = 0, nil
	for _, wp in pairs(all) do
		if wp.n and wp.n:lower():find(needle, 1, true) then
			hits = hits + 1
			first = first or wp.n
		end
	end
	print(string.format("  search '%s': %d hits%s", needle, hits, first and (", e.g. " .. first) or ""))
end
