-- Chopper To-Do : calendar + task list logic for Rainmeter
-- Tasks and events live in @Resources\tasks.txt, one per line:
--   done|date|start|end|kind|text
-- Older done|date|start|end|text and done|date|text lines still load.

local TASK_ROWS, EVENT_ROWS = 4, 4
local TRANSPARENT = '0,0,0,0'

local tasks, taskVis, eventVis, cells, counts = {}, {}, {}, {}, {}
local viewY, viewM = 2000, 1
local selected = nil                -- 'YYYY-MM-DD' of the clicked day, or nil
local taskOffset, eventOffset = 0, 0
local weekStart = 0                 -- 0 = Sunday first, 1 = Monday first
local file, todayKey = '', ''
local adding = false
local addingKind = 'task'
local startMinutes, endMinutes = 480, 540
local endManuallySet = false
local openDropdown, dropdownOffset = nil, 0
local pendingTask, inputReady = '', false

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
    local d, dt, start, finish, kind, txt =
      line:match('^([01])|([^|]*)|([^|]*)|([^|]*)|([^|]*)|(.*)$')
    if not d then
      d, dt, start, finish, txt =
        line:match('^([01])|([^|]*)|([^|]*)|([^|]*)|(.*)$')
    end
    if not d then
      d, dt, txt = line:match('^([01])|([^|]*)|(.*)$')
    end
    if d and txt ~= '' then
      tasks[#tasks + 1] = {
        done = (d == '1'), date = dt, start = start or '',
        finish = finish or '', kind = (kind == 'event') and 'event' or 'task',
        text = txt
      }
    end
  end
  f:close()
end

local function save()
  local f = io.open(file, 'w')
  if not f then return end
  for _, t in ipairs(tasks) do
    f:write((t.done and '1' or '0') .. '|' .. t.date .. '|' .. (t.start or '') ..
            '|' .. (t.finish or '') .. '|' .. (t.kind or 'task') ..
            '|' .. t.text .. '\n')
  end
  f:close()
end

------------------------------------------------------------------ state

function Initialize()
  file = SKIN:ReplaceVariables('#CURRENTPATH#tasks.txt')
  weekStart = tonumber(var('WeekStart', '0')) or 0
  local t = os.date('*t')
  viewY, viewM = t.year, t.month
  selected, taskOffset, eventOffset = nil, 0, 0
end

