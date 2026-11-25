# Placement Cell — specification audit

The Placement module measured against the PCMS specification set **v1.3 FINAL**
(`Fusion/17-Placement Cell/`). Every finding below was checked against the code,
not inferred from a citation: a comment naming a rule proves only that somebody
typed its id.

## What the specification contains

| Artefact | Active | Retired by the spec |
|---|---|---|
| Business rules | **26** | 4 — `PC-BR-008`, `018`, `027`, `028` |
| Use cases | **22** | 2 — `PC-UC-018`, `019` |
| Workflows | 8 basis + 4 composite | legacy `PC-WF-001` … `008` |
| Requirements | 19 consolidated (CFR), 64 atomic (AFR) | — |

The retirements are deliberate and explained in the documents. Two of the retired
rules still describe behaviour the module must have — they were retired because
they duplicate a requirement, not because the behaviour was dropped:

- `PC-BR-008` application history → now **PC-AFR-009**
- `PC-BR-018` announcement history → now **PC-AFR-043**
- `PC-UC-018` role-scoped access → now cross-cutting, **PC-BR-022** / **PC-AFR-061**

The traceability matrix's mapping columns (`Mapped UC(s)`, `Mapped BR(s)`) are
empty in the file, so requirement coverage below was established by reading
each requirement, not by trusting the matrix.

**Audit freshness:** this document began as an audit of the pre-Assignment-9
implementation. The G3/G4 status and remaining open decisions below have been
rechecked against the current implementation. The numeric summary and older
traceability inventory have not been recomputed after the imported changes and
must not be read as current coverage totals.

## Summary

| | Implemented | Partial | Missing | Deviation |
|---|---|---|---|---|
| Business rules (26) | 24 | 1 (`029`) | 1 (`019`) | — |
| Use cases (22) | 18 | 2 (`010`, `024`) | 1 (`017`) | 1 (`014`) |
| Requirements (64) | 55 | 5 | 3 | 1 (`044`) |

**Traceability is weaker than the implementation.** 6 rules and 5 use cases are
built but never cited; 2 use-case ids are cited for the wrong thing; 24 citations
point at retired ids; and no code cites a v1.3 workflow at all.

---

## 1. Genuine gaps — work to do

### G1. Alumni cannot reach the module at all
`PC-UC-017`, `PC-BR-019`, `PC-AFR-058`, `PC-AFR-059` · **missing**

`selectors/scoping.py` handles an `alumni` role carefully — a read-only slice,
and exclusion from every active workflow object. But nothing lets an alumnus in:
the placement registry grants the module to no alumni role, and the identity
service has no alumni kind. The scoping code is correct and unreachable.

`PC-BR-020` / `PC-AFR-060` (alumni kept *out* of active workflows) is satisfied,
but only trivially, because no alumnus can arrive to be kept out.

Needs a decision before code: how an alumnus is identified (an IAM kind, a
designation, or graduated students by batch), and what the mentorship slice
actually shows.

### G2. A company cannot register itself
`PC-UC-014`, `PC-AFR-044` · **deviation**

The spec's actor is the Company/Recruiter, submitting its own registration for
institute approval. In the code, `services/companies.py::register` requires the
TPO's `manage` permission, and recruiters arrive only by TPO invitation. The
approval gate (`PC-BR-007`, `PC-AFR-045`) is sound; what is missing is the
company-initiated front door.

This may be the right call for the institute — an open registration form is an
abuse surface — but it departs from the document and should be decided, not
inherited.

### G3. TPO placement-record updates are implemented
`PC-BR-029`, `PC-AFR-031`, `PC-AFR-032` · **implemented in current code; citation audit remains**

`services/clearance.py::update_record` permits a TPO with
`placement_cell.record.manage` to update the allowed placement-record fields
(`ctc_lpa`, `kind`, and `is_active`). The API exposes the update operation, and
`tests/test_clearance.py::test_tpo_can_update_student_and_alumni_placement_record`
covers student and alumni records. This closes the record-update gap described
in the original audit. It does not grant alumni write access.

### G4. Cross-season reporting exists; historical student selection is partial
`PC-AFR-034`, `PC-AFR-035`, `PC-AFR-036`, `PC-AFR-016` · **partial**

`services/stats.py` now provides company participation and employment trends
across configured seasons, plus salary distribution reporting and per-season
figures. `api/views.py` exposes the report endpoints. The reports page still
calls `useStats()` without a season argument and has no season selector, so
students cannot select historical statistics through that UI (`PC-AFR-016`).
This leaves the historical-student-view requirement partial even though the
backend accepts a season parameter.

---

## 2. Implemented, but nothing points at it

Traceability only — the behaviour is there.

| Id | What it is | Where it actually lives |
|---|---|---|
| `PC-BR-005` | TPO posting authority | `services/postings.py` — writes require `manage` |
| `PC-BR-022` | Role-restricted access | module grant + permission codes + `selectors/scoping.py` |
| `PC-BR-024` | Sensitive-data modify restriction | `services/authz.py::require` on every write path |
| `PC-BR-025` | Academic master data stays external | CPI read from the IAM projection, never computed here |
| `PC-BR-026` | Auth / RBAC stays external | `fusion_auth` + the identity service |
| `PC-BR-030` | No external selection decisions | outcomes are recorded from TPO or company actions only |
| `PC-UC-004` | Student tracks status | application history, offers, placement records |
| `PC-UC-007` | Automated notifications | notification outbox; all seven events in `PC-AFR-050`–`056` |
| `PC-UC-021` | Company schedules an interview | `services/interviews.py` admits recruiters |
| `PC-UC-022` | Company extends an offer | `services/offers.py` admits recruiters |
| `PC-UC-023` | Resume from profile | **deviation** — the resume is maintained on the ERP portal, see §6 |
| `PC-UC-024` | Student statistics | `services/stats.py::student_view`, cited only as `PC-BR-016` — **partial**: past seasons unreachable from the UI, see G4 |

