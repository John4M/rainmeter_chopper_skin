# Chopper To-Do

Chopper To-Do is a desktop calendar and task/event tracker built as a
[Rainmeter](https://www.rainmeter.net/) skin for Windows. It stores its data in
a plain-text file in the skin folder.

## Features

- Monthly calendar with previous/next month navigation.
- Separate **Tasks** and **Events** panels on the right side.
- Click a calendar date to filter both panels to that date.
- Add dated or undated tasks, and add separate calendar events.
- Set start and end times using scrollable, half-hour time lists.
- Mark tasks complete, delete tasks or events, and scroll longer lists.
- See task and event markers together on calendar dates that have both.

## Requirements

- Windows
- Rainmeter

No separate database or package installation is required.

## Installation

1. Install and start Rainmeter.
2. Extract the `ChopperTodo` skin folder into:

   ```text
   %USERPROFILE%\Documents\Rainmeter\Skins\
   ```

   Keep `ChopperTodo.ini`, `Todo.lua`, and `tasks.txt` together in the
   `ChopperTodo` folder.
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
4. Choose start and end times if needed, then click **Enter** to save. Click
   **Cancel** to discard the new task.

### Adding an event

1. Select a calendar date first if the event should be assigned to a specific
   day. Without a selected date, a new event is assigned to today.
2. Click **+ Event** in the Events panel.
3. Enter and stage the event name as you would for a task.
4. Set the times if needed, then click **Enter** to save or **Cancel** to
   discard it.

### Times, completion, and deletion

- New tasks and events default to **8:00 AM–9:00 AM**.
- The time lists contain 48 choices, from 12:00 AM to 11:30 PM, in 30-minute
  increments. Scroll within a list to browse the choices.
- Changing the start time moves the end time one hour later until the end time
  has been changed manually.
- Click a task's checkbox or name to mark it complete or reopen it. Events do
  not have a completion checkbox.
- Click the **x** beside an item to delete it.
- The calendar uses red for dates with open tasks, teal for dates whose tasks
  are all complete, and orange-yellow for events. If a date has both tasks and
  events, both markers are shown.

## Data file

The skin reads and writes `tasks.txt` in the same folder as
`ChopperTodo.ini` and `Todo.lua`. It is plain text and can be backed up or
edited with a text editor. The current record format is:

```text
done|date|start|end|kind|text
```

| Field | Meaning |
| --- | --- |
| `done` | `0` for open; `1` for complete. Events are stored as open items. |
| `date` | Date in `YYYY-MM-DD` form, or empty for an undated task. |
| `start` | Start time in 24-hour `HH:MM` form. |
| `end` | End time in 24-hour `HH:MM` form. |
| `kind` | `task` or `event`. |
| `text` | The task or event name. |

For example:

```text
0|2026-11-14|08:00|09:00|task|Review notes
0|2026-11-14|10:30|11:30|event|Dentist appointment
0|||task|Unscheduled task
```

Older `done|date|start|end|text` and `done|date|text` records are also loaded
as tasks. The skin writes records in the current format when it next saves
changes.

## Customization

Edit the `[Variables]` section near the top of `ChopperTodo.ini`, then refresh
the skin. Common options include:

| Variable | Description |
| --- | --- |
| `TitleText` | Text shown in the skin's header. |
| `WeekStart` | `0` starts calendar weeks on Sunday; `1` starts on Monday. |
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
- **Before editing the data file:** Make a copy of `tasks.txt` as a backup.
