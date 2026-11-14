# Chopper To-Do

A lightweight Windows calendar and task manager built as a
[Rainmeter](https://www.rainmeter.net/) skin, with optional two-way Google
Calendar and Google Tasks sync.

![Illustrative Chopper To-Do calendar preview](assets/chopper-todo-preview.svg)

## Features

- Monthly calendar with previous/next month navigation.
- Separate **Tasks** and **Events** panels on the right side.
- Click a calendar date to filter both panels to that date.
- Add dated or undated tasks, and add separate calendar events.
- Assign due dates to tasks and set event start/end times using scrollable,
  half-hour time lists.
- Mark tasks complete, delete tasks or events, and scroll longer lists.
- See task and event markers together on calendar dates that have both.
- Optionally sync tasks and events two ways with Google.

## Requirements

- Windows
- Rainmeter
- Python 3.9+ and an internet connection, if Google sync is enabled.

No separate database is required. Google sync uses the Python packages listed
in `ChopperTodo\requirements.txt`.

## Installation

1. Install and start Rainmeter.
2. Extract the `ChopperTodo` skin folder into:

   ```text
   %USERPROFILE%\Documents\Rainmeter\Skins\
   ```

   Keep the files in the `ChopperTodo` folder together. If using Google sync,
   keep `GoogleSync.py`, `Sync.cmd`, `Sync.vbs`, and `requirements.txt` there
   as well.
3. Open Rainmeter's **Manage** window and refresh the skins if needed.
4. In the **Skins** list, find `ChopperTodo\ChopperTodo.ini` and select
   **Load**.
5. Drag the skin to position it. To keep it on the desktop, right-click the
   skin and choose **Settings > Position > On desktop**.

## Using the calendar

- Use the arrows around the month heading to change months.
- Select a date to show only that day's tasks and events. New items are
  assigned to the selected date.
- Select the same date again to clear the filter and show all tasks and events.
- **Today** moves the calendar to the current month and selects today's date.
- Add `@11-20` or `@2026-11-20` to the end of an item's name to assign or
  override its date. The short form uses the current year.

## Tasks and events

The right side is split into two panels: **Tasks** on top and **Events** below.
Each panel shows all items of its type until a calendar date is selected. Four
rows are visible in each panel; use the mouse wheel over an item's name to
scroll that panel independently.

### Adding a task

1. Select a calendar date first if the task should be assigned to a specific
   day; otherwise it will be undated.
2. Click **+ Task** in the Tasks panel.
3. Click the task-name field, type a name, and press Enter to stage the text.
4. Confirm the due date shown in the form, then click **Enter** to save.
   Click **Cancel** to discard the new task.

### Adding an event

1. Select a calendar date first if the event should be assigned to a specific
   day. Without a selected date, a new event is assigned to today.
2. Click **+ Event** in the Events panel.
3. Enter and stage the event name as you would for a task.
4. Set the start and end times if needed, then click **Enter** to save or
   **Cancel** to discard it.

### Times, completion, and deletion

- Tasks use the selected calendar date as their due date; without a selected
  date, the task is undated. New events default to **8:00 AM–9:00 AM**.
- The time lists contain 48 choices, from 12:00 AM to 11:30 PM, in 30-minute
  increments for event times. Scroll within a list to browse the choices.
- For events, changing the start time moves the end time one hour later until
  the end time has been changed manually.
- Click a task's checkbox or name to mark it complete or reopen it. Events do
  not have a completion checkbox.
- Click the **x** beside an item to delete it.
- The calendar uses red for dates with open tasks, teal for dates whose tasks
  are all complete, and orange-yellow for events. If a date has both tasks and
  events, both markers are shown.

## Google Calendar and Tasks sync

Google sync is optional and disabled by default. When enabled, a local helper
uses the Google Calendar API and Google Tasks API; Rainmeter remains the skin's
interface and `tasks.txt` remains its local data file.

### Setup

1. Install Python 3.9 or later for Windows. The commands below use the Windows
   `py` launcher; if `py` is not recognized, install Python with its Windows
   launcher or use `python` if it resolves to an installed Python. Do not
   create this virtual environment from WSL.
2. In [Google Cloud Console](https://console.cloud.google.com/), create a
   project and enable **Google Calendar API** and **Google Tasks API**.
3. Configure the OAuth consent screen and create an OAuth client of type
   **Desktop app**. Download its JSON file into the `ChopperTodo` folder as
   `credentials.json`. If the consent screen is in testing mode, add your
   Google account as a test user.
4. Open PowerShell or Command Prompt in the `ChopperTodo` folder and install
   the helper's dependencies:

   ```text
   py -3 -m venv .venv
   .venv\Scripts\python.exe -m pip install -r requirements.txt
   ```

5. Run `Sync.cmd authorize` and approve access in the browser. This creates a
   local token file.
6. Run `Sync.cmd sync` once to perform the initial sync and check
   `sync.log` for errors.
7. Set `GoogleSyncEnabled=1` in the `[Variables]` section of
   `ChopperTodo.ini`, then refresh the skin. Sync runs in the background after
   local changes and periodically while the skin is loaded.

The helper uses the primary Google Calendar and the default Google Tasks list.
It reads the Google Calendar account's current time-zone setting for event
times. Since the skin stores wall-clock times without a time-zone ID, changing
that Google setting later changes how existing local event times are
interpreted. Keep `credentials.json`, `token.json`, and the sync state files
private; they are excluded from Git.

### What syncs

- Events sync their title, date, and start/end times with the primary Google
  Calendar. Times are interpreted in that calendar's current time zone.
- Tasks sync their title, due date, and completion state with the default
  Google Tasks list. Both Google Tasks and the skin use a date-only due date.
- **Dated synced tasks appear in Google Calendar when its Tasks display is
  enabled.** Their completion state syncs too; whether completed tasks remain
  visible is controlled by Google Calendar's display settings.
- Undated tasks sync to Google Tasks but have no date to show on the Calendar
  grid.
- Google Tasks due dates are used as returned by the API, without a timezone
  conversion or one-day adjustment. The skin displays a task's due date, not
  a due time.
- Past-dated tasks are hidden from the unfiltered **All tasks** list, but
  remain available by selecting their date in the calendar. Past events are
  hidden from the calendar markers and event list and are excluded from sync;
  existing past event records are preserved and are not deleted remotely.
- Dated tasks and events more than one year ahead are hidden from the unfiltered
  lists, but remain stored and synced. Select their date in the calendar to
  view them.
- Deletions propagate to the other side after an item has been linked.
- A simultaneous edit on both sides is not overwritten. The conflict is
  recorded in `sync-conflicts.json`; make the local and Google versions agree
  to resolve it on a later sync.

The first sync matches existing items only when their sync fields match
uniquely. Review existing data first: items that are duplicates or differ
between the skin and Google may be imported or created separately.

The current skin model supports single-day events. Multi-day or overnight
Google Calendar events are reported in `sync-conflicts.json` and skipped
rather than shortened. Undated local events are also reported because the
skin requires a date to sync an event.
Recurring events are synced as individual occurrences; recurrence rules are
not editable in the skin.
Before each remote write, the helper checks that the local data file has not
changed during sync. If it has, the helper stops further sync operations and
preserves the file; run sync again after the local save finishes.

## Data file

The skin reads and writes `tasks.txt` in the same folder as
`ChopperTodo.ini` and `Todo.lua`. It is plain text and can be backed up or
edited with a text editor. The current record format is:

```text
done|date|start|end|kind|id|text
```

| Field | Meaning |
| --- | --- |
| `done` | `0` for open; `1` for complete. Events are stored as open items. |
| `date` | Date in `YYYY-MM-DD` form, or empty for an undated task. |
| `start` | Event start time in 24-hour `HH:MM` form; blank for tasks. |
| `end` | Event end time in 24-hour `HH:MM` form; blank for tasks. |
| `kind` | `task` or `event`. |
| `id` | Stable local ID used to associate the item with Google during sync. |
| `text` | The task or event name. |

For example:

```text
0|2026-11-14|||task|6a7d1000-ab12cd34-123|Review notes
0|2026-11-14|10:30|11:30|event|6a7d1000-ef56ab78-124|Dentist appointment
0||||task|6a7d1000-9abcde12-125|Unscheduled task
```

Older records without IDs are still loaded and assigned an ID on the next save.
The previous `done|date|start|end|kind|text`, `done|date|start|end|text`, and
`done|date|text` formats are also loaded.

## Customization

Edit the `[Variables]` section near the top of `ChopperTodo.ini`, then refresh
the skin. Common options include:

| Variable | Description |
| --- | --- |
| `TitleText` | Text shown in the skin's header. |
| `WeekStart` | `0` starts calendar weeks on Sunday; `1` starts on Monday. |
| `GoogleSyncEnabled` | Set to `1` after completing Google sync setup. |
| `ColorAccent` | Main accent color, including open-task markers. |
| `ColorAccent2` | Secondary accent color, including completed-task markers. |
| `ColorEvent` | Event marker and event-button color. |
| `FontMain`, `FontTitle` | Main and heading fonts. |

Colors use Rainmeter's `R,G,B,A` format, with each channel from `0` to `255`.

## Troubleshooting

- **The skin is missing or looks unchanged:** Refresh Rainmeter, then confirm
  the skin is loaded from `ChopperTodo.ini`.
- **An item has the wrong date:** Select the date before adding it, or add a
  date suffix such as `@2026-11-20` to the name.
- **Tasks or events are missing:** Confirm `tasks.txt` is in the same folder
  as the INI and Lua files. Selecting a calendar date filters both panels.
- **Google sync is not working:** Confirm `GoogleSyncEnabled=1`, that OAuth
  setup is complete, and check `sync.log` and `sync-conflicts.json`.
- **Sync stopped after a local edit:** If `sync.log` reports that `tasks.txt`
  changed during sync, run `Sync.cmd sync` again after the save finishes.
- **Before editing the data file:** Make a copy of `tasks.txt` as a backup.
