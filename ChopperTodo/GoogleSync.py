import argparse
import json
import logging
import os
import re
import time
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parent
TASKS_FILE = ROOT / "tasks.txt"
STATE_FILE = ROOT / "sync-state.json"
CONFLICTS_FILE = ROOT / "sync-conflicts.json"
TOKEN_FILE = ROOT / "token.json"
CREDENTIALS_FILE = ROOT / "credentials.json"
SCOPES = [
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/calendar.settings.readonly",
    "https://www.googleapis.com/auth/tasks",
]
LOCAL_ID = re.compile(r"^[0-9a-fA-F]+-[0-9a-fA-F]+-[0-9]+$")
API_RETRIES = 5


@dataclass
class Item:
    done: bool
    date: str
    start: str
    finish: str
    kind: str
    id: str
    text: str


def new_id():
    return f"{int(time.time()):x}-{uuid.uuid4().hex[:8]}-{time.time_ns() % 1000000}"


def parse_items(path):
    items = []
    changed = False
    if not path.exists():
        return items, changed

    for line_number, raw in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        if not raw:
            continue
        parts = raw.split("|", 6)
        done = parts[0] if parts else ""
        if done not in ("0", "1"):
            raise ValueError(f"{path.name}:{line_number}: invalid completion value")

        if len(parts) == 7 and LOCAL_ID.fullmatch(parts[5]):
            _, item_date, start, finish, kind, item_id, text = parts
        else:
            legacy = raw.split("|", 5)
            if len(legacy) == 6 and legacy[4] in ("task", "event"):
                _, item_date, start, finish, kind, text = legacy
            else:
                legacy = raw.split("|", 4)
                if len(legacy) == 5:
                    _, item_date, start, finish, text = legacy
                    kind = "task"
                else:
                    legacy = raw.split("|", 2)
                    if len(legacy) != 3:
                        raise ValueError(f"{path.name}:{line_number}: unrecognized record")
                    _, item_date, text = legacy
                    start, finish, kind = "", "", "task"
            item_id = ""

        kind = "event" if kind == "event" else "task"
        start = start or ""
        finish = finish or ""
        if kind == "task":
            if start or finish:
                changed = True
            start, finish = "", ""
        if not item_id:
            item_id = new_id()
            changed = True
        items.append(Item(done == "1", item_date, start, finish, kind, item_id, text))

    return items, changed


def write_items(path, items):
    lines = []
    for item in items:
        text = item.text.replace("|", "/").replace("\r", " ").replace("\n", " ")
        lines.append(
            f"{int(item.done)}|{item.date}|{item.start}|{item.finish}|"
            f"{item.kind}|{item.id}|{text}"
        )
    atomic_write(path, ("\n".join(lines) + ("\n" if lines else "")).encode("utf-8"))


def atomic_write(path, content):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(content)
    os.replace(temporary, path)


def execute_api_request(request):
    return request.execute(num_retries=API_RETRIES)


def load_json(path, default):
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def save_state(state):
    atomic_write(STATE_FILE, json.dumps(state, indent=2, sort_keys=True).encode("utf-8"))


def record_snapshot(item):
    if item.kind == "task":
        return {
            "kind": "task",
            "title": item.text,
            "date": item.date,
            "done": item.done,
        }
    return {
        "kind": "event",
        "title": item.text,
        "date": item.date,
        "start": item.start,
        "end": item.finish,
    }


def changed_locally_for_deletion(item, mapping):
    return record_snapshot(item) != mapping.get("last_synced")


def event_snapshot(event, calendar_timezone):
    if event.get("status") == "cancelled":
        return None
    start = event.get("start", {})
    end = event.get("end", {})
    if start.get("date"):
        start_date = start["date"]
        end_date = end.get("date", start_date)
        if end_date != (date.fromisoformat(start_date) + timedelta(days=1)).isoformat():
            raise ValueError(f"Multi-day event is not supported: {event.get('id', '')}")
        return {
            "kind": "event",
            "title": event.get("summary", ""),
            "date": start_date,
            "start": "",
            "end": "",
        }

    zone = ZoneInfo(calendar_timezone)
    start_dt = datetime.fromisoformat(start["dateTime"].replace("Z", "+00:00"))
    end_dt = datetime.fromisoformat(end["dateTime"].replace("Z", "+00:00"))
    if start_dt.tzinfo is None:
        start_dt = start_dt.replace(tzinfo=zone)
    if end_dt.tzinfo is None:
        end_dt = end_dt.replace(tzinfo=zone)
    start_dt = start_dt.astimezone(zone)
    end_dt = end_dt.astimezone(zone)
    if start_dt.date() != end_dt.date():
        raise ValueError(f"Multi-day event is not supported: {event.get('id', '')}")
    return {
        "kind": "event",
        "title": event.get("summary", ""),
        "date": start_dt.date().isoformat(),
        "start": start_dt.strftime("%H:%M"),
        "end": end_dt.strftime("%H:%M"),
    }


