# Lab Head UI — Recap чата (2026-06-23)

## Контекст запроса

Пользователь попросил подробно разобрать, как устроен Lab Head UI в репозитории: от входа в браузере до ORM/SQL и HTML-ответа, включая URL-карту, view/service-слой, шаблоны, тесты и сквозные сценарии.

Разбор выполнялся по файлам в заданном порядке:

1. `backend/config/urls.py`
2. `backend/apps/bookings/urls_web.py`
3. `backend/apps/bookings/views/lab_head.py`
4. `backend/apps/bookings/services/lab_head.py`
5. шаблоны `backend/templates/bookings/lab_head/*.html`
6. `backend/apps/bookings/tests/test_lab_head_ui.py`
7. связанные модели/querysets, необходимые для понимания потока

---

## Что было сделано в чате

### 1) Полный архитектурный разбор Lab Head UI

Собрана и объяснена общая картина:

- вход в `config.urls` и подключение `apps.bookings.urls_web`;
- карта всех `lab-head/*` URL;
- роль `LAB_HEAD` и проверка доступа через `LabHeadRequiredMixin`;
- принцип scope-изоляции по `training_center` / `laboratory`;
- цепочка `Browser -> urls -> view -> service -> ORM -> template -> response`.

### 2) Подробный разбор web-слоя

Детально разобраны классы из `views/lab_head.py`:

- домашняя страница и счетчики;
- staff/teacher people-flow;
- bind/unbind дисциплин и лабораторных работ;
- создание/обновление ЛР;
- стенды;
- расписание;
- валидации POST, `messages`, redirects, status flow.

### 3) Подробный разбор service-слоя

Объяснена роль `services/lab_head.py`:

- функции scope-фильтрации;
- `*_in_scope` проверки для object-level доступа;
- поиск по ЛР/стендам через `Q`;
- синхронизация M2M `training_centers` от связей `laboratories`;
- обновление ЛР через `lab_head_update_lab_work`.

### 4) Разбор шаблонов

Разобраны все шаблоны `lab_head`:

- `home.html` — рабочий дашборд;
- `bindings.html` — рабочие формы bind/unbind;
- `lab_works.html` — рабочие модалки create/edit;
- `stands.html` — рабочая форма создания;
- `people.html` и `schedule.html` — сейчас заглушки UI;
- CSRF в POST-формах подтвержден;
- HTMX-атрибуты в этих страницах не используются (классический SSR + JS).

### 5) Разбор тестов

Покрытие `test_lab_head_ui.py` разложено по AAA:

- доступ/роль;
- создание сотрудников;
- bind/unbind дисциплин;
- создание/обновление/снятие публикации ЛР;
- поиск ЛР и стендов;
- создание стенда и записи расписания;
- запрет staff-операций через staff URL в отдельном сценарии.

### 6) End-to-end сценарии

Разобраны сквозные сценарии:

1. `GET /lab-head/`
2. `POST /lab-head/people/create/`
3. `POST /lab-head/bindings/disciplines/<id>/bind/`
4. `POST /lab-head/lab-works/create/`
5. `POST /lab-head/stands/create/`
6. `POST /lab-head/schedule/create/`

Для каждого описаны:

- вызываемый view;
- цепочка сервисов;
- какие данные читаются/пишутся ORM;
- рендер/redirect;
- поведение при ошибках и ограничениях доступа.

### 7) SQL-паспорт и query-trace

Дополнительно составлены:

- SQL-паттерны по ключевым GET/POST endpoint;
- пошаговый trace по ORM и ожидаемым SQL-операциям;
- таблицы и M2M связи, участвующие в Lab Head UI;
- разбор того, как `add/remove/set` маппятся в SQL.

### 8) Оценка структуры проекта

Дана оценка архитектуры репозитория:

- это модульный Django-монолит с доменным разделением (`users`, `academics`, `scheduling`, `bookings`, `integrations`);
- большое количество папок оправдано разделением ответственности;
- сильно “раздувает” дерево наличие `backend/.venv`.

### 9) Практические материалы из чата

Подготовлены рабочие артефакты:

- roadmap “вход в проект за 60 минут”;
- cheat sheet “где что менять”;
- PR-чеклист из 10 пунктов для безопасного ревью изменений;
- набор `EXPLAIN ANALYZE` SQL-шаблонов для диагностики производительности Lab Head UI.

---

## Ключевые выводы по состоянию Lab Head UI

1. **Доступ и scope реализованы централизованно**, в основном через mixin + service/queryset helpers.
2. **Критические CRUD-пути работают** и покрыты тестами.
3. **Часть UI уже функциональна** (`bindings`, `lab_works`, `stands`), часть пока с заглушками (`people`, `schedule` шаблоны).
4. **Главные performance-риски**: поиск с `icontains` + M2M join + `distinct` на больших данных.
5. **Текущая структура проекта зрелая** и типична для production Django.

