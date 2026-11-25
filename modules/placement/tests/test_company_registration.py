"""PC-UC-014: every company registration gets its own slug, even when two race for one."""
import threading

import pytest
from django.conf import settings
from django.db import IntegrityError, connection

from core.api.exceptions import ConflictError
from modules.placement.models import Company
from modules.placement.services import companies

_using_sqlite = settings.DATABASES["default"]["ENGINE"] == "django.db.backends.sqlite3"


@pytest.mark.django_db
def test_pc_uc_014_registering_a_name_twice_gives_each_its_own_slug():
    first = companies.register(name="Acme Corp")
    second = companies.register(name="Acme Corp")
    assert (first.slug, second.slug) == ("acme-corp", "acme-corp-2")


@pytest.mark.skipif(_using_sqlite, reason="SQLite :memory: cannot handle concurrent transactions — requires PostgreSQL")
@pytest.mark.django_db(transaction=True)
def test_pc_uc_014_two_registrations_racing_for_one_slug_both_succeed(monkeypatch):
    # Hold both threads after they choose a slug, so both choose before either inserts.
    both_chose = threading.Barrier(2, timeout=10)
    chose_once = threading.local()
    choose = companies._unique_slug

    def choose_then_wait(name):
        slug = choose(name)
        if not getattr(chose_once, "done", False):
            chose_once.done = True
            both_chose.wait()
        return slug

    monkeypatch.setattr(companies, "_unique_slug", choose_then_wait)
    slugs, failures = [], []

    def register():
        try:
            slugs.append(companies.register(name="Acme Corp").slug)
        except (IntegrityError, ConflictError) as exc:
            failures.append(exc)
        finally:
            connection.close()

    threads = [threading.Thread(target=register) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert failures == []
    assert sorted(slugs) == ["acme-corp", "acme-corp-2"]
    assert Company.objects.filter(name="Acme Corp").count() == 2


@pytest.mark.django_db
def test_pc_uc_014_a_slug_that_keeps_clashing_is_refused_with_409(monkeypatch):
    Company.objects.create(name="Acme Corp", slug="acme-corp", status="prospect")
    monkeypatch.setattr(companies, "_unique_slug", lambda name: "acme-corp")

    with pytest.raises(ConflictError) as raised:
        companies.register(name="Acme Corp")

    assert raised.value.code == "company_slug_contention"
    assert raised.value.status_code == 409
    assert Company.objects.filter(name="Acme Corp").count() == 1