def task_snapshot(task):
    if task.get("deleted"):
        return None
    due = task.get("due", "")
    return {
        "kind": "task",
        "title": task.get("title", ""),
        "date": due[:10] if due else "",
        "done": task.get("status") == "completed",
    }


def snapshot_to_item(snapshot, item_id):
    if snapshot["kind"] == "task":
        return Item(
            bool(snapshot["done"]), snapshot["date"], "", "", "task", item_id,
            snapshot["title"].replace("|", "/"),
        )
    return Item(
        False, snapshot["date"], snapshot["start"], snapshot["end"], "event", item_id,
        snapshot["title"].replace("|", "/"),
    )


def event_payload(item, calendar_timezone, include_local_id=True):
    if not item.date:
        raise ValueError("Events without a date cannot be synced")
    payload = {"summary": item.text}
    if include_local_id:
        payload["extendedProperties"] = {
            "private": {"chopperTodoId": item.id}
        }
    if item.start and item.finish:
        if item.finish <= item.start:
            raise ValueError(
                f"Event {item.text!r} must end later on the same day than it starts"
            )
        payload["start"] = {
            "dateTime": f"{item.date}T{item.start}:00",
            "timeZone": calendar_timezone,
        }
        payload["end"] = {
            "dateTime": f"{item.date}T{item.finish}:00",
            "timeZone": calendar_timezone,
        }
    else:
        payload["start"] = {"date": item.date}
        payload["end"] = {
            "date": (date.fromisoformat(item.date) + timedelta(days=1)).isoformat()
        }
    return payload


def task_payload(item, updating=False):
    payload = {
        "title": item.text,
        "status": "completed" if item.done else "needsAction",
    }
    if item.date:
        payload["due"] = f"{item.date}T00:00:00.000Z"
    elif updating:
        payload["due"] = None
    if item.done:
        payload["completed"] = datetime.now(timezone.utc).isoformat()
    elif updating:
        payload["completed"] = None
    return payload


def append_conflict(state, kind, item_id, remote_id, local, remote):
    conflicts = state.setdefault("conflicts", {})
    key = f"{kind}:{item_id}"
    conflicts[key] = {
        "kind": kind,
        "local_id": item_id,
        "google_id": remote_id,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "local": local,
        "google": remote,
    }
    logging.warning("Conflict for %s %s; see %s", kind, item_id, CONFLICTS_FILE.name)


def clear_conflict(state, kind, item_id):
    state.setdefault("conflicts", {}).pop(f"{kind}:{item_id}", None)


def execute_remote(
    service, kind, action, item, remote_id=None, calendar_timezone=None, etag=None
):
    if kind == "event":
        calendar_id = "primary"
        if action == "create":
            return execute_api_request(service.events().insert(
                calendarId=calendar_id,
                body=event_payload(item, calendar_timezone),
            ))
        if action == "update":
            request = service.events().patch(
                calendarId=calendar_id,
                eventId=remote_id,
                body=event_payload(item, calendar_timezone, include_local_id=False),
            )
            if etag:
                request.headers["If-Match"] = etag
            return execute_api_request(request)
        if action == "delete":
            execute_api_request(
                service.events().delete(calendarId=calendar_id, eventId=remote_id)
            )
            return None

    tasklist = "@default"
    if action == "create":
        return execute_api_request(
            service.tasks().insert(tasklist=tasklist, body=task_payload(item))
        )
    if action == "update":
        request = service.tasks().patch(
            tasklist=tasklist, task=remote_id, body=task_payload(item, updating=True)
        )
        if etag:
            request.headers["If-Match"] = etag
        return execute_api_request(request)
    if action == "delete":
        execute_api_request(service.tasks().delete(tasklist=tasklist, task=remote_id))
        return None
    raise ValueError(f"Unknown remote action: {action}")


