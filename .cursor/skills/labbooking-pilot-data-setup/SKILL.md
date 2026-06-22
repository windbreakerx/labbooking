# labbooking-pilot-data-setup

Use this skill when preparing pilot data, refreshing seed data, loading CSV files, checking acceptance visibility, or rehearsing the pilot with test accounts.

## Pilot Scope

- 1 laboratory / training center for the first launch.
- Real or approved pilot groups, disciplines, lab works, rooms, staff, teachers, students, and schedule for at least two weeks.
- CSV and local accounts are the pilot path; SSO and live Dekanat API are post-pilot.

## Data Checklist

- Active `Semester` exists.
- `StudentGroup` rows exist and students point to `student_group`.
- Groups are linked to the correct disciplines and optional lab works.
- Disciplines and lab works are linked to the pilot `TrainingCenter`.
- Staff, teachers, and lab head have `profile.training_center`.
- Sessions exist for visible lab works and rooms.
- A holiday row exists for negative testing.

## Commands

```bash
cd backend
python manage.py seed_demo --weeks 2
pytest apps/bookings/tests/test_pilot_visibility.py -v
```

For CSV refresh, follow `docs/PILOT_DATA_SETUP.md` and run imports in the documented order.

## Acceptance Accounts

Use the accounts documented in `docs/PILOT_DATA_SETUP.md` after `seed_demo`. Confirm each role can complete its manual scenario before exposing the pilot to real students.
