---
name: labbooking-dekanat-csv
description: Manages Dekanat CSV import and pilot data templates for labbooking before live API integration. Use when changing CSV templates, import_dekanat_csv, curriculum bindings, lab bindings, or pilot user import docs.
---

# labbooking-dekanat-csv

Use this skill when changing CSV templates, pilot imports, `import_dekanat_csv`, generated pilot users, curriculum bindings, lab bindings, or documentation about Dekanat data before the real API exists.

## Import Order

```bash
cd backend
python manage.py migrate
python manage.py seed_demo --weeks 2
python manage.py import_dekanat_csv ../docs/csv_templates/pilot_groups.csv --type=groups
python manage.py import_dekanat_csv ../docs/csv_templates/pilot_disciplines.csv --type=disciplines --semester "Пилот 2026/2027 (нефтегаз)"
python manage.py import_dekanat_csv ../docs/csv_templates/pilot_lab_bindings.csv --type=lab_bindings
python manage.py import_dekanat_csv ../docs/csv_templates/pilot_curriculum.csv --type=curriculum
python manage.py import_dekanat_csv ../docs/csv_templates/pilot_staff.csv --type=staff
python manage.py import_dekanat_csv ../docs/csv_templates/pilot_teachers.csv --type=teachers
python manage.py import_dekanat_csv ../docs/csv_templates/pilot_staff_bindings.csv --type=staff_bindings
python manage.py import_dekanat_csv ../docs/csv_templates/pilot_students.csv --type=students
```

## Checklist

- Back up production data before imports.
- Confirm CSV encoding and delimiter.
- Avoid real personal data in committed templates.
- Be explicit about generated emails and default passwords.
- Remember that live Dekanat API and SSO are post-pilot.

## Test Gate

```bash
cd backend
pytest apps/bookings/tests/test_pilot_visibility.py -v
```

Add management-command tests when changing parser behavior, password behavior, or CSV schema.