def push_remote(
    state, service, kind, action, item, calendar_timezone, remote_id=None, etag=None
):
    try:
        return execute_remote(
            service, kind, action, item, remote_id,
            calendar_timezone=calendar_timezone, etag=etag,
        )
    except ValueError as error:
        append_conflict(
            state, kind, item.id, remote_id, record_snapshot(item),
            {"error": str(error)},
        )
        return None


def remote_snapshot(kind, remote, calendar_timezone, state):
    if kind != "event":
        return task_snapshot(remote)
    conflict_key = f"unsupported:event:{remote.get('id', '')}"
    try:
        snapshot = event_snapshot(remote, calendar_timezone)
    except ValueError as error:
        state.setdefault("conflicts", {})[conflict_key] = {
            "kind": "unsupported_event",
            "google_id": remote.get("id", ""),
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "message": str(error),
        }
        logging.warning("%s", error)
        return None
    clear_conflict(state, "unsupported", f"event:{remote.get('id', '')}")
    return snapshot


def remote_deleted(kind, remote):
    if remote is None:
        return False
    if kind == "event":
        return remote.get("status") == "cancelled"
    return bool(remote.get("deleted"))


def remote_id_for(remote):
    return remote.get("id", "")


def private_local_id(event):
    return event.get("extendedProperties", {}).get("private", {}).get("chopperTodoId")


