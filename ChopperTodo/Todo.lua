-- Chopper To-Do : calendar + task list logic for Rainmeter
-- Tasks live in @Resources\tasks.txt, one per line:  done|date|text
--   done = 0 or 1, date = YYYY-MM-DD (or empty), text = the task

local ROWS = 9                      -- number of task rows drawn in the skin
local TRANSPARENT = '0,0,0,0'

local tasks, vis, cells, counts = {}, {}, {}, {}
local viewY, viewM = 2000, 1
local selected = nil                -- 'YYYY-MM-DD' of the clicked day, or nil
local offset = 0                    -- scroll position of the list
local weekStart = 0                 -- 0 = Sunday first, 1 = Monday first
local file, todayKey = '', ''

local function var(name, default)
  local v = SKIN:GetVariable(name, default)
  if v == nil or v == '' then return default end
  return v
end

local function key(y, m, d) return string.format('%04d-%02d-%02d', y, m, d) end

local function fmtDate(k)
  local y, m, d = tostring(k):match('^(%d+)%-(%d+)%-(%d+)$')
  if not y then return tostring(k) end
  local ts = os.time{year = tonumber(y), month = tonumber(m), day = tonumber(d), hour = 12}
  return os.date('%b ', ts) .. tonumber(d)
end

------------------------------------------------------------------ storage

