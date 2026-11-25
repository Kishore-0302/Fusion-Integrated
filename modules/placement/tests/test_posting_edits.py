"""Editing a posting (PC-BR-002, PC-BR-003, PC-BR-004) and what publishing freezes."""
from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from conftest import make_principal, make_session
from core.api.exceptions import ConflictError
from modules.placement.models import Company, JobPosting
from modules.placement.services import postings

pytestmark = pytest.mark.django_db

MANAGE = "placement_cell.job_posting.manage"
BROKEN_RULE = {"approx": ["cpi", 7]}


@pytest.fixture
def company():
    return Company.objects.create(name="Acme", slug="acme", status="active",
                                  approval_status="approved", approved_by_user_id=9)


@pytest.fixture
def staff():
    return make_principal(user_id=9, kind="staff", permissions=(MANAGE,))


def _draft(company, **kw):
    fields = {"company": company, "title": "SDE-1", "placement_year": "2026-27",
              "description": "Build things.", "status": "draft",
              "closes_at": timezone.now() + timedelta(days=7),
              "eligibility_rule": {"gte": ["cpi", 7.0]}, "created_by_user_id": 9}
    fields.update(kw)
    return JobPosting.objects.create(**fields)


def _published(company, staff, **kw):
    return postings.publish(posting_id=_draft(company, **kw).pk, actor=staff)


def _code(call):
    with pytest.raises(ConflictError) as exc:
        call()
    return exc.value.code


# -- A broken rule never goes live -------------------------------------------------
def test_a_sound_rule_is_saved(company, staff):
    rule = {"all": [{"gte": ["cpi", 7.5]}, {"in": ["discipline", ["CSE"]]}]}
    posting = postings.update(posting_id=_draft(company).pk, actor=staff,
                              eligibility_rule=rule)
    assert posting.eligibility_rule == rule


def test_an_unknown_operator_is_refused_when_saved(company, staff):
    posting = _draft(company)
    code = _code(lambda: postings.update(posting_id=posting.pk, actor=staff,
                                         eligibility_rule=BROKEN_RULE))
    assert code == "invalid_eligibility_rule"
    posting.refresh_from_db()
    assert posting.eligibility_rule == {"gte": ["cpi", 7.0]}


def test_a_wrongly_typed_value_is_refused_when_created(company, staff):
    code = _code(lambda: postings.create(
        company_id=company.pk, placement_year="2026-27", actor=staff, title="X",
        eligibility_rule={"gte": ["cpi", "seven"]}))
    assert code == "invalid_eligibility_rule"
    assert not JobPosting.objects.filter(title="X").exists()


def test_a_broken_rule_already_stored_cannot_be_published(company, staff):
    posting = _draft(company, eligibility_rule=BROKEN_RULE)
    code = _code(lambda: postings.publish(posting_id=posting.pk, actor=staff))
    assert code == "invalid_eligibility_rule"
    posting.refresh_from_db()
    assert (posting.status, posting.published_at) == ("draft", None)


def test_a_sound_rule_is_published(company, staff):
    assert _published(company, staff).status == "published"


# -- What publishing freezes ----------------------------------------------------
def test_a_published_posting_keeps_its_type(company, staff):
    posting = _published(company, staff)
    code = _code(lambda: postings.update(posting_id=posting.pk, actor=staff,
                                         kind="internship"))
    assert code == "posting_kind_locked"
    posting.refresh_from_db()
    assert posting.kind == "fte"


def test_sending_the_same_type_again_is_not_a_change(company, staff):
    posting = _published(company, staff)
    postings.update(posting_id=posting.pk, actor=staff, kind="fte", seats=3)
    posting.refresh_from_db()
    assert (posting.kind, posting.seats) == ("fte", 3)


def test_a_draft_may_change_its_type(company, staff):
    posting = postings.update(posting_id=_draft(company).pk, actor=staff,
                              kind="internship")
    assert posting.kind == "internship"


def test_a_published_deadline_cannot_move_earlier(company, staff):
    posting = _published(company, staff)
    before = posting.closes_at
    code = _code(lambda: postings.update(posting_id=posting.pk, actor=staff,
                                         closes_at=before - timedelta(hours=1)))
    assert code == "deadline_cannot_shorten"
    posting.refresh_from_db()
    assert posting.closes_at == before


def test_a_published_deadline_cannot_be_removed(company, staff):
    posting = _published(company, staff)
    code = _code(lambda: postings.update(posting_id=posting.pk, actor=staff,
                                         closes_at=None))
    assert code == "deadline_cannot_shorten"