def sync_collection(
    kind, items, remotes, state, service, calendar_timezone, full_snapshot,
    ignore_events_before=None, before_remote_write=None,
):
    def push(item, action, remote_id=None, etag=None):
        if before_remote_write is not None:
            before_remote_write()
        return push_remote(
            state, service, kind, action, item, calendar_timezone, remote_id, etag
        )

    def delete_remote(remote_id):
        if before_remote_write is not None:
            before_remote_write()
        return execute_remote(service, kind, "delete", None, remote_id)

    item_states = state.setdefault("items", {})
    local = {item.id: item for item in items if item.kind == kind}
    mappings = {
        item_id: mapping
        for item_id, mapping in item_states.items()
        if mapping.get("kind") == kind
    }
    if kind == "task":
        for mapping in mappings.values():
            mapping.pop("local_due_time", None)
    remote_by_id = {remote_id_for(remote): remote for remote in remotes}
    processed_remote = set()
    ignored_remote_ids = set()
    if kind == "event" and ignore_events_before:
        for remote in remotes:
            if remote_deleted(kind, remote):
                continue
            snapshot = remote_snapshot(kind, remote, calendar_timezone, state)
            if (
                snapshot is not None
                and snapshot["date"]
                and snapshot["date"] < ignore_events_before
            ):
                ignored_remote_ids.add(remote_id_for(remote))

    for item_id, mapping in list(mappings.items()):
        item = local.get(item_id)
        remote_id = mapping.get("remote_id", "")
        remote = remote_by_id.get(remote_id)
        if kind == "event" and ignore_events_before:
            if item is not None and item.date and item.date < ignore_events_before:
                continue
            if remote_id in ignored_remote_ids:
                continue
            if (
                (remote is None or remote_deleted(kind, remote))
                and mapping.get("last_synced", {}).get("date", "")
                and mapping["last_synced"]["date"] < ignore_events_before
            ):
                continue
        if mapping.get("remote_deleted"):
            if item is not None:
                created = push(item, "create")
                if created is None:
                    continue
                mapping["remote_id"] = created["id"]
                mapping["last_synced"] = record_snapshot(item)
                mapping["etag"] = created.get("etag", "")
                mapping.pop("remote_deleted", None)
                clear_conflict(state, kind, item_id)
                processed_remote.add(created["id"])
            continue

        is_deleted = remote_deleted(kind, remote) or (full_snapshot and remote is None)
        if is_deleted:
            local_changed = (
                item is not None and changed_locally_for_deletion(item, mapping)
            )
            if item is None:
                item_states.pop(item_id, None)
            elif local_changed:
                append_conflict(
                    state, kind, item_id, remote_id, record_snapshot(item), None
                )
                mapping["remote_deleted"] = True
            else:
                items.remove(item)
                item_states.pop(item_id, None)
            continue

        if remote is None:
            if item is None:
                if not full_snapshot:
                    delete_remote(remote_id)
                    item_states.pop(item_id, None)
                continue
            baseline = mapping.get("last_synced")
            current = record_snapshot(item)
            if current != baseline:
                updated = push(item, "update", remote_id, mapping.get("etag"))
                if updated is None:
                    continue
                mapping["last_synced"] = remote_snapshot(
                    kind, updated, calendar_timezone, state
                )
                mapping["etag"] = updated.get("etag", mapping.get("etag", ""))
                processed_remote.add(remote_id)
            continue

        processed_remote.add(remote_id)
        if remote.get("etag"):
            mapping["etag"] = remote["etag"]
        if item is None:
            google_snapshot = remote_snapshot(kind, remote, calendar_timezone, state)
            if google_snapshot is None:
                append_conflict(
                    state, kind, item_id, remote_id, None, "unsupported event"
                )
                continue
            if google_snapshot == mapping.get("last_synced"):
                delete_remote(remote_id)
                item_states.pop(item_id, None)
            else:
                append_conflict(
                    state, kind, item_id, remote_id, None,
                    google_snapshot,
                )
                imported = snapshot_to_item(google_snapshot, new_id())
                items.append(imported)
                item_states.pop(item_id, None)
                item_states[imported.id] = {
                    "kind": kind,
                    "remote_id": remote_id,
                    "last_synced": google_snapshot,
                    "etag": remote.get("etag", ""),
                }
            continue

        baseline = mapping.get("last_synced")
        local_snapshot = record_snapshot(item)
        google_snapshot = remote_snapshot(kind, remote, calendar_timezone, state)
        if google_snapshot is None:
            continue
        local_changed = local_snapshot != baseline
        google_changed = google_snapshot != baseline

        if local_changed and google_changed:
            if local_snapshot == google_snapshot:
                mapping["last_synced"] = local_snapshot
                clear_conflict(state, kind, item_id)
            else:
                append_conflict(
                    state, kind, item_id, remote_id, local_snapshot, google_snapshot
                )
        elif local_changed:
            updated = push(item, "update", remote_id, mapping.get("etag"))
            if updated is None:
                continue
            mapping["last_synced"] = remote_snapshot(
                kind, updated, calendar_timezone, state
            )
            mapping["etag"] = updated.get("etag", mapping.get("etag", ""))
            clear_conflict(state, kind, item_id)
        elif google_changed:
            new_item = snapshot_to_item(google_snapshot, item_id)
            item.done, item.date = new_item.done, new_item.date
            item.start, item.finish = new_item.start, new_item.finish
            item.text = new_item.text
            mapping["last_synced"] = google_snapshot
            clear_conflict(state, kind, item_id)
        else:
            clear_conflict(state, kind, item_id)

    known_remote = {
        mapping.get("remote_id")
        for mapping in item_states.values()
        if mapping.get("kind") == kind
    }
    unlinked_local = [
        item for item in items
        if item.kind == kind and item.id not in item_states
        and not (
            kind == "event" and ignore_events_before
            and item.date and item.date < ignore_events_before
        )
    ]
    unlinked_remote = [
        remote for remote in remotes
        if remote_id_for(remote)
        and remote_id_for(remote) not in known_remote
        and remote_id_for(remote) not in processed_remote
        and remote_id_for(remote) not in ignored_remote_ids
        and not remote_deleted(kind, remote)
    ]

    if kind == "event":
        for remote in list(unlinked_remote):
            linked_id = private_local_id(remote)
            if linked_id and linked_id in local and linked_id not in item_states:
                snapshot = remote_snapshot(kind, remote, calendar_timezone, state)
                if snapshot is None:
                    continue
                item_states[linked_id] = {
                    "kind": kind,
                    "remote_id": remote_id_for(remote),
                    "last_synced": snapshot,
                    "etag": remote.get("etag", ""),
                }
                clear_conflict(state, kind, linked_id)
                unlinked_local = [
                    item for item in unlinked_local if item.id != linked_id
                ]
                unlinked_remote.remove(remote)
                processed_remote.add(remote_id_for(remote))

    def signature(snapshot):
        return json.dumps(snapshot, sort_keys=True)

    remote_signatures = {}
    for remote in unlinked_remote:
        snapshot = remote_snapshot(kind, remote, calendar_timezone, state)
        if snapshot is not None:
            remote_signatures.setdefault(signature(snapshot), []).append(remote)

    for item in list(unlinked_local):
        if kind == "event" and not item.date:
            append_conflict(
                state, kind, item.id, None, record_snapshot(item),
                {"error": "Events without a date cannot be synced"},
            )
            continue
        local_snapshot = record_snapshot(item)
        candidates = remote_signatures.get(signature(local_snapshot), [])
        if len(candidates) == 1:
            remote = candidates.pop()
            remote_id = remote_id_for(remote)
            item_states[item.id] = {
                "kind": kind,
                "remote_id": remote_id,
                "last_synced": local_snapshot,
                "etag": remote.get("etag", ""),
            }
            clear_conflict(state, kind, item.id)
            processed_remote.add(remote_id)
            continue
        created = push(item, "create")
        if created is None:
            continue
        remote_id = created["id"]
        item_states[item.id] = {
            "kind": kind,
            "remote_id": remote_id,
            "last_synced": remote_snapshot(kind, created, calendar_timezone, state),
            "etag": created.get("etag", ""),
        }
        clear_conflict(state, kind, item.id)
        processed_remote.add(remote_id)

    for remote in unlinked_remote:
        remote_id = remote_id_for(remote)
        if remote_id in processed_remote:
            continue
        snapshot = remote_snapshot(kind, remote, calendar_timezone, state)
        if snapshot is None:
            continue
        imported = snapshot_to_item(snapshot, new_id())
        items.append(imported)
        item_states[imported.id] = {
            "kind": kind,
            "remote_id": remote_id,
            "last_synced": snapshot,
            "etag": remote.get("etag", ""),
        }
        processed_remote.add(remote_id)


