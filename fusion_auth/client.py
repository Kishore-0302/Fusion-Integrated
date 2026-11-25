"""HTTP client for Fusion_System_Administrator — the IAM.

Identity, RBAC and directory data all come from there; this service holds no
user table. Fails closed: a network error or non-200 means "not authenticated"
or "no such user", never "allow". Directory lookups are batched by signature,
so an N+1 is hard to write.
"""
from __future__ import annotations

import contextlib
import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

import requests
from django.conf import settings
from django.core.cache import cache

log = logging.getLogger("fusion.iam")


class IamUnavailable(Exception):
    """IAM could not be reached or answered with a server error."""


class IamThrottled(Exception):
    """IAM refused a login for too many attempts: its rate limit, or a locked account."""

    def __init__(self, message: str, retry_after: int | None = None):
        super().__init__(message)
        self.message = message
        self.retry_after = retry_after


@dataclass(frozen=True)
class IamSession:
    """The authenticated principal, as IAM describes it."""

    user_id: int
    username: str
    display_name: str
    kind: str                       # student | faculty | staff | operator
    active_role: str | None = None
    roles: tuple[str, ...] = ()
    permissions: frozenset[str] = frozenset()
    modules: tuple[str, ...] = ()
    #: The whole sidebar. Empty from an older IAM, and the caller falls back.
    navigation: tuple[dict, ...] = ()
    email: str = ""

    def has_permission(self, code: str) -> bool:
        return code in self.permissions

    def has_module(self, code: str) -> bool:
        return code in self.modules


@dataclass(frozen=True)
class UserRef:
    """Common directory data. Whatever IAM knows about a person."""

    user_id: int
    username: str
    display_name: str
    kind: str
    email: str = ""
    department: str = ""
    programme: str = ""
    discipline: str = ""
    batch_year: int | None = None
    #: Defaults True so an identity service that does not send it still works.
    is_active: bool = True
    #: Maintained on the ERP portal's profile page. Read here, never written.
    resume_link: str = ""
    profile_completed: bool = False
    skills: tuple[str, ...] = ()
    extra: dict[str, Any] = field(default_factory=dict)