---

## Использованные в разборе ключевые файлы

- `backend/config/urls.py`
- `backend/apps/bookings/urls_web.py`
- `backend/apps/bookings/views/lab_head.py`
- `backend/apps/bookings/services/lab_head.py`
- `backend/templates/bookings/lab_head/home.html`
- `backend/templates/bookings/lab_head/people.html`
- `backend/templates/bookings/lab_head/bindings.html`
- `backend/templates/bookings/lab_head/lab_works.html`
- `backend/templates/bookings/lab_head/stands.html`
- `backend/templates/bookings/lab_head/schedule.html`
- `backend/apps/bookings/tests/test_lab_head_ui.py`
- `backend/apps/academics/querysets.py`
- `backend/apps/bookings/services/booking.py` (функция `staff_lab_filter`)
- `backend/apps/users/models.py`
- `backend/apps/academics/models.py`
- `backend/apps/scheduling/models.py`
- `backend/templates/base.html`

---

## Примечание

Это **новый** документ-резюме чата, созданный отдельно и не заменяющий существующие файлы документации.

---

## Развернутая часть (детальный конспект обсуждения)

Ниже — расширенная версия, чтобы сохранить не только выводы, но и логику анализа, которую проходили шаг за шагом.

## A. Общая картина Lab Head UI

### A.1 Что делает Lab Head UI

Lab Head UI — это web-кабинет заведующего лабораторией (`LAB_HEAD`) в Django-приложении. Через него управляются:

- сотрудники и преподаватели своей области;
- привязки дисциплин и лабораторных работ к своей лаборатории;
- карточки лабораторных работ;
- лабораторные стенды;
- записи расписания.

UI рендерится на сервере (Django templates), а интерактивность сделана преимущественно через нативный JS/модальные окна. В конкретных `lab_head` шаблонах HTMX-атрибуты не используются, хотя библиотека HTMX подключена глобально в `base.html`.

### A.2 Поток запроса

1. Браузер отправляет HTTP-запрос.
2. `backend/config/urls.py` передает web-пути в `apps.bookings.urls_web`.
3. По `lab-head/*` выбирается соответствующий class-based view.
4. View проходит `LabHeadRequiredMixin` (роль + базовый scope).
5. View вызывает функции `services/lab_head.py` и/или `academics/querysets.py`.
6. ORM строит SQL-запросы к таблицам домена.
7. Возвращается HTML-страница (GET) или redirect+message (POST).

### A.3 Карта ответственности файлов

- `config/urls.py`: корневой роутинг приложения.
- `bookings/urls_web.py`: карта web URL, включая `lab-head/*`.
- `bookings/views/lab_head.py`: контроллерный слой.
- `bookings/services/lab_head.py`: бизнес-проверки и scope-фильтры.
- `templates/bookings/lab_head/*.html`: presentation layer.
- `tests/test_lab_head_ui.py`: интеграционные сценарии.

### A.4 Карта доступа и scope

Ключевые точки:

- `is_lab_head_user(user)` — допускает только роль `LAB_HEAD`.
- `LabHeadRequiredMixin.dispatch` — отсекает anonymous/чужие роли/профили без лабораторного контекста.
- `resolve_staff_training_center` и `resolve_staff_laboratory` (из `academics/querysets.py`) — определяют рабочий scope.
- `lab_head_*_in_scope` функции — объектная проверка для id из URL/POST.

Идея безопасности: заведующий работает только в своей лаборатории / учебном центре.

---

## B. Подробный конспект по файлам

## B.1 `backend/config/urls.py`

Что важно:

- `path("", include("apps.bookings.urls_web"))` подключает все web-маршруты, включая `lab-head/*`.
- `path("login/")` и `path("logout/")` обеспечивают web-аутентификацию, на которую опирается `LoginRequiredMixin`.
- API роуты отделены (`api/v1/*`), это другая плоскость интерфейса.

Роль в общей архитектуре: единая точка входа URL-конфигурации.

## B.2 `backend/apps/bookings/urls_web.py`

Что важно:

- здесь объявлены все `lab-head/*` URL names;
- names используются в шаблонах `{% url '...' %}`;
- методы HTTP определяются не тут, а в самих view-классах.

Список `lab-head` endpoint:

- `lab-head-home`
- `lab-head-people`
- `lab-head-person-create`
- `lab-head-person-bindings`
- `lab-head-bindings`
- `lab-head-discipline-create`
- `lab-head-discipline-bind`
- `lab-head-discipline-unbind`
- `lab-head-lab-work-bind`
- `lab-head-lab-work-unbind`
- `lab-head-lab-works`
- `lab-head-lab-work-create`
- `lab-head-lab-work-update`
- `lab-head-stands`
- `lab-head-stand-create`
- `lab-head-schedule`
- `lab-head-schedule-create`

## B.3 `backend/apps/bookings/views/lab_head.py`

### Миксин доступа

`LabHeadRequiredMixin`:

- проверяет, что пользователь — `LAB_HEAD`;
- проверяет наличие training center в профиле;
- при нарушении — `messages.error` + redirect на `home`.

Это единая “дверь” для всех lab-head страниц.

### Главная страница

`LabHeadHomeView` считает агрегаты через `.count()` и кладет в context:

- число людей;
- число дисциплин;
- число ЛР;
- число стендов;
- число записей расписания.

### Люди

- `LabHeadPeopleView` отдает `people` queryset + контекст для ролей/дисциплин.
- `LabHeadPersonCreateView.post`:
  - читает форму;
  - валидирует обязательные поля/роль/email uniqueness;
  - создает `User`;
  - назначает `profile.training_center`;
  - возвращает success-message + redirect.
- `LabHeadPersonBindingsView.post`:
  - берет сотрудника только из scoped queryset;
  - берет только разрешенные дисциплины;
  - выполняет `profile.disciplines.set(...)`.

### Привязки

`LabHeadBindingsView`:

- загружает дисциплины лаборатории;
- prefetch’ит управляемые ЛР;
- отдельно строит bindable-списки;
- поддерживает текстовый поиск `q`.

POST операции:

- `LabHeadDisciplineBindView` / `UnbindView`
- `LabHeadLabWorkBindView` / `UnbindView`

Все операции сопровождаются сообщением и redirect.

`LabHeadDisciplineCreateView` специально отключен: всегда message error, создание только через админку.

### Лабораторные работы

`LabHeadLabWorksView`:

- возвращает scoped список ЛР;
- делает `select_related/prefetch_related`;
- применяет поисковый фильтр.

`LabHeadLabWorkCreateView.post`:

- проверяет scope дисциплины/лаборатории/аудитории;
- валидирует числа и ограничения;
- проверяет дубликат `(discipline, number)`;
- создает ЛР;
- привязывает лабораторию;
- синхронизирует training centers.

`LabHeadLabWorkUpdateView.post`:

- проверяет доступ к ЛР;
- делегирует в `lab_head_update_lab_work`;
- отрабатывает `ValueError` от сервиса через messages.

### Стенды

- `LabHeadStandsView`: scoped queryset + поиск.
- `LabHeadStandCreateView.post`: проверка room в scope + `LabStand.objects.create(...)`.

### Расписание

- `LabHeadScheduleView`: scoped entries + контекст (ЛР, комнаты, преподаватели, активный семестр, week parity).
- `LabHeadScheduleCreateView.post`:
  - проверяет активный семестр;
  - scope-check по lab_work/room/teacher;
  - парсит weekday/time/capacity/duration;
  - создает `ScheduleEntry`.

## B.4 `backend/apps/bookings/services/lab_head.py`

Ключевая роль: все сложные scope и validation правила вынесены сюда.

Основные группы функций:

1. Идентификация и базовый scope:
   - `is_lab_head_user`
   - `lab_head_training_center`
   - `lab_head_laboratory`
2. Консистентность M2M:
   - `sync_training_centers_for_laboratories`
3. Scoped querysets:
   - `lab_head_people_qs`
   - `lab_head_bindable_disciplines_qs`
   - `lab_head_bindable_lab_works_qs`
   - `lab_head_rooms_qs`, `lab_head_laboratories_qs`, `lab_head_teachers_qs`, `lab_head_schedule_qs`
4. Поиск:
   - `lab_head_lab_work_search_q` / `filter_lab_head_lab_works`
   - `lab_head_stand_search_q` / `filter_lab_head_stands`
5. Object-level проверки:
   - `lab_head_*_in_scope`
6. Update-логика ЛР:
   - `lab_head_update_lab_work` с централизованными проверками.

## B.5 Шаблоны `lab_head`

- `home.html` — рабочая карточка-панель.
- `bindings.html` — полнофункциональная страница привязок с диалогом и POST-формами.
- `lab_works.html` — таблица + модалки create/edit + JS для заполнения edit-формы.
- `stands.html` — таблица + модалка создания стенда.
- `people.html` — временная заглушка.
- `schedule.html` — временная заглушка.

Отдельно подтверждено:

- CSRF-токены присутствуют в POST формах;
- в этих шаблонах нет `hx-get/hx-post` и прочих `hx-*`.