All seven notification events were confirmed individually: posting published,
application submitted, shortlisted, rejected, interview scheduled, offer issued,
announcement published.

All six states in `PC-AFR-010` exist: submitted, shortlisted, interview
scheduled, offer issued, offer accepted, offer declined.

## 3. Citations that point at the wrong thing

The code was written against an earlier use-case numbering.

| Cited as | Means in v1.3 | Should be | Sites |
|---|---|---|---|
| `PC-UC-002` | Browse opportunities | `PC-UC-023` resume | resolved — those sites were deleted with the profile, see §6 |
| `PC-UC-016` | Company shortlists | `PC-UC-022` extend offer | 1 — `services/offers.py` |

Meanwhile the real `PC-UC-016` (company shortlisting) is implemented as the
review transitions in `domain/state_machine.py`, which admit both the TPO and the
owning company — and cite neither.

## 4. Citations to retired ids

| Retired id | Sites | Repoint to |
|---|---|---|
| `PC-BR-008` | 7 — audit trail model, API, serializer, test, client drawer and hooks | `PC-AFR-009` |
| `PC-BR-018` | 3 — announcement model, service, scoping | `PC-AFR-043` |
| `PC-UC-018` | 1 — `selectors/scoping.py` | `PC-BR-022` |
| `PC-WF-001` … `008` | 13 | the matching `BW-PC-nn` / `CW-PC-nn` |

No code cites a v1.3 basis or composite workflow.

---

## 5. Confirmed implemented

Checked against the code, not just the citation.

| Id | Rule | Evidence |
|---|---|---|
| `PC-BR-001` | Profile completeness before applying | answered by the ERP portal's `profile_completed`, enforced in `services/applications.py` — see §6 |
| `PC-BR-002` | Eligibility before applying | `domain/eligibility.py`; criteria frozen on publish |
| `PC-BR-003` | Posting content required | model constraint plus a data migration |
| `PC-BR-004` | Eligibility vocabulary | closed vocabulary — an unknown field denies |
| `PC-BR-006` | Company posting authority | `services/postings.py` |
| `PC-BR-007` | Company approval gate | `approval_status`, `can_operate` |
| `PC-BR-009` | Company sees only its own applications | `selectors/scoping.py` |
| `PC-BR-010` | TPO manages applications | review transitions in `domain/state_machine.py` |
| `PC-BR-011` | Interview date, slot, mode | required fields on `InterviewRound` |
| `PC-BR-012` | Interview notification | `services/interviews.py` enqueues on adding candidates |
| `PC-BR-013` | Offer response deadline | expiry task on a five-minute beat |
| `PC-BR-014` | Record written on acceptance | `services/offers.py` |
| `PC-BR-015` | Multiple-offer policy | `domain/offer_policy.py` |
| `PC-BR-016` | Anonymised student statistics | small-cell floor in `services/stats.py` |
| `PC-BR-017` | Announcement topics bounded | fixed topic choices |
| `PC-BR-020` | Alumni kept out of active workflows | `selectors/scoping.py` — trivially, see G1 |
| `PC-BR-021` | Email hand-off | notification outbox and delivery worker |
| `PC-BR-023` | Sensitive data view restriction | CPI directory permission-gated |

Use cases `001`, `002`, `003`, `005`, `006`, `008`, `009`, `011`, `012`, `013`,
`015`, `016` and `020` are implemented as specified. `PC-UC-012` includes
company participation (`companies_participated` and the by-company breakdown).

---

## Suggested order

1. **Fix traceability (§2–§4).** Mechanical and safe, and it makes every later
   finding checkable. Worth a generated reference page, as for ELM.
2. **G3 — record corrections.** Smallest real gap, and a wrong placement record
   is a live data-quality problem.
3. **G4 — historical student season selection.** Backend trends and report
   endpoints exist; the student-facing reports page needs a season selector.
4. **G1 and G2 need decisions first** — who counts as an alumnus, and whether
   companies may register themselves. Neither should be built on a guess.

---

## 6. The placement profile was removed

The module used to keep its own student profile — headline, about, skills,
documents and a completeness percentage — and a resume uploaded into it. The
ERP portal already holds all of that on its own profile page, so a student
maintained two, and only the placement one gated applying.

**What changed.** `StudentProfile`, `services/profiles.py` and
`domain/profile_completeness.py` are gone. The resume and the completion flag
are projected from the portal through the IAM into `modules/directory`, and
placement reads them like any other person fact. Recruiters see the resume on
the applicant row rather than behind a separate profile page.

**What this means for the specification.**

| Id | Was | Now |
|---|---|---|
| `PC-BR-001` | completeness computed here | the portal's `profile_completed`; the rule still holds, the answer comes from upstream |
| `PC-UC-001` | student maintains a placement profile | **deviation** — one profile, on the portal |
| `PC-UC-023` | a structured resume derived from the profile | **deviation** — a link the student maintains upstream, not generated data |

**What was deliberately kept.** `ProfileDocument` survives, detached from the
profile and keyed by `user_id` alone. It holds offer letters and clearance
paperwork, which are placement's own and duplicate nothing — deleting it with
the profile would have destroyed them. Its `resume` kind is gone.

**Eligibility lost the `skills` criterion**, which had no source once the
profile went; the IAM does not project skills. No posting used it. The
`LIST_FIELDS` machinery stays, because a closed vocabulary is meant to be
added to.
