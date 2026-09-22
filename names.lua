local _, addon = ...

-- Localized waypoint names. The map files carry English names; on a client
-- with a matching locale file, locale/<locale>.lua has set addon.names:
--   parts = English name part -> localized part (creature, role, zone, ...)
--   full  = English name -> localized name, where the parts cannot express it
-- Names are translated as the map files hand their waypoints over, so the
-- dataset only ever sees one name per waypoint. Keyed by text, not by id:
-- a regenerated export needs no new locale files unless names changed.
local names = addon.names
if names == nil then
	return
end
addon.names = nil

local dataset, parts, full = addon.dataset, names.parts, names.full
addon.dataset = {
	addWaypoints = function(_, waypoints)
		for i = 1, #waypoints do
			local wp = waypoints[i]
			if wp.n ~= nil then
				wp.n = full[wp.n] or (wp.n:gsub("[^;]+", parts))
			end
		end
		dataset:addWaypoints(waypoints)
	end,
}