def google_services():
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError as error:
        raise RuntimeError(
            "Google sync dependencies are missing; install requirements.txt first"
        ) from error

    credentials = None
    if TOKEN_FILE.exists():
        credentials = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    if credentials and credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
        TOKEN_FILE.write_text(credentials.to_json(), encoding="utf-8")
    if not credentials or not credentials.valid:
        if not CREDENTIALS_FILE.exists():
            raise FileNotFoundError(
                "credentials.json is missing; create a Desktop OAuth client and "
                "put its downloaded JSON beside GoogleSync.py"
            )
        flow = InstalledAppFlow.from_client_secrets_file(
            str(CREDENTIALS_FILE), SCOPES
        )
        credentials = flow.run_local_server(port=0)
        TOKEN_FILE.write_text(credentials.to_json(), encoding="utf-8")
    return (
        build("calendar", "v3", credentials=credentials, cache_discovery=False),
        build("tasks", "v1", credentials=credentials, cache_discovery=False),
    )


def authorize():
    google_services()
    print("Google authorization complete.")


def list_events(calendar, sync_token):
    from googleapiclient.errors import HttpError

    full_snapshot = not sync_token
    query = {
        "calendarId": "primary",
        "singleEvents": True,
        "showDeleted": True,
        "maxResults": 2500,
    }
    if sync_token:
        query["syncToken"] = sync_token

    def fetch(params):
        result, page_token, next_token = [], None, None
        while True:
            page_query = dict(params)
            if page_token:
                page_query["pageToken"] = page_token
            response = execute_api_request(calendar.events().list(**page_query))
            result.extend(response.get("items", []))
            page_token = response.get("nextPageToken")
            if not page_token:
                next_token = response.get("nextSyncToken", next_token)
                break
        return result, next_token

    try:
        events, next_token = fetch(query)
    except HttpError as error:
        if error.resp.status != 410 or not sync_token:
            raise
        logging.warning("Calendar sync token expired; performing a full sync")
        query.pop("syncToken", None)
        full_snapshot = True
        events, next_token = fetch(query)
    if not next_token:
        raise RuntimeError("Calendar API did not return a nextSyncToken")
    return events, next_token, full_snapshot


def list_tasks(tasks_service):
    result, page_token = [], None
    while True:
        request = tasks_service.tasks().list(
            tasklist="@default",
            showCompleted=True,
            showHidden=True,
            showDeleted=True,
            maxResults=100,
            pageToken=page_token,
        )
        response = execute_api_request(request)
        result.extend(response.get("items", []))
        page_token = response.get("nextPageToken")
        if not page_token:
            return result