class IamClient:
    def __init__(self, base_url: str | None = None, token: str | None = None,
                 timeout: int | None = None):
        self.base = (base_url or settings.IAM_BASE_URL).rstrip("/")
        self.prefix = settings.IAM_API_PREFIX.rstrip("/")
        self.token = token if token is not None else settings.IAM_SERVICE_TOKEN
        self.timeout = timeout or settings.IAM_TIMEOUT_SECONDS

    # -- plumbing ---------------------------------------------------------
    def _url(self, path: str) -> str:
        return f"{self.base}{self.prefix}/{path.lstrip('/')}"

    def _get(self, path: str, *, params=None, cookies=None, auth_token=None):
        headers = {"Accept": "application/json"}
        if auth_token:
            headers["Authorization"] = f"Token {auth_token}"     # as the person
        elif self.token:
            # As the service: a separate scheme, so a machine is never a person.
            headers["Authorization"] = f"Service {self.token}"
        try:
            r = requests.get(self._url(path), params=params, headers=headers,
                             cookies=cookies or {}, timeout=self.timeout)
        except requests.RequestException as exc:
            log.warning("iam.unreachable path=%s err=%s", path, exc)
            raise IamUnavailable(str(exc)) from exc
        if r.status_code in (401, 403):
            return None                       # not authenticated / not allowed
        if r.status_code == 404:
            return None
        if r.status_code >= 500:
            raise IamUnavailable(f"IAM returned {r.status_code}")
        if r.status_code >= 400:
            return None
        try:
            return r.json()
        except ValueError as exc:
            raise IamUnavailable("IAM returned a non-JSON body") from exc

    # -- identity ---------------------------------------------------------
    def resolve_session(self, *, auth_token: str | None = None,
                        cookies: dict | None = None) -> IamSession | None:
        """Who is holding this credential? None means 'not authenticated'."""
        key = None
        ttl = settings.IAM_SESSION_CACHE_SECONDS
        if auth_token and ttl:
            key = f"iam:session:{auth_token[:48]}"
            hit = cache.get(key)
            if hit is not None:
                return hit or None            # cached negative stays negative

        payload = self._get("iam/v1/me", auth_token=auth_token, cookies=cookies)
        session = self._to_session(payload) if payload else None
        if key:
            cache.set(key, session or False, ttl)
        return session

    def forget_session(self, auth_token: str) -> None:
        """Drop the cached session so the next read sees a change immediately."""
        if settings.IAM_SESSION_CACHE_SECONDS:
            cache.delete(f"iam:session:{auth_token[:48]}")

    @staticmethod
    def _to_session(p: dict) -> IamSession | None:
        user = p.get("user") or {}
        uid = user.get("id") or user.get("user_id") or p.get("user_id")
        if uid is None:
            return None
        return IamSession(
            user_id=int(uid),
            username=user.get("username") or p.get("username", ""),
            display_name=user.get("display_name") or user.get("name", ""),
            kind=user.get("kind") or p.get("kind", "student"),
            email=user.get("email", ""),
            active_role=p.get("active_role"),
            roles=tuple(p.get("roles", ())),
            permissions=frozenset(p.get("permissions", ())),
            modules=tuple(p.get("modules", ())),
            navigation=tuple(p.get("navigation", ())),
        )

    def set_active_role(self, auth_token: str, role: str) -> None:
        """Remember the designation this person chose to work as."""
        try:
            r = requests.patch(self._url("iam/v1/me"),
                               json={"last_selected_role": role},
                               headers={"Authorization": f"Token {auth_token}"},
                               timeout=self.timeout)
        except requests.RequestException as exc:
            raise IamUnavailable(str(exc)) from exc
        if r.status_code == 400:
            raise ValueError(r.json().get("detail", "Unknown role."))
        if r.status_code >= 400:
            raise IamUnavailable(f"IAM returned {r.status_code}")
        self.forget_session(auth_token)

    def login(self, username: str, password: str,
              client_ip: str | None = None) -> str | None:
        """Exchange credentials for a session token at the IAM.

        This service never checks a password itself. None means bad
        credentials — deliberately not distinguishing which half was wrong.
        """
        # The IAM limits logins per caller; without this every user shares our address.
        headers = {"X-Forwarded-For": client_ip} if client_ip else {}
        try:
            r = requests.post(self._url("iam/v1/auth/login"),
                              json={"username": username, "password": password},
                              headers=headers, timeout=self.timeout)
        except requests.RequestException as exc:
            raise IamUnavailable(str(exc)) from exc
        if r.status_code == 429:
            raise IamThrottled(_detail(r), _retry_after(r))
        if r.status_code in (400, 401, 403):
            return None
        if r.status_code >= 500:
            raise IamUnavailable(f"IAM returned {r.status_code}")
        try:
            return r.json().get("token")
        except ValueError as exc:
            raise IamUnavailable("IAM returned a non-JSON body") from exc

    def logout(self, auth_token: str) -> None:
        # Best effort: a failure here must not stop someone signing out.
        with contextlib.suppress(requests.RequestException):
            requests.post(self._url("iam/v1/auth/logout"),
                          headers={"Authorization": f"Token {auth_token}"},
                          timeout=self.timeout)

    # -- directory (batched by design) ------------------------------------
    def get_users(self, user_ids: Sequence[int]) -> dict[int, UserRef]:
        """Directory data for several people at once. There is intentionally
        no singular version — that is the one that ends up inside a loop."""
        ids = sorted({int(i) for i in user_ids if i is not None})
        if not ids:
            return {}
        payload = self._get("iam/v1/directory/users",
                            params={"ids": ",".join(map(str, ids))})
        if not payload:
            return {}
        rows = payload.get("results", payload if isinstance(payload, list) else [])
        return {u.user_id: u for u in (self._to_ref(r) for r in rows) if u}

    @staticmethod
    def _to_ref(r: dict) -> UserRef | None:
        uid = r.get("user_id") or r.get("id")
        if uid is None:
            return None
        raw_skills = r.get("skills") or ()
        if isinstance(raw_skills, str):
            raw_skills = [s.strip() for s in raw_skills.split(",") if s.strip()]
        skills = tuple(str(s).strip() for s in raw_skills if str(s).strip())
        return UserRef(
            user_id=int(uid),
            username=r.get("username", ""),
            display_name=r.get("display_name") or r.get("name", ""),
            kind=r.get("kind", ""),
            email=r.get("email", ""),
            department=r.get("department", "") or "",
            programme=r.get("programme", "") or "",
            discipline=r.get("discipline", "") or "",
            batch_year=r.get("batch_year"),
            is_active=bool(r.get("is_active", True)),
            resume_link=r.get("resume_link", "") or "",
            profile_completed=bool(r.get("profile_completed", False)),
            skills=skills,
            extra={k: v for k, v in r.items()
                   if k not in {"user_id", "id", "username", "display_name", "name",
                                "kind", "email", "department", "programme",
                                "discipline", "batch_year", "is_active",
                                "resume_link", "profile_completed", "skills"}},
        )

    # -- academic standing (declared CPI) ---------------------------------
    def get_academic_standings(self, user_ids: Sequence[int]) -> dict[int, dict]:
        """Declared CPI, earned credits and backlogs, batched.

        A student with no declared result is ABSENT from the mapping, never
        zero — read absence as "cannot be assessed", or a missing result
        becomes a very weak one.
        """
        ids = sorted({int(i) for i in user_ids if i is not None})
        if not ids:
            return {}
        payload = self._get("iam/v1/academics/standings",
                            params={"ids": ",".join(map(str, ids))})
        if not payload:
            return {}
        out: dict[int, dict] = {}
        for row in payload.get("results", []):
            uid = row.get("user_id")
            if uid is not None:
                out[int(uid)] = row
        return out

    def academic_directory(self, **filters) -> dict:
        """The whole cohort's declared standing, filtered and paginated.

        Always called with the service credential; the caller must already
        have established that the person asking is placement staff.
        """
        payload = self._get("iam/v1/academics/directory", params=filters)
        return payload or {"count": 0, "results": []}

    def academic_filters(self) -> dict:
        payload = self._get("iam/v1/academics/filters")
        return payload or {"disciplines": [], "batch_years": [], "programmes": []}

    def employee_page(self, *, limit: int = 500, offset: int = 0) -> dict:
        """One page of the payroll."""
        payload = self._get("iam/v1/directory/users",
                            params={"employees": 1, "limit": limit, "offset": offset})
        if not isinstance(payload, dict):
            raise IamUnavailable("directory returned no page")
        return payload

    def count_employees(self) -> int:
        return int(self.employee_page(limit=1).get("count", 0))

    def iter_employees(self, *, page_size: int = 500):
        offset = 0
        while True:
            page = self.employee_page(limit=page_size, offset=offset)
            rows = page.get("results", [])
            for row in rows:
                ref = self._to_ref(row)
                if ref:
                    yield ref
            offset += len(rows)
            if not rows or offset >= int(page.get("count", 0)):
                return

    def search_users(self, q: str = "", kind: str | None = None,
                     limit: int = 25) -> list[UserRef]:
        params = {"q": q, "limit": limit}
        if kind:
            params["kind"] = kind
        payload = self._get("iam/v1/directory/users", params=params)
        rows = (payload or {}).get("results", []) if isinstance(payload, dict) else []
        return [u for u in (self._to_ref(r) for r in rows) if u]


_client: IamClient | None = None


def _detail(r: requests.Response) -> str:
    try:
        return str(r.json().get("detail") or "")
    except ValueError:
        return ""


def _retry_after(r: requests.Response) -> int | None:
    value = r.headers.get("Retry-After", "")
    return int(value) if value.isdigit() else None


def get_client() -> IamClient:
    global _client                                             # noqa: PLW0603
    if _client is None:
        _client = IamClient()
    return _client


def reset_client() -> None:
    """Test hook — drops the memoized client so settings changes take effect."""
    global _client                                             # noqa: PLW0603
    _client = None
