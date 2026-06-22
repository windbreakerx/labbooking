# labbooking-access-scope

Use this skill when changing users, roles, groups, laboratories, disciplines, lab works, sessions, support tickets, staff pages, lab-head pages, or API querysets.

## Scope Model

- Students are scoped by `UserProfile.student_group` and `StudentGroup.disciplines` / `StudentGroup.lab_works`.
- Staff, teachers, and lab heads are scoped by `UserProfile.training_center`.
- `SYS_ADMIN` may see all data where explicitly intended.
- `UserProfile.disciplines` is pilot metadata for lab-head assignment; it is not a security boundary unless a dedicated feature changes that contract.

## Checklist

- Use helpers from `backend/apps/academics/querysets.py` for discipline and lab-work visibility.
- Use `staff_lab_filter` / `staff_can_access_scoped_object` for operational objects.
- Check both list endpoints and object-level access by direct URL/API id.
- Verify staff with no `training_center` sees empty staff data.
- Verify student without a resolved `StudentGroup` sees no disciplines or lab works.

## Commands

```bash
cd backend
pytest apps/bookings/tests/test_student_scope.py -v
pytest apps/bookings/tests/test_staff_scope.py -v
pytest apps/bookings/tests/test_pilot_visibility.py -v
```

## Review Questions

- Can a student see a discipline outside their group curriculum?
- Can staff see bookings, sessions, people, stands, support tickets, or reports from another lab?
- Does a direct foreign id return 403/404 instead of leaking data?
