import pytest
from django.test import override_settings

from apps.bookings.patch_notes import PATCH_NOTES


@pytest.mark.django_db
@override_settings(PATCH_NOTES_ENABLED=True)
def test_patch_notes_page_for_student(client, student):
    client.force_login(student)
    response = client.get("/patch-notes/")
    assert response.status_code == 200
    content = response.content.decode()
    assert "Что нового в системе" in content
    assert f"v{PATCH_NOTES[0]['version']}" in content


@pytest.mark.django_db
@override_settings(PATCH_NOTES_ENABLED=True)
def test_patch_notes_nav_visible_for_staff(client, staff):
    client.force_login(staff)
    response = client.get("/")
    content = response.content.decode()
    assert "Что нового" in content
    assert 'href="/patch-notes/"' in content


@pytest.mark.django_db
@override_settings(PATCH_NOTES_ENABLED=False)
def test_patch_notes_hidden_when_disabled(client, student):
    client.force_login(student)
    home = client.get("/")
    assert "Что нового" not in home.content.decode()
    response = client.get("/patch-notes/")
    assert response.status_code == 404