function Refresh()
  load()
  todayKey = os.date('%Y-%m-%d')

  counts = {}
  for _, t in ipairs(tasks) do
    if t.date ~= '' then
      local c = counts[t.date] or {open = 0, done = 0, events = 0}
      if t.kind == 'event' then
        c.events = c.events + 1
      elseif t.done then
        c.done = c.done + 1
      else
        c.open = c.open + 1
      end
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

  taskVis, eventVis = {}, {}
  for i, t in ipairs(tasks) do
    if not selected or t.date == selected then
      local item = {i = i, t = t}
      if t.kind == 'event' then
        eventVis[#eventVis + 1] = item
      else
        taskVis[#taskVis + 1] = item
      end
    end
  end
  table.sort(taskVis, function(a, b)
    if a.t.done ~= b.t.done then return not a.t.done end
    if a.t.date ~= b.t.date then
      if a.t.date == '' then return false end
      if b.t.date == '' then return true end
      return a.t.date < b.t.date
    end
    return a.i < b.i
  end)
  table.sort(eventVis, function(a, b)
    if a.t.date ~= b.t.date then return a.t.date < b.t.date end
    if a.t.start ~= b.t.start then return a.t.start < b.t.start end
    return a.i < b.i
  end)

  taskOffset = math.max(0, math.min(taskOffset, #taskVis - TASK_ROWS))
  eventOffset = math.max(0, math.min(eventOffset, #eventVis - EVENT_ROWS))
end

function Update()
  Refresh()
  return 0
end

local function taskRow(n)
  if n < 1 or n > TASK_ROWS then return nil end
  return taskVis[n + taskOffset]
end

local function eventRow(n)
  if n < 1 or n > EVENT_ROWS then return nil end
  return eventVis[n + eventOffset]
end
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

function TaskTitle()
  if selected then return 'Tasks for ' .. fmtDate(selected) end
  return 'All tasks'
end

function EventTitle()
  if selected then return 'Events for ' .. fmtDate(selected) end
  return 'All events'
end

function Summary()
  local done = 0
  for _, r in ipairs(taskVis) do
    if r.t.done then done = done + 1 end
  end
  local s = #taskVis > 0 and (done .. ' of ' .. #taskVis .. ' tasks done') or ''
  if #eventVis > 0 then
    if s ~= '' then s = s .. '   |   ' end
    s = s .. #eventVis .. ' events'
  end
  if #taskVis > TASK_ROWS or #eventVis > EVENT_ROWS then
    if s ~= '' then s = s .. '   |   ' end
    s = s .. 'scroll for more'
  end
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
  if not k or (k.open == 0 and k.done == 0) then return TRANSPARENT end
  if k.open > 0 then return var('ColorAccent', '232,110,122') end
  return var('ColorAccent2', '104,160,178')
end

function DayEventDot(n)
  local c = cells[n]
  local k = c and counts[c.key]
  if k and k.events > 0 then return var('ColorEvent', '245,175,50') end
  return TRANSPARENT
end

function DayDotX(n)
  local c = cells[n]
  local k = c and counts[c.key]
  if k and (k.open + k.done) > 0 and k.events > 0 then return 14 end
  return 19
end

function DayEventDotX(n)
  local c = cells[n]
  local k = c and counts[c.key]
  if k and (k.open + k.done) > 0 and k.events > 0 then return 24 end
  return 19
end

------------------------------------------------------------------ task rows

function RowText(n)
  local r = taskRow(n)
  if not r then
    if n == 1 and #taskVis == 0 then return 'Nothing here yet - add one!' end
    return ''
  end
  return r.t.text
end

function RowColor(n)
  local r = taskRow(n)
  if not r or r.t.done then return var('ColorMuted', '176,142,145') end
  return var('ColorText', '112,66,70')
end

function RowDate(n)
  local r = taskRow(n)
  if not r or selected or r.t.date == '' then return '' end
  return fmtDate(r.t.date)
end

local function formatTime(minutes)
  local h = math.floor(minutes / 60) % 24
  local m = minutes % 60
  return string.format('%d:%02d %s', (h % 12 == 0) and 12 or (h % 12),
                       m, h < 12 and 'AM' or 'PM')
end

local function displayTime(value)
  local h, m = tostring(value):match('^(%d%d?):(%d%d)$')
  h, m = tonumber(h), tonumber(m)
  if not h or not m or h > 23 or m > 59 then return '' end
  return formatTime(h * 60 + m)
end

local function rowTime(r)
  if not r then return '' end
  local start = displayTime(r.t.start)
  local finish = displayTime(r.t.finish)
  if start == '' or finish == '' then return '' end
  return start .. '-' .. finish
end

function RowTime(n) return rowTime(taskRow(n)) end

function RowDateColor(n)
  local r = taskRow(n)
  if r and not r.t.done and r.t.date ~= '' and r.t.date < todayKey then
    return var('ColorAccent', '232,110,122')      -- overdue
  end
  return var('ColorAccent2', '104,160,178')
end

function DelColor(n)
  if taskRow(n) then return var('ColorMuted', '176,142,145') end
  return TRANSPARENT
end

function CheckFill(n)
  local r = taskRow(n)
  if not r then return TRANSPARENT end
  if r.t.done then return var('ColorAccent2', '104,160,178') end
  return var('ColorBox', '255,255,255,210')
end

function CheckStroke(n)
  local r = taskRow(n)
  if not r then return TRANSPARENT end
  if r.t.done then return var('ColorAccent2', '104,160,178') end
  return var('ColorAccent', '232,110,122')
end

function TickColor(n)
  local r = taskRow(n)
  if r and r.t.done then return '255,255,255,255' end
  return TRANSPARENT
end

function CheckHidden(n)
  return taskRow(n) and 0 or 1
end

function EventMarkHidden(n)
  if n < 5 or n > 8 then return 1 end
  return eventRow(n - 4) and 0 or 1
end

function EventText(n)
  local r = eventRow(n)
  if not r then
    if n == 1 and #eventVis == 0 then return 'No events scheduled yet' end
    return ''
  end
  return r.t.text
end

function EventTextColor(n)
  return var('ColorText', '112,66,70')
end

function EventDate(n)
  local r = eventRow(n)
  if not r or selected or r.t.date == '' then return '' end
  return fmtDate(r.t.date)
end

function EventTime(n) return rowTime(eventRow(n)) end

function EventDateColor(n)
  return var('ColorEvent', '245,175,50')
end

function EventDelColor(n)
  if eventRow(n) then return var('ColorMuted', '176,142,145') end
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
  taskOffset, eventOffset = 0, 0
  redraw()
end

function SelectDay(n)
  local c = cells[n]
  if not c then return end
  if selected == c.key then selected = nil else selected = c.key end
  if not c.inMonth then viewY, viewM = c.y, c.m end
  taskOffset, eventOffset = 0, 0
  redraw()
end

function ScrollTasks(d)
  taskOffset = taskOffset + d
  redraw()
end

function ScrollEvents(d)
  eventOffset = eventOffset + d
  redraw()
end

function Scroll(d)
  taskOffset, eventOffset = taskOffset + d, eventOffset + d
  redraw()
end

function Adding() return adding and 0 or 1 end
function NotAdding() return adding and 1 or 0 end

function TimeVisible() return adding and 0 or 1 end

function TimeDropdownHidden()
  return adding and openDropdown and 0 or 1
end

function CardHeight()
  if adding then return 470 end
  return 440
end

function EntryButtonsHidden() return adding and 0 or 1 end
function EntryName()
  if inputReady then return pendingTask end
  return addingKind == 'event' and 'Click here to enter an event' or
         'Click here to enter a task'
end

function StartTimeLabel() return formatTime(startMinutes) end
function EndTimeLabel() return formatTime(endMinutes) end

function TimeDropdownX()
  return openDropdown == 'end' and 520 or 384
end

function DropdownTime(n)
  local minutes = (dropdownOffset + n - 1) * 30
  if minutes < 0 or minutes >= 1440 then return '' end
  return formatTime(minutes)
end

function DropdownTimeColor(n)
  local minutes = (dropdownOffset + n - 1) * 30
  local selectedMinutes = openDropdown == 'start' and startMinutes or endMinutes
  if minutes == selectedMinutes then return var('ColorAccent', '232,110,122') end
  return var('ColorText', '112,66,70')
end

local function clampDropdownOffset(value)
  return math.max(0, math.min(42, value))
end

function OpenTimeDropdown(which)
  if not adding then return end
  if openDropdown == which then
    openDropdown = nil
  else
    openDropdown = which
    local minutes = which == 'start' and startMinutes or endMinutes
    dropdownOffset = clampDropdownOffset(math.floor(minutes / 30) - 2)
  end
  redraw()
end

function ScrollTimeList(direction)
  if not openDropdown then return end
  dropdownOffset = clampDropdownOffset(dropdownOffset + direction)
  redraw()
end

function ChooseTime(n)
  if not openDropdown or n < 1 or n > 6 then return end
  local minutes = (dropdownOffset + n - 1) * 30
  if minutes < 0 or minutes >= 1440 then return end
  if openDropdown == 'start' then
    startMinutes = minutes
    if not endManuallySet then endMinutes = (startMinutes + 60) % 1440 end
  else
    endMinutes = minutes
    endManuallySet = true
  end
  openDropdown = nil
  redraw()
end

function StartAdd(kind)
  adding = true
  addingKind = kind == 'event' and 'event' or 'task'
  startMinutes, endMinutes = 480, 540
  endManuallySet = false
  openDropdown = nil
  dropdownOffset = 0
  pendingTask, inputReady = '', false
  SKIN:Bang('!SetVariable NewTask ""')
  redraw()
end

function CaptureTaskName()
  pendingTask = SKIN:GetVariable('NewTask', '') or ''
  pendingTask = pendingTask:gsub('^%s+', ''):gsub('%s+$', '')
  inputReady = pendingTask ~= ''
  redraw()
end

function EditTaskName()
  if not adding then return end
  inputReady = false
  redraw()
  SKIN:Bang('!CommandMeasure mInput "ExecuteBatch 1"')
end

function CancelAdd()
  adding, openDropdown, inputReady = false, nil, false
  addingKind = 'task'
  pendingTask = ''
  SKIN:Bang('!SetVariable NewTask ""')
  redraw()
end

function Toggle(n)
  local r = taskRow(n)
  if r then r.t.done = not r.t.done; save() end
  redraw()
end

function DeleteTask(n)
  local r = taskRow(n)
  if r then table.remove(tasks, r.i); save() end
  redraw()
end

function DeleteEvent(n)
  local r = eventRow(n)
  if r then table.remove(tasks, r.i); save() end
  redraw()
end

-- Typing "Buy milk @11-20" or "Buy milk @2026-11-20" schedules the task.
function AddFromVar()
  if not adding or not inputReady then return end
  local s = pendingTask

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

  if addingKind == 'event' and date == '' then date = os.date('%Y-%m-%d') end
  s = s:gsub('|', '/')
  if s == '' then return end

  load()
  tasks[#tasks + 1] = {
    done = false,
    date = date,
    start = string.format('%02d:%02d', math.floor(startMinutes / 60), startMinutes % 60),
    finish = string.format('%02d:%02d', math.floor(endMinutes / 60), endMinutes % 60),
    kind = addingKind,
    text = s
  }
  save()
  taskOffset, eventOffset = 0, 0
  adding, openDropdown, inputReady = false, nil, false
  addingKind = 'task'
  pendingTask = ''
  SKIN:Bang('!SetVariable NewTask ""')
  redraw()
end