## B.6 `backend/apps/bookings/tests/test_lab_head_ui.py`

Тесты покрывают:

- доступ на дашборд по роли;
- создание сотрудника;
- привязки дисциплин сотруднику;
- bind/unbind дисциплин к лаборатории;
- create/update/unpublish для ЛР;
- поиск по ЛР и стендам;
- создание стенда;
- создание записи расписания;
- запрет staff-сценария на управление стендами через staff URL.

Практический смысл: тесты выступают как “контракт” поведения UI.

---

## C. Сквозные сценарии (E2E, обсужденные в чате)

## C.1 `GET /lab-head/`

Путь:

`urls_web -> LabHeadHomeView -> scope/queryset counts -> home.html`.

Результат:

- HTML с карточками и счетчиками.

Ошибки/доступ:

- anonymous/чужая роль/нет scope — redirect.

## C.2 `POST /lab-head/people/create/`

Путь:

`LabHeadPersonCreateView.post -> validation -> User.create_user -> profile update -> redirect`.

Результат:

- сотрудник/преподаватель создан в правильном training center.

## C.3 `POST /lab-head/bindings/disciplines/<id>/bind/`

Путь:

`DisciplineBindView -> get bindable discipline -> m2m add(lab) -> sync training centers -> redirect`.

## C.4 `POST /lab-head/lab-works/create/`

Путь:

`CreateView -> scope checks -> duplicate check -> create LabWork -> set laboratory -> sync tc -> redirect`.

## C.5 `POST /lab-head/stands/create/`

Путь:

`StandCreateView -> room in scope -> create stand -> redirect`.

## C.6 `POST /lab-head/schedule/create/`

Путь:

`ScheduleCreateView -> active semester -> scope checks -> parse time/day -> create ScheduleEntry -> redirect`.

---

## D. SQL/ORM слой — расширенный конспект

Обсуждены:

- SQL-паттерны для ключевых GET и POST endpoint;
- trace уровня “какой ORM-вызов, зачем, что читает/пишет”;
- таблицы и M2M, которые реально участвуют в Lab Head UI.

Ключевые таблицы:

- `users_user`, `users_userprofile`
- `academics_semester`, `academics_discipline`, `academics_labwork`
- `scheduling_trainingcenter`, `scheduling_laboratory`, `scheduling_room`, `scheduling_labstand`, `scheduling_scheduleentry`
- M2M: `*_laboratories`, `*_training_centers`, `users_userprofile_disciplines`

Разобрано поведение:

- `add` -> `INSERT` в m2m
- `remove` -> `DELETE`
- `set` -> replace (delete/insert pattern)

---

## E. Производительность и индексы — расширенный конспект

Обсуждение включало:

1. Где вероятны узкие места:
   - `icontains` поиск по тексту;
   - join’ы по M2M + `distinct`;
   - тяжелые списковые страницы (`lab_works`, `bindings`).
2. Что уже покрыто:
   - FK и unique constraints дают базовые индексы.
3. Что диагностировать:
   - `EXPLAIN (ANALYZE, BUFFERS)` на основных endpoint.
4. Что подготовлено:
   - шаблоны SQL-запросов для план-анализа;
   - критерии red flags в execution plans.

---

## F. Практические артефакты, подготовленные в ходе диалога

1. Конспект архитектуры Lab Head UI.
2. Карта URL и flow запроса.
3. Пошаговые E2E-сценарии.
4. SQL-паспорт endpoint’ов.
5. Query-trace по 6 сценариям.
6. DB/M2M карта для ревью миграций и связей.
7. Индекс-аудит (качественный, по текущему коду).
8. Набор SQL для `EXPLAIN ANALYZE`.
9. “Вход в проект за 60 минут”.
10. Cheat sheet “где что менять”.
11. PR-чеклист из 10 пунктов.

---

## G. Отдельные наблюдения по зрелости кода

1. Проект выглядит как зрелый Django-монолит с модульной декомпозицией.
2. Важные правила доступа вынесены в queryset/service слой.
3. Тесты покрывают основные UI-сценарии Lab Head.
4. Есть разрыв между backend и UI для разделов `people`/`schedule` (view функциональны, шаблоны пока заглушки).
5. Наличие `.venv` внутри `backend` заметно увеличивает объем дерева файлов.

---

## H. Итог

Диалог покрыл полный цикл понимания Lab Head UI:

- от роутинга и role gate
- до конкретных ORM-паттернов и проверок индексов
- плюс практические инструменты для ревью и сопровождения.

Этот документ расширен специально, чтобы быть не коротким summary, а полноценной технической записью обсуждения.
