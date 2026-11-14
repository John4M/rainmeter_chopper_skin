import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import GoogleSync as sync


class FakeRequest:
    def __init__(self, result):
        self.result = result
        self.headers = {}
        self.num_retries = None

    def execute(self, num_retries=0):
        self.num_retries = num_retries
        return self.result


class FakeTasksService:
    def __init__(self, updated=None):
        self.updated = updated
        self.calls = []
        self.request = None

    def tasks(self):
        return self

    def patch(self, **kwargs):
        self.calls.append(("patch", kwargs))
        self.request = FakeRequest(self.updated)
        return self.request

    def delete(self, **kwargs):
        self.calls.append(("delete", kwargs))
        return FakeRequest({})


class GoogleSyncTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.state_path = Path(self.directory.name) / "sync-state.json"
        state_patch = patch.object(sync, "STATE_FILE", self.state_path)
        state_patch.start()
        self.addCleanup(state_patch.stop)

    def test_reads_legacy_records_and_assigns_ids(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tasks.txt"
            path.write_text(
                "0|2026-11-14|08:00|09:00|task|Read\n"
                "0|2026-11-15|10:30|11:30|event|Meeting\n"
                "1|2026-11-16|Old task\n",
                encoding="utf-8",
            )

            items, changed = sync.parse_items(path)

            self.assertTrue(changed)
            self.assertEqual(items[0].start, "")
            self.assertEqual(items[0].finish, "")
            self.assertEqual(items[1].start, "10:30")
            self.assertEqual(items[2].finish, "")
            self.assertTrue(all(item.id for item in items))

    def test_current_record_format_round_trips_local_id(self):
        item = sync.Item(
            False, "2026-11-14", "", "", "task",
            "6a7d1000-ab12cd34-123", "Review",
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tasks.txt"

            sync.write_items(path, [item])
            items, changed = sync.parse_items(path)

        self.assertFalse(changed)
        self.assertEqual(items, [item])

    def test_google_task_due_date_is_used_without_adjustment(self):
        snapshot = sync.task_snapshot({
            "title": "Due tomorrow",
            "due": "2026-11-15T00:00:00.000Z",
            "status": "needsAction",
        })

        assert snapshot is not None
        item = sync.snapshot_to_item(snapshot, "local-1")

        self.assertEqual(item.date, "2026-11-15")
        self.assertEqual(item.finish, "")

    def test_api_requests_use_retries(self):
        request = FakeRequest({"ok": True})

        result = sync.execute_api_request(request)

        self.assertEqual(result, {"ok": True})
        self.assertEqual(request.num_retries, sync.API_RETRIES)

    def test_event_snapshot_uses_calendar_timezone(self):
        event = {
            "id": "event-1",
            "start": {"dateTime": "2026-11-14T15:00:00+00:00"},
            "end": {"dateTime": "2026-11-14T16:00:00+00:00"},
        }

        snapshot = sync.event_snapshot(event, "America/New_York")

        assert snapshot is not None
        self.assertEqual(snapshot["date"], "2026-11-14")
        self.assertEqual(snapshot["start"], "10:00")
        self.assertEqual(snapshot["end"], "11:00")

    def test_task_payload_sends_due_date_not_local_due_time(self):
        item = sync.Item(False, "2026-11-15", "", "", "task", "a-b-1", "Submit")

        payload = sync.task_payload(item)

        self.assertEqual(payload["due"], "2026-11-15T00:00:00.000Z")

    def test_calendar_payload_rejects_overnight_events(self):
        item = sync.Item(
            False, "2026-11-14", "22:00", "01:00", "event", "a-b-1", "Overnight"
        )

        with self.assertRaisesRegex(ValueError, "same day"):
            sync.event_payload(item, "America/New_York")

    def test_unsupported_multiday_calendar_event_is_reported(self):
        event = {
            "id": "google-event",
            "start": {"date": "2026-11-14"},
            "end": {"date": "2026-11-16"},
        }
        state = {}

        with self.assertLogs(level="WARNING"):
            snapshot = sync.remote_snapshot("event", event, "UTC", state)

        self.assertIsNone(snapshot)
        self.assertIn("unsupported:event:google-event", state["conflicts"])

    def test_undated_local_event_is_reported(self):
        item = sync.Item(False, "", "10:00", "11:00", "event", "local-1", "Meeting")
        state = {}

        with self.assertLogs(level="WARNING"):
            sync.sync_collection(
                "event", [item], [], state, object(), "UTC", True
            )

        self.assertEqual(
            state["conflicts"]["event:local-1"]["google"],
            {"error": "Events without a date cannot be synced"},
        )

    def test_past_remote_event_is_not_imported(self):
        remote = {
            "id": "google-past",
            "summary": "Old event",
            "start": {"date": "2026-11-13"},
            "end": {"date": "2026-11-14"},
        }
        items = []
        state = {}

        sync.sync_collection(
            "event", items, [remote], state, object(), "UTC", True,
            ignore_events_before="2026-11-14",
        )

        self.assertEqual(items, [])
        self.assertEqual(state.get("items", {}), {})

    def test_past_local_event_is_preserved_when_missing_remotely(self):
        item = sync.Item(
            False, "2026-11-13", "10:00", "11:00",
            "event", "local-past", "Old event",
        )
        mapping = {
            "kind": "event",
            "remote_id": "google-past",
            "last_synced": {
                "kind": "event",
                "title": "Old event",
                "date": "2026-11-13",
                "start": "10:00",
                "end": "11:00",
            },
        }
        items = [item]
        state = {"items": {"local-past": mapping}}

        sync.sync_collection(
            "event", items, [], state, object(), "UTC", True,
            ignore_events_before="2026-11-14",
        )

        self.assertEqual(items, [item])
        self.assertEqual(state["items"]["local-past"], mapping)

    def test_past_remote_event_is_not_deleted_when_local_item_is_missing(self):
        remote = {
            "id": "google-past",
            "summary": "Old event",
            "start": {"date": "2026-11-13"},
            "end": {"date": "2026-11-14"},
        }
        mapping = {
            "kind": "event",
            "remote_id": "google-past",
            "last_synced": {
                "kind": "event",
                "title": "Old event",
                "date": "2026-11-13",
                "start": "",
                "end": "",
            },
        }
        state = {"items": {"local-past": mapping}}

        sync.sync_collection(
            "event", [], [remote], state, object(), "UTC", True,
            ignore_events_before="2026-11-14",
        )

        self.assertEqual(state["items"]["local-past"], mapping)

    def test_event_on_cutoff_date_is_still_imported(self):
        remote = {
            "id": "google-today",
            "summary": "Today",
            "start": {"date": "2026-11-14"},
            "end": {"date": "2026-11-15"},
        }
        items = []
        state = {}

        sync.sync_collection(
            "event", items, [remote], state, object(), "UTC", True,
            ignore_events_before="2026-11-14",
        )

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].date, "2026-11-14")

    def test_local_only_change_updates_google_task(self):
        item = sync.Item(False, "2026-11-14", "", "", "task", "local-1", "New")
        old = {"kind": "task", "title": "Old", "date": "2026-11-14", "done": False}
        remote = {
            "id": "google-1",
            "title": "Old",
            "due": "2026-11-14T00:00:00.000Z",
            "status": "needsAction",
        }
        service = FakeTasksService({
            "id": "google-1",
            "title": "New",
            "due": "2026-11-14T00:00:00.000Z",
            "status": "needsAction",
        })
        state = {
            "items": {
                "local-1": {
                    "kind": "task",
                    "remote_id": "google-1",
                    "last_synced": old,
                    "etag": "etag-old",
                }
            }
        }
        remote["etag"] = "etag-old"

        sync.sync_collection(
            "task", [item], [remote], state, service, "UTC", True
        )

        self.assertEqual(len(service.calls), 1)
        self.assertEqual(service.calls[0][0], "patch")
        self.assertEqual(service.calls[0][1]["body"]["title"], "New")
        assert service.request is not None
        self.assertEqual(service.request.headers["If-Match"], "etag-old")

    def test_two_sided_edit_is_reported_without_overwrite(self):
        item = sync.Item(False, "2026-11-14", "", "", "task", "local-1", "Local")
        baseline = {
            "kind": "task",
            "title": "Before",
            "date": "2026-11-14",
            "done": False,
        }
        remote = {
            "id": "google-1",
            "title": "Google",
            "due": "2026-11-14T00:00:00.000Z",
            "status": "needsAction",
        }
        service = FakeTasksService()
        state = {
            "items": {
                "local-1": {
                    "kind": "task",
                    "remote_id": "google-1",
                    "last_synced": baseline,
                }
            }
        }

        with self.assertLogs(level="WARNING"):
            sync.sync_collection(
                "task", [item], [remote], state, service, "UTC", True
            )

        self.assertEqual(service.calls, [])
        self.assertEqual(item.text, "Local")
        self.assertIn("task:local-1", state["conflicts"])

    def test_google_task_edit_updates_task_date_only(self):
        item = sync.Item(False, "2026-11-14", "", "", "task", "local-1", "Old")
        baseline = {
            "kind": "task",
            "title": "Old",
            "date": "2026-11-14",
            "done": False,
        }
        remote = {
            "id": "google-1",
            "title": "Updated",
            "due": "2026-11-14T00:00:00.000Z",
            "status": "needsAction",
        }
        state = {
            "items": {
                "local-1": {
                    "kind": "task",
                    "remote_id": "google-1",
                    "last_synced": baseline,
                }
            }
        }

        sync.sync_collection(
            "task", [item], [remote], state, FakeTasksService(), "UTC", True
        )

        self.assertEqual(item.text, "Updated")
        self.assertEqual(item.finish, "")

    def test_local_deletion_propagates_to_linked_google_task(self):
        baseline = {
            "kind": "task",
            "title": "Remove",
            "date": "2026-11-14",
            "done": False,
        }
        remote = {
            "id": "google-1",
            "title": "Remove",
            "due": "2026-11-14T00:00:00.000Z",
            "status": "needsAction",
        }
        service = FakeTasksService()
        state = {
            "items": {
                "local-1": {
                    "kind": "task",
                    "remote_id": "google-1",
                    "last_synced": baseline,
                }
            }
        }

        sync.sync_collection(
            "task", [], [remote], state, service, "UTC", True
        )

        self.assertEqual(service.calls[0][0], "delete")
        self.assertNotIn("local-1", state["items"])

    def test_file_change_guard_stops_remote_deletion(self):
        baseline = {
            "kind": "task",
            "title": "Remove",
            "date": "2026-11-14",
            "done": False,
        }
        remote = {
            "id": "google-1",
            "title": "Remove",
            "due": "2026-11-14T00:00:00.000Z",
            "status": "needsAction",
        }
        service = FakeTasksService()
        state = {
            "items": {
                "local-1": {
                    "kind": "task",
                    "remote_id": "google-1",
                    "last_synced": baseline,
                }
            }
        }

        def changed_file():
            raise RuntimeError("tasks.txt changed during sync")

        with self.assertRaisesRegex(RuntimeError, "tasks.txt changed"):
            sync.sync_collection(
                "task", [], [remote], state, service, "UTC", True,
                before_remote_write=changed_file,
            )

        self.assertEqual(service.calls, [])
        self.assertIn("local-1", state["items"])

    def test_tasks_still_sync_when_calendar_rate_limit_fails(self):
        from googleapiclient.errors import HttpError
        from httplib2 import Response

        error = HttpError(Response({"status": "403"}), b"Rate Limit Exceeded")
        remote_task = {
            "id": "google-task",
            "title": "Imported from Google",
            "due": "2026-11-14T00:00:00.000Z",
            "status": "needsAction",
        }
        with tempfile.TemporaryDirectory() as directory:
            tasks_path = Path(directory) / "tasks.txt"
            state_path = Path(directory) / "sync-state.json"
            conflicts_path = Path(directory) / "sync-conflicts.json"
            tasks_path.write_bytes(b"")

            class FakeSettings:
                def get(self, setting):
                    assert setting == "timezone"
                    return FakeRequest({"value": "UTC"})

            class FakeCalendar:
                def settings(self):
                    return FakeSettings()

            patches = (
                patch.object(sync, "TASKS_FILE", tasks_path),
                patch.object(sync, "STATE_FILE", state_path),
                patch.object(sync, "CONFLICTS_FILE", conflicts_path),
                patch.object(sync, "google_services", return_value=(FakeCalendar(), object())),
                patch.object(sync, "list_events", side_effect=error),
                patch.object(sync, "list_tasks", return_value=[remote_task]),
                patch.object(sync, "acquire_lock", return_value=object()),
                patch.object(sync, "release_lock"),
            )
            for active_patch in patches:
                active_patch.start()
                self.addCleanup(active_patch.stop)

            with self.assertLogs(level="ERROR"), patch("builtins.print"):
                sync.sync()

            imported, _ = sync.parse_items(tasks_path)

        self.assertEqual(len(imported), 1)
        self.assertEqual(imported[0].text, "Imported from Google")


if __name__ == "__main__":
    unittest.main()