def test_a_published_deadline_can_be_extended(company, staff):
    posting = _published(company, staff)
    later = posting.closes_at + timedelta(days=2)
    assert postings.update(posting_id=posting.pk, actor=staff,
                           closes_at=later).closes_at == later


def test_a_closed_posting_keeps_the_same_locks(company, staff):
    posting = _published(company, staff)
    postings.close(posting_id=posting.pk, actor=staff)
    code = _code(lambda: postings.update(posting_id=posting.pk, actor=staff,
                                         kind="ppo"))
    assert code == "posting_kind_locked"


def test_a_draft_deadline_can_move_earlier(company, staff):
    posting = _draft(company)
    earlier = posting.closes_at - timedelta(days=1)
    assert postings.update(posting_id=posting.pk, actor=staff,
                           closes_at=earlier).closes_at == earlier


def test_informational_fields_stay_editable_after_publish(company, staff):
    posting = _published(company, staff)
    postings.update(posting_id=posting.pk, actor=staff, seats=12,
                    location="Jabalpur", description="Updated role.")
    posting.refresh_from_db()
    assert (posting.seats, posting.location, posting.description) == (
        12, "Jabalpur", "Updated role.")


# -- The same refusals over HTTP ------------------------------------------------
@pytest.fixture
def api(stub_iam):
    stub_iam(make_session(user_id=9, kind="staff", roles=("tpo",), active_role="tpo",
                          modules=("placement_cell",), permissions=(MANAGE,)))
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION="Token abc")
    return client


def _patch(api, posting, body):
    return api.patch(f"/api/v1/placement/postings/{posting.pk}", body, format="json")


def test_api_refuses_a_broken_rule(api, company):
    resp = _patch(api, _draft(company), {"eligibility_rule": BROKEN_RULE})
    assert resp.status_code == 409
    error = resp.json()["error"]
    assert error["code"] == "invalid_eligibility_rule"
    assert error["details"] == [{"path": "rule", "field": "cpi",
                                 "reason": "unknown_operator"}]


def test_api_refuses_publishing_a_broken_rule(api, company):
    posting = _draft(company, eligibility_rule=BROKEN_RULE)
    resp = api.post(f"/api/v1/placement/postings/{posting.pk}/publish")
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "invalid_eligibility_rule"


def test_api_refuses_changing_a_published_type(api, company, staff):
    resp = _patch(api, _published(company, staff), {"kind": "internship"})
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "posting_kind_locked"


def test_api_refuses_bringing_a_published_deadline_forward(api, company, staff):
    posting = _published(company, staff)
    earlier = (posting.closes_at - timedelta(hours=2)).isoformat()
    resp = _patch(api, posting, {"closes_at": earlier})
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "deadline_cannot_shorten"


def test_api_extends_a_published_deadline(api, company, staff):
    posting = _published(company, staff)
    later = posting.closes_at + timedelta(days=3)
    resp = _patch(api, posting, {"closes_at": later.isoformat()})
    assert resp.status_code == 200
    posting.refresh_from_db()
    assert posting.closes_at == later


def test_a_posting_without_a_description_cannot_be_published(company, staff):
    """PC-BR-003: role description is required."""
    posting = JobPosting.objects.create(
        company=company, title="SDE-1", placement_year="2026-27",
        description="",  # empty
        status="draft",
        closes_at=timezone.now() + timedelta(days=7),
        eligibility_rule={"gte": ["cpi", 7.0]},
        created_by_user_id=9,
    )
    code = _code(lambda: postings.publish(posting_id=posting.pk, actor=staff))
    assert code == "incomplete_posting"


def test_company_submits_then_tpo_publishes(company, staff):
    """BW-PC-03: Company submits opportunity, TPO publishes it."""
    from types import SimpleNamespace

    from modules.placement.models import RecruiterAccount

    acct = RecruiterAccount.objects.create(
        company=company,
        email="recruiter@acme.example.com",
        full_name="Recruiter",
    )
    recruiter_actor = SimpleNamespace(
        user_id=None,
        username="recruiter",
        display_name="Recruiter",
        kind="recruiter",
        active_role=None,
        roles=(),
        permissions=frozenset((MANAGE,)),
        modules=(),
        is_authenticated=True,
        is_anonymous=False,
        account_id=acct.pk,
    )
    draft = postings.create(
        company_id=company.pk,
        placement_year="2026-27",
        actor=recruiter_actor,
        title="Recruiter Draft",
        description="Role details here.",
        eligibility_rule={"gte": ["cpi", 7.0]},
        closes_at=timezone.now() + timedelta(days=7),
    )
    assert draft.status == "draft"
    published = postings.publish(posting_id=draft.pk, actor=staff)
    assert published.status == "published"