local function load()
  tasks = {}
  local f = io.open(file, 'r')
  if not f then return end
  for line in f:lines() do
    line = line:gsub('^\239\187\191', ''):gsub('\r$', '')
    local d, dt, txt = line:match('^([01])|([^|]*)|(.*)$')
    if d and txt ~= '' then
      tasks[#tasks + 1] = {done = (d == '1'), date = dt, text = txt}
    end
  end
  f:close()
end

local function save()
  local f = io.open(file, 'w')
  if not f then return end
  for _, t in ipairs(tasks) do
    f:write((t.done and '1' or '0') .. '|' .. t.date .. '|' .. t.text .. '\n')
  end
  f:close()
end

------------------------------------------------------------------ state

function Initialize()
  file = SKIN:ReplaceVariables('#CURRENTPATH#tasks.txt')
  weekStart = tonumber(var('WeekStart', '0')) or 0
  local t = os.date('*t')
  viewY, viewM = t.year, t.month
  selected, offset = nil, 0
end

function Refresh()
  load()
  todayKey = os.date('%Y-%m-%d')

  counts = {}
  for _, t in ipairs(tasks) do
    if t.date ~= '' then
      local c = counts[t.date] or {open = 0, done = 0}
      if t.done then c.done = c.done + 1 else c.open = c.open + 1 end
      counts[t.date] = c
    end
  end

  local first = os.date('*t', os.time{year = viewY, month = viewM, day = 1, hour = 12}).wday - 1
  local lead = (first - weekStart) % 7
  for n = 1, 42 do
    local d = os.date('*t', os.time{year = viewY, month = viewM, day = n - lead, hour = 12})
    cells[n] = {day = d.day, key = key(d.year, d.month, d.day),
                inMonth = (d.month == viewM), y = d.year, m = d.month}
  end

  vis = {}
  for i, t in ipairs(tasks) do
    if (not selected) or t.date == selected then vis[#vis + 1] = {i = i, t = t} end
  end
  table.sort(vis, function(a, b)
    if a.t.done ~= b.t.done then return not a.t.done end
    if a.t.date ~= b.t.date then
      if a.t.date == '' then return false end
      if b.t.date == '' then return true end
      return a.t.date < b.t.date
    end
    return a.i < b.i
  end)

  local maxOff = math.max(0, #vis - ROWS)
  if offset > maxOff then offset = maxOff end
  if offset < 0 then offset = 0 end
end

function Update()
  Refresh()
  return 0
end

local function row(n) return vis[n + offset] end
local function redraw() SKIN:Bang('!Update') end

------------------------------------------------------------------ labels

function TodayLabel() return os.date('%A, %b ') .. tonumber(os.date('%d')) end

function MonthTitle()
  return os.date('%B %Y', os.time{year = viewY, month = viewM, day = 1, hour = 12})
end

function WeekdayLabel(i)
  local names = {'S', 'M', 'T', 'W', 'T', 'F', 'S'}
  return names[((i - 1 + weekStart) % 7) + 1]
end

function ListTitle()
  if selected then return 'Tasks for ' .. fmtDate(selected) end
  return 'All tasks'
end

function ShowAll()
  if selected then return 'show all tasks' end
  return ''
end

function Summary()
  if #vis == 0 then return '' end
  local done = 0
  for _, r in ipairs(vis) do if r.t.done then done = done + 1 end end
  local s = done .. ' of ' .. #vis .. ' done'
  if #vis > ROWS then s = s .. '   |   scroll for more' end
  return s
end

------------------------------------------------------------------ calendar cells

function DayText(n) local c = cells[n]; return c and tostring(c.day) or '' end

function DayColor(n)
  local c = cells[n]
  if not c then return TRANSPARENT end
  if c.key == todayKey then return '255,255,255,255' end
  if not c.inMonth then return var('ColorMuted', '176,142,145') end
  return var('ColorText', '112,66,70')
end

function DayFill(n)
  local c = cells[n]
  if c and c.key == todayKey then return var('ColorAccent', '232,110,122') end
  return TRANSPARENT
end

function DayRing(n)
  local c = cells[n]
  if c and c.key == selected then return var('ColorAccent2', '104,160,178') end
  return TRANSPARENT
end

function DayDot(n)
  local c = cells[n]
  local k = c and counts[c.key]
  if not k then return TRANSPARENT end
  if k.open > 0 then
    if c.key == todayKey then return var('ColorAccent2', '104,160,178') end
    return var('ColorAccent', '232,110,122')
  end
  return var('ColorAccent2', '104,160,178')
end

------------------------------------------------------------------ task rows

function RowText(n)
  local r = row(n)
  if not r then
    if n == 1 and #vis == 0 then return 'Nothing here yet - add one!' end
    return ''
  end
  return r.t.text
end

function RowColor(n)
  local r = row(n)
  if not r or r.t.done then return var('ColorMuted', '176,142,145') end
  return var('ColorText', '112,66,70')
end

function RowDate(n)
  local r = row(n)
  if not r or selected or r.t.date == '' then return '' end
  return fmtDate(r.t.date)
end

function RowDateColor(n)
  local r = row(n)
  if r and not r.t.done and r.t.date ~= '' and r.t.date < todayKey then
    return var('ColorAccent', '232,110,122')      -- overdue
  end
  return var('ColorAccent2', '104,160,178')
end

function DelColor(n)
  if row(n) then return var('ColorMuted', '176,142,145') end
  return TRANSPARENT
end

function CheckFill(n)
  local r = row(n)
  if not r then return TRANSPARENT end
  if r.t.done then return var('ColorAccent2', '104,160,178') end
  return var('ColorBox', '255,255,255,210')
end

function CheckStroke(n)
  local r = row(n)
  if not r then return TRANSPARENT end
  if r.t.done then return var('ColorAccent2', '104,160,178') end
  return var('ColorAccent', '232,110,122')
end

function TickColor(n)
  local r = row(n)
  if r and r.t.done then return '255,255,255,255' end
  return TRANSPARENT
end

------------------------------------------------------------------ actions

function Prev()
  viewM = viewM - 1
  if viewM < 1 then viewM = 12; viewY = viewY - 1 end
  redraw()
end

function Next()
  viewM = viewM + 1
  if viewM > 12 then viewM = 1; viewY = viewY + 1 end
  redraw()
end

function GoToday()
  local t = os.date('*t')
  viewY, viewM = t.year, t.month
  selected = os.date('%Y-%m-%d')
  offset = 0
  redraw()
end

function SelectDay(n)
  local c = cells[n]
  if not c then return end
  if selected == c.key then selected = nil else selected = c.key end
  if not c.inMonth then viewY, viewM = c.y, c.m end
  offset = 0
  redraw()
end

function ClearSelection() selected = nil; offset = 0; redraw() end

function Scroll(d) offset = offset + d; redraw() end

function Toggle(n)
  local r = row(n)
  if r then r.t.done = not r.t.done; save() end
  redraw()
end

function Delete(n)
  local r = row(n)
  if r then table.remove(tasks, r.i); save() end
  redraw()
end

-- Called by the InputText plugin (text arrives in the NewTask variable).
-- Typing  "Buy milk @11-20"  or  "Buy milk @2026-11-20"  schedules the task.
function AddFromVar()
  local s = SKIN:GetVariable('NewTask', '') or ''
  s = s:gsub('^%s+', ''):gsub('%s+$', '')
  if s == '' then return end

  local date = selected or ''
  local txt, y, m, d = s:match('^(.-)%s*@(%d%d%d%d)%-(%d%d?)%-(%d%d?)$')
  if not txt then
    txt, m, d = s:match('^(.-)%s*@(%d%d?)%-(%d%d?)$')
    y = os.date('%Y')
  end
  if txt then
    y, m, d = tonumber(y), tonumber(m), tonumber(d)
    local chk = os.date('*t', os.time{year = y, month = m, day = d, hour = 12})
    if chk.month == m and chk.day == d then
      date = key(y, m, d)
      s = txt
    end
  end

  s = s:gsub('|', '/')
  if s == '' then return end

  load()
  tasks[#tasks + 1] = {done = false, date = date, text = s}
  save()
  offset = 0
  redraw()
end
