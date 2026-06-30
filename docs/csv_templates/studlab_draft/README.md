# Studlab draft (normalized)

Нормализованные таблицы для ручной проверки. Исходный дамп парсера — в `_raw/`.

## Порядок проверки

1. `01_faculties.csv` — справочник факультетов
2. `02_training_centers.csv` — УЦ (дедуп по номеру)
3. `03_departments.csv` — кафедры, собранные из подсказок
4. `04_laboratories.csv` — лаборатории
5. `05_rooms.csv` — аудитории (сортировка: факультет → УЦ → номер)
6. `06_staff.csv` — сотрудники (руководитель первым в группе лаборатории)

## Колонки для ревью

- `check_ok` — поставьте `1` / `да`, когда строка проверена
- `review_comment` — замечания и правки

## Эвристики (проверить вручную)

- `department_code_suggested` для НГФ — по ключевым словам в названии аудитории
- `role_suggested` — LAB_HEAD / LAB_ADMIN
- `phone` и `internal_phone` разделены из строки вида `8 (812) ... (14-83)`

## Перегенерация

```bash
python scripts/scrape_studlab.py
python scripts/normalize_studlab_draft.py
```