def acquire_lock():
    import msvcrt

    handle = (ROOT / "sync.lock").open("a+b")
    handle.seek(0, os.SEEK_END)
    if handle.tell() == 0:
        handle.write(b"\0")
        handle.flush()
    handle.seek(0)
    try:
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        handle.close()
        return None
    return handle


def release_lock(handle):
    import msvcrt

    handle.seek(0)
    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    handle.close()


def sync():
    lock = acquire_lock()
    if lock is None:
        logging.info("Another sync is already running")
        return
    try:
        calendar, tasks_service = google_services()
        from googleapiclient.errors import HttpError

        original_tasks = TASKS_FILE.read_bytes() if TASKS_FILE.exists() else None
        items, _ = parse_items(TASKS_FILE)
        current_tasks = TASKS_FILE.read_bytes() if TASKS_FILE.exists() else None
        if current_tasks != original_tasks:
            raise RuntimeError("tasks.txt changed while sync was starting; retry later")

        def assert_tasks_unchanged():
            current = TASKS_FILE.read_bytes() if TASKS_FILE.exists() else None
            if current != original_tasks:
                raise RuntimeError(
                    "tasks.txt changed during sync; aborting further API writes. "
                    "Local changes were preserved; run sync again to reconcile them."
                )

        state = load_json(STATE_FILE, {
            "version": 1,
            "calendar_sync_token": "",
            "items": {},
            "conflicts": {},
        })
        local_task_count = sum(item.kind == "task" for item in items)
        local_event_count = sum(item.kind == "event" for item in items)
        logging.info(
            "Sync inventory: %d local tasks, %d local events",
            local_task_count, local_event_count,
        )

        failures = []
        prior_token = state.get("calendar_sync_token", "")
        next_token = prior_token
        calendar_timezone = "UTC"
        calendar_synced = False
        try:
            timezone_info = execute_api_request(
                calendar.settings().get(setting="timezone")
            )
            calendar_timezone = timezone_info.get("value")
            if not calendar_timezone:
                raise RuntimeError("Primary Google Calendar has no time zone")
            ZoneInfo(calendar_timezone)
            events, next_token, full_snapshot = list_events(calendar, prior_token)
            assert_tasks_unchanged()
            sync_collection(
                "event", items, events, state, calendar, calendar_timezone,
                full_snapshot,
                ignore_events_before=datetime.now(
                    ZoneInfo(calendar_timezone)
                ).date().isoformat(),
                before_remote_write=assert_tasks_unchanged,
            )
            calendar_synced = True
        except HttpError as error:
            failures.append("Google Calendar")
            next_token = prior_token
            logging.error(
                "Google Calendar sync failed; it will retry next time: %s", error
            )

        try:
            remote_tasks = list_tasks(tasks_service)
            logging.info("Google Tasks returned %d tasks", len(remote_tasks))
            assert_tasks_unchanged()
            sync_collection(
                "task", items, remote_tasks, state, tasks_service, calendar_timezone,
                True, before_remote_write=assert_tasks_unchanged,
            )
        except HttpError as error:
            failures.append("Google Tasks")
            logging.error("Google Tasks sync failed; it will retry next time: %s", error)

        assert_tasks_unchanged()
        if calendar_synced:
            state["calendar_sync_token"] = next_token
        write_items(TASKS_FILE, items)
        save_state(state)
        atomic_write(
            CONFLICTS_FILE,
            json.dumps(list(state.get("conflicts", {}).values()), indent=2).encode("utf-8"),
        )
        if failures:
            message = ", ".join(failures)
            logging.warning("Google sync partially failed: %s", message)
            print(f"Google sync incomplete ({message}); check sync.log.")
        else:
            logging.info("Google sync completed: %d local items", len(items))
            print("Google sync completed.")
    finally:
        release_lock(lock)


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    parser = argparse.ArgumentParser(description="Two-way Chopper To-Do Google sync")
    parser.add_argument("command", nargs="?", choices=("authorize", "sync"), default="sync")
    args = parser.parse_args()
    if args.command == "authorize":
        authorize()
    else:
        sync()


if __name__ == "__main__":
    main()
