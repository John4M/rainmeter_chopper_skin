CHOPPER TO-DO  (Rainmeter skin)

INSTALL
1. Install Rainmeter (rainmeter.net) and run it once.
2. Extract this zip INTO:  Documents\Rainmeter\Skins\
   (the skin works from any folder depth, but keep Todo.lua, tasks.txt and
   ChopperTodo.ini together in the same folder)
3. Right-click the Rainmeter tray icon > Refresh all.
4. Right-click tray icon > Skins > ChopperTodo > ChopperTodo.ini > Load.
5. Drag the card to where you want it, then right-click it >
   Position > "On desktop" (so it sits above Lively but under your windows).

USE
- The right side has separate task and event panels, with tasks above events
  and a matching add button in each panel. Both show all items by default.
- Click a day  -> each panel shows that day's tasks or events; new items are
  assigned to the selected date.
- "+ Task" opens a form with a task-name field and start/end times. Click
  the name field to type a task, then press Enter to stage it. Choose times
  before or after typing, then click Enter to add it or Cancel to discard it.
  Escape cancels text entry.
  Add "@11-20" or "@2026-11-20" at the end to schedule it for that date.
- New tasks default to 8:00 AM-9:00 AM. Click the staged task text to edit it.
  Choose start and end from the dropdown lists; scroll in a list to browse
  times in 30-minute steps. Changing the start also moves the end one hour
  later unless you have changed the end.
- "+ Event" adds a separate calendar event, shown in orange-yellow. Events use the
  selected date, or today if no date is selected, and appear alongside task
  markers in the calendar.
- Click a task (or its box) to tick it off. Click the x to delete it.
- Mouse wheel over a panel scrolls that list when it has more than 4 items.
- Today button jumps to today.

CUSTOMIZE
- Open ChopperTodo.ini (right-click skin > Edit skin) and change the
  [Variables] section at the top, then right-click > Refresh skin.
- Tasks are plain text in tasks.txt in the skin folder
  (done|date|start|end|kind|text), where kind is task or event. Older
  (done|date|start|end|text) and (done|date|text) entries still load.
  You can edit the file in Notepad too.
