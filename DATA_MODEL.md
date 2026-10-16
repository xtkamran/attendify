# Data Model

MongoDB database (default name `attendance`) with three collections:
`employees`, `attendance`, and `audit_logs`. All timestamps are stored as
timezone-aware **UTC** `Date` values. The Motor client is created with
`tz_aware=True`, so datetimes come back aware on read.

---

## Collection: `employees`

The workforce master data. One document per employee.

| Field | Type | Notes |
|---|---|---|
| `_id` | ObjectId | Mongo primary key |
| `employee_id` | string | Business key, **unique** (e.g. `E001`) |
| `name` | string | Display name (snapshotted onto attendance) |
| `email` | string | Contact |
| `department` | string | Used by department analytics (snapshotted onto attendance) |
| `shift_start` | string `"HH:MM"` | Expected start; drives lateness |
| `shift_end` | string `"HH:MM"` | Expected end |
| `created_at` | Date (UTC) | Creation time |

```json
{
  "_id": "6700...",
  "employee_id": "E001",
  "name": "Asha Rao",
  "email": "asha.rao@example.com",
  "department": "Engineering",
  "shift_start": "09:00",
  "shift_end": "18:00",
  "created_at": "2026-10-09T06:00:00Z"
}
```

**Indexes**
- `employee_id` — **unique**.

---

## Collection: `attendance`

One document per work **session** (one punch-in, optionally one punch-out).
A session with no `punch_out` yet is `status: "open"`.

| Field | Type | Notes |
|---|---|---|
| `_id` | ObjectId | Record id (used in correction / audit URLs) |
| `employee_id` | string | FK → `employees.employee_id` |
| `employee_name` | string | **Snapshot** of name at punch-in time |
| `department` | string | **Snapshot** of department at punch-in time |
| `punch_in` | Date (UTC) | Session start |
| `punch_out` | Date (UTC) \| null | Session end; `null` while open |
| `worked_minutes` | int \| null | Computed at punch-out; `null` while open |
| `status` | `"open"` \| `"closed"` | Lifecycle |
| `is_late` | bool | Punch-in later than `shift_start + grace` |
| `late_by_minutes` | int | Minutes past `shift_start` (0 if not late) |
| `flags` | string[] | Review flags: `long_session`, `short_session`, `overnight` |
| `source` | string | `web` / `mobile` / `biometric` / `system` / `correction` |
| `note` | string \| null | Optional free text |
| `is_corrected` | bool | True once any manual correction applied |
| `correction_count` | int | Number of corrections applied |
| `created_at` | Date (UTC) | Insert time |
| `updated_at` | Date (UTC) | Last mutation time |

```json
{
  "_id": "6701...",
  "employee_id": "E001",
  "employee_name": "Asha Rao",
  "department": "Engineering",
  "punch_in": "2026-10-06T09:40:00Z",
  "punch_out": "2026-10-06T20:30:00Z",
  "worked_minutes": 650,
  "status": "closed",
  "is_late": true,
  "late_by_minutes": 40,
  "flags": [],
  "source": "biometric",
  "note": null,
  "is_corrected": false,
  "correction_count": 0,
  "created_at": "2026-10-06T09:40:00Z",
  "updated_at": "2026-10-06T20:30:00Z"
}
```

**Indexes**
- `(employee_id, punch_in desc)` — list/history queries and range scans.
- `status` — status filters.
- `(employee_id, status)` **unique, partial** on `{status: "open"}` —
  **guarantees at most one open session per employee at the database level**,
  even under concurrent requests. This is the core integrity invariant.

### Why snapshot `employee_name` / `department` onto the session?

Attendance is a historical ledger. If someone transfers from Sales to
Engineering, last month's hours should still be attributed to **Sales**. Storing
the department as it was at punch-in keeps analytics historically correct and
lets the common pipelines group with a plain `$group` (no `$lookup` / join on
every query). The authoritative current value always lives on `employees`.

---

## Collection: `audit_logs`

Append-only trail of manual corrections. Never updated or deleted.

| Field | Type | Notes |
|---|---|---|
| `_id` | ObjectId | |
| `entity_type` | string | `"attendance"` |
| `entity_id` | string | The corrected `attendance._id` (as string) |
| `employee_id` | string | Denormalised for easy per-employee audit queries |
| `action` | string | `"correction"` |
| `changes` | object[] | `[{ field, old, new }]` — one entry per changed field |
| `reason` | string | Mandatory justification |
| `performed_by` | string | Actor id/name |
| `performed_at` | Date (UTC) | When applied |

```json
{
  "_id": "6702...",
  "entity_type": "attendance",
  "entity_id": "6701...",
  "employee_id": "E001",
  "action": "correction",
  "changes": [
    { "field": "punch_in", "old": "2026-10-06T09:40:00Z", "new": "2026-10-06T09:00:00Z" }
  ],
  "reason": "employee forgot to punch in",
  "performed_by": "hr.admin",
  "performed_at": "2026-10-07T04:30:00Z"
}
```

**Indexes**
- `(entity_id, performed_at desc)` — audit trail for a record.
- `(employee_id, performed_at desc)` — all corrections for an employee.

---

## Relationships

```
employees (1) ────< (many) attendance ────< (many) audit_logs
          employee_id                 entity_id
```

- `attendance.employee_id` → `employees.employee_id` (validated at punch-in).
- `audit_logs.entity_id` → `attendance._id` (one trail per record).

## Derived fields — single source of truth

`worked_minutes`, `is_late`, `late_by_minutes`, and `flags` are **computed by
`app/rules.py`** at write time (punch-out and correction) and stored on the
document. They are deliberately denormalised so analytics stay index-friendly
and cheap; the pure functions that produce them are unit-tested in isolation and
reused by the seed script, guaranteeing consistency between seeded and
live-written data.
