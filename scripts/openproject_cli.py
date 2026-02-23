#!/usr/bin/env python3
"""Conservative OpenProject API v3 CLI for project management and knowledge workflows."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import urlparse

try:
    import requests
except ModuleNotFoundError:  # pragma: no cover - dependency fallback for help-only usage
    requests = None  # type: ignore[assignment]

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:  # pragma: no cover - dependency fallback for help-only usage
    def load_dotenv(*_args: Any, **_kwargs: Any) -> bool:
        return False

API_PREFIX = "/api/v3"
DEFAULT_DECISION_LOG_DIR = Path("project-knowledge/decisions")
DEFAULT_WEEKLY_STATUS_DIR = Path("project-knowledge/status")
DEFAULT_WEEKLY_FETCH_LIMIT = 200
REQUEST_TIMEOUT_SECONDS = 30
MAX_PAGE_SIZE = 200


def to_api_path(url_or_path: str) -> str:
    """Normalize an API href/path into a path that can be passed to `_request`."""
    value = (url_or_path or "").strip()
    if not value:
        return "/"

    if "://" in value:
        parsed = urlparse(value)
        value = parsed.path or "/"

    if value.startswith(API_PREFIX):
        value = value[len(API_PREFIX) :] or "/"

    if not value.startswith("/"):
        value = f"/{value}"

    return value


class OpenProjectError(Exception):
    """Raised when OpenProject configuration or API interaction fails."""

    def __init__(self, message: str, status_code: Optional[int] = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class OpenProjectClient:
    """Minimal OpenProject API v3 client with safe defaults for this alpha."""

    def __init__(
        self,
        base_url: str,
        auth_mode: str = "token",
        api_token: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ) -> None:
        cleaned_base_url = base_url.strip().rstrip("/")
        if cleaned_base_url.endswith(API_PREFIX):
            cleaned_base_url = cleaned_base_url[: -len(API_PREFIX)]
        if not cleaned_base_url:
            raise OpenProjectError("OPENPROJECT_BASE_URL is required.")

        self.base_url = cleaned_base_url
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/hal+json",
                "Content-Type": "application/json",
                "User-Agent": "openclaw-openproject-cli/0.1.0-alpha",
            }
        )

        mode = auth_mode.strip().lower() if auth_mode else "token"
        if mode == "token":
            if not api_token:
                raise OpenProjectError("OPENPROJECT_API_TOKEN is required for token authentication.")
            # OpenProject token auth convention: username=apikey, password=<token>
            self.session.auth = ("apikey", api_token)
        elif mode == "basic":
            if not username or not password:
                raise OpenProjectError(
                    "OPENPROJECT_USERNAME and OPENPROJECT_PASSWORD are required for basic auth mode."
                )
            self.session.auth = (username, password)
        else:
            raise OpenProjectError(
                f"Unsupported auth mode '{auth_mode}'. Use 'token' (default) or 'basic'."
            )

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        payload: Optional[Dict[str, Any]] = None,
        expected_statuses: Tuple[int, ...] = (200,),
    ) -> Dict[str, Any]:
        """Send a request to OpenProject and normalize common errors."""
        if not path.startswith("/"):
            path = f"/{path}"

        url = f"{self.base_url}{API_PREFIX}{path}"

        try:
            response = self.session.request(
                method=method,
                url=url,
                params=params,
                json=payload,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
        except requests.RequestException as exc:
            raise OpenProjectError(f"Network error while calling OpenProject: {exc}") from exc

        if response.status_code in expected_statuses:
            if not response.content:
                return {}
            try:
                return response.json()
            except ValueError:
                return {}

        detail = extract_error_message(response)
        if response.status_code in (401, 403):
            raise OpenProjectError(
                "Authentication failed. Check OPENPROJECT_BASE_URL, OPENPROJECT_API_TOKEN, "
                "and token permissions.",
                status_code=response.status_code,
            )

        raise OpenProjectError(
            f"OpenProject API error {response.status_code} for {method.upper()} {path}: {detail}",
            status_code=response.status_code,
        )

    def _collect_collection(
        self,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Collect HAL collection pages up to `limit` elements."""
        if limit <= 0:
            return []

        base_params = dict(params or {})
        page_size = int(base_params.pop("pageSize", min(limit, MAX_PAGE_SIZE)))
        page_size = max(1, min(page_size, MAX_PAGE_SIZE))

        collected: List[Dict[str, Any]] = []
        offset = 1

        while len(collected) < limit:
            remaining = limit - len(collected)
            request_params = dict(base_params)
            request_params["offset"] = offset
            request_params["pageSize"] = min(page_size, remaining)

            data = self._request("GET", path, params=request_params, expected_statuses=(200,))
            elements = extract_embedded_elements(data)
            if not elements:
                break

            collected.extend(elements[:remaining])

            count = int(data.get("count", len(elements)) or len(elements))
            if count <= 0:
                break

            links = data.get("_links", {})
            has_next = isinstance(links, dict) and isinstance(links.get("nextByOffset"), dict)
            if not has_next:
                break

            offset += count

        return collected[:limit]

    def get_projects(self, limit: int = 500) -> List[Dict[str, Any]]:
        """Return a list of projects visible to the current user."""
        return self._collect_collection("/projects", limit=limit)

    def resolve_project(self, project_ref: str) -> Dict[str, Any]:
        """Resolve a project by id, identifier, or exact name (case-insensitive for text)."""
        target = project_ref.strip()
        if not target:
            raise OpenProjectError("Project value is empty.")

        projects = self.get_projects()
        if not projects:
            raise OpenProjectError("No projects were returned by OpenProject.")

        lowered_target = target.lower()

        for project in projects:
            project_id = str(project.get("id", "")).strip()
            identifier = str(project.get("identifier", "")).strip()
            name = str(project.get("name", "")).strip()

            if target.isdigit() and project_id == target:
                return project
            if identifier and identifier.lower() == lowered_target:
                return project
            if name and name.lower() == lowered_target:
                return project

        raise OpenProjectError(
            "Could not resolve project. Provide a valid project ID or identifier, "
            "or set OPENPROJECT_DEFAULT_PROJECT."
        )

    def list_work_packages(
        self,
        project_id: int,
        limit: int = 50,
        status_filter: Optional[str] = None,
        assignee_filter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch work packages for a project using project scope and optional filter hints."""
        params: Dict[str, Any] = {}
        # Try API-side filtering via query hints when available in the server version.
        if status_filter:
            params["status"] = status_filter
        if assignee_filter:
            params["assignee"] = assignee_filter

        path = f"/projects/{project_id}/work_packages"
        try:
            return self._collect_collection(path, params=params, limit=limit)
        except OpenProjectError as exc:
            if not (status_filter or assignee_filter) or exc.status_code not in (400, 422):
                raise
            return self._collect_collection(path, params={}, limit=limit)

    def resolve_type(self, project_id: int, type_name: str) -> Tuple[str, str]:
        """Resolve a work package type by name and return (name, href)."""
        lowered_target = type_name.strip().lower()
        endpoints = [f"/projects/{project_id}/types", "/types"]
        available: List[str] = []

        for endpoint in endpoints:
            try:
                data = self._request("GET", endpoint, expected_statuses=(200,))
            except OpenProjectError as exc:
                if exc.status_code in (404, 405):
                    continue
                raise

            for item in extract_embedded_elements(data):
                name = str(item.get("name", "")).strip()
                href = nested_get(item, ["_links", "self", "href"], "")
                if name:
                    available.append(name)
                if name and name.lower() == lowered_target:
                    return name, href or f"{API_PREFIX}/types/{item.get('id')}"

        if available:
            hint = ", ".join(sorted(set(available)))
            raise OpenProjectError(f"Unknown type '{type_name}'. Available types: {hint}")

        raise OpenProjectError(
            "Could not resolve type list from OpenProject. Check permissions for reading types."
        )

    def create_work_package(
        self,
        project: Dict[str, Any],
        subject: str,
        type_name: str = "Task",
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a work package in a project."""
        project_id = int(project["id"])
        project_href = nested_get(project, ["_links", "self", "href"], f"{API_PREFIX}/projects/{project_id}")
        _, type_href = self.resolve_type(project_id, type_name)

        payload: Dict[str, Any] = {
            "subject": subject,
            "_links": {
                "project": {"href": project_href},
                "type": {"href": type_href},
            },
        }
        if description:
            payload["description"] = {"raw": description}

        return self._request("POST", "/work_packages", payload=payload, expected_statuses=(200, 201))

    def get_work_package(self, work_package_id: int) -> Dict[str, Any]:
        """Fetch a single work package by id."""
        return self._request("GET", f"/work_packages/{work_package_id}", expected_statuses=(200,))

    def resolve_status(self, status_name: str) -> Tuple[str, str]:
        """Resolve status by name and return (name, href)."""
        lowered_target = status_name.strip().lower()
        data = self._request("GET", "/statuses", expected_statuses=(200,))
        statuses = extract_embedded_elements(data)

        available: List[str] = []
        for status in statuses:
            name = str(status.get("name", "")).strip()
            href = nested_get(status, ["_links", "self", "href"], "")
            if name:
                available.append(name)
            if name and name.lower() == lowered_target:
                return name, href or f"{API_PREFIX}/statuses/{status.get('id')}"

        if available:
            hint = ", ".join(sorted(set(available)))
            raise OpenProjectError(f"Unknown status '{status_name}'. Available statuses: {hint}")

        raise OpenProjectError("No statuses were returned by OpenProject.")

    def resolve_allowed_transition_status(
        self,
        work_package: Dict[str, Any],
        status_name: str,
    ) -> Tuple[str, str]:
        """
        Resolve status from statuses allowed for this specific work package transition.

        Uses the work package form endpoint to respect workflow/role-based transitions.
        Falls back to global status lookup if transition metadata is unavailable.
        """
        lock_version = work_package.get("lockVersion")
        if lock_version is None:
            raise OpenProjectError("Work package payload did not include lockVersion.")

        update_form_href = nested_get(work_package, ["_links", "update", "href"], "")
        if not update_form_href:
            return self.resolve_status(status_name)

        try:
            form_data = self._request(
                "POST",
                to_api_path(update_form_href),
                payload={"lockVersion": lock_version},
                expected_statuses=(200,),
            )
        except OpenProjectError as exc:
            if exc.status_code in (404, 405, 422):
                return self.resolve_status(status_name)
            raise

        status_schema = nested_get(form_data, ["_embedded", "schema", "status"], None)
        if not isinstance(status_schema, dict):
            return self.resolve_status(status_name)

        allowed_values = nested_get(status_schema, ["_embedded", "allowedValues"], [])
        if not isinstance(allowed_values, list) or not allowed_values:
            return self.resolve_status(status_name)

        lowered_target = status_name.strip().lower()
        available: List[str] = []
        for status in allowed_values:
            if not isinstance(status, dict):
                continue
            name = str(status.get("name", "")).strip()
            href = nested_get(status, ["_links", "self", "href"], "")
            if name:
                available.append(name)
            if name and name.lower() == lowered_target:
                return name, href or f"{API_PREFIX}/statuses/{status.get('id')}"

        if available:
            hint = ", ".join(sorted(set(available)))
            raise OpenProjectError(
                f"Status '{status_name}' is not an allowed transition for this work package. "
                f"Allowed statuses: {hint}"
            )

        return self.resolve_status(status_name)

    def update_work_package_status(self, work_package_id: int, status_name: str) -> Dict[str, Any]:
        """Update a work package status using transition-aware status resolution."""
        work_package = self.get_work_package(work_package_id)
        lock_version = work_package.get("lockVersion")
        if lock_version is None:
            raise OpenProjectError("Work package payload did not include lockVersion.")

        _, status_href = self.resolve_allowed_transition_status(work_package, status_name)
        update_href = nested_get(work_package, ["_links", "updateImmediately", "href"], "")
        patch_path = to_api_path(update_href) if update_href else f"/work_packages/{work_package_id}"
        payload = {
            "lockVersion": lock_version,
            "_links": {
                "status": {
                    "href": status_href,
                }
            },
        }
        try:
            return self._request(
                "PATCH",
                patch_path,
                payload=payload,
                expected_statuses=(200,),
            )
        except OpenProjectError as exc:
            if exc.status_code == 422:
                raise OpenProjectError(
                    f"Status update rejected by workflow for work package #{work_package_id}. {exc}"
                ) from exc
            raise

    def add_comment(self, work_package_id: int, comment: str) -> Dict[str, Any]:
        """Add a note/comment to a work package using best-effort API compatibility."""
        work_package = self.get_work_package(work_package_id)
        lock_version = work_package.get("lockVersion")

        add_comment_link = nested_get(work_package, ["_links", "addComment"], None)
        if isinstance(add_comment_link, dict):
            comment_href = add_comment_link.get("href", "")
            method = str(add_comment_link.get("method", "post")).upper()
            if comment_href and method in {"POST", "PATCH"}:
                payload = {"comment": {"raw": comment}}
                try:
                    return self._request(
                        method,
                        to_api_path(comment_href),
                        payload=payload,
                        expected_statuses=(200, 201),
                    )
                except OpenProjectError as exc:
                    if exc.status_code not in (400, 404, 405, 415, 422):
                        raise

        if lock_version is not None:
            update_href = nested_get(work_package, ["_links", "updateImmediately", "href"], "")
            patch_path = to_api_path(update_href) if update_href else f"/work_packages/{work_package_id}"
            patch_payload = {
                "lockVersion": lock_version,
                "comment": {
                    "raw": comment,
                },
            }
            try:
                return self._request(
                    "PATCH",
                    patch_path,
                    payload=patch_payload,
                    expected_statuses=(200,),
                )
            except OpenProjectError as patch_error:
                if patch_error.status_code not in (400, 404, 405, 415, 422):
                    raise

        activities_href = nested_get(work_package, ["_links", "activities", "href"], "")
        fallback_path = to_api_path(activities_href) if activities_href else f"/work_packages/{work_package_id}/activities"
        try:
            return self._request(
                "POST",
                fallback_path,
                payload={"comment": {"raw": comment}},
                expected_statuses=(200, 201),
            )
        except OpenProjectError as fallback_error:
            raise OpenProjectError(
                "Unable to add comment. API v3 comment creation is not available via addComment, "
                "PATCH comment, or activities endpoint on this server/version."
            ) from fallback_error


def extract_error_message(response: requests.Response) -> str:
    """Extract a readable error message from an OpenProject error payload."""
    try:
        data = response.json()
    except ValueError:
        body = response.text.strip()
        return body if body else "No error body returned."

    if isinstance(data, dict):
        if isinstance(data.get("message"), str) and data["message"].strip():
            return data["message"].strip()

        embedded = data.get("_embedded")
        if isinstance(embedded, dict):
            errors = embedded.get("errors")
            if isinstance(errors, list):
                messages: List[str] = []
                for err in errors:
                    if isinstance(err, dict):
                        msg = err.get("message")
                        if isinstance(msg, str) and msg.strip():
                            messages.append(msg.strip())
                if messages:
                    return "; ".join(messages)

    return "Unexpected error format returned by server."


def extract_embedded_elements(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return `_embedded.elements` from HAL payloads."""
    embedded = payload.get("_embedded")
    if not isinstance(embedded, dict):
        return []

    elements = embedded.get("elements")
    if not isinstance(elements, list):
        return []

    return [item for item in elements if isinstance(item, dict)]


def nested_get(data: Dict[str, Any], keys: Iterable[str], default: Any = "") -> Any:
    """Safely walk a nested dictionary path."""
    current: Any = data
    for key in keys:
        if not isinstance(current, dict):
            return default
        if key not in current:
            return default
        current = current[key]
    return current


def get_default_project() -> str:
    """Return default project reference from env, if configured."""
    return os.getenv("OPENPROJECT_DEFAULT_PROJECT", "").strip()


def require_project(project_arg: Optional[str]) -> str:
    """Return explicit project argument or env default, otherwise fail."""
    project = (project_arg or "").strip() or get_default_project()
    if not project:
        raise OpenProjectError(
            "--project is required unless OPENPROJECT_DEFAULT_PROJECT is set."
        )
    return project


def build_client_from_env() -> OpenProjectClient:
    """Build the OpenProject client from environment configuration."""
    if requests is None:
        raise OpenProjectError(
            "Missing dependency 'requests'. Install requirements.txt before using API commands."
        )

    base_url = os.getenv("OPENPROJECT_BASE_URL", "").strip()
    auth_mode = os.getenv("OPENPROJECT_AUTH_MODE", "token").strip().lower()

    if auth_mode == "basic":
        username = os.getenv("OPENPROJECT_USERNAME", "").strip()
        password = os.getenv("OPENPROJECT_PASSWORD", "").strip()
        return OpenProjectClient(
            base_url=base_url,
            auth_mode="basic",
            username=username,
            password=password,
        )

    api_token = os.getenv("OPENPROJECT_API_TOKEN", "").strip()
    return OpenProjectClient(base_url=base_url, auth_mode="token", api_token=api_token)


def link_title(item: Dict[str, Any], relation: str, default: str = "-") -> str:
    """Get a relation title from `_links` with fallback to relation id."""
    link_obj = nested_get(item, ["_links", relation], None)
    if isinstance(link_obj, dict):
        title = link_obj.get("title")
        if isinstance(title, str) and title.strip():
            return title.strip()
        href = link_obj.get("href")
        if isinstance(href, str) and href.strip():
            return href.rstrip("/").split("/")[-1]
    return default


def format_date(iso_timestamp: str) -> str:
    """Format ISO timestamp into YYYY-MM-DD where possible."""
    if not iso_timestamp:
        return "-"
    if len(iso_timestamp) >= 10:
        return iso_timestamp[:10]
    return iso_timestamp


def truncate(value: str, max_length: int = 70) -> str:
    """Truncate text for compact terminal rows."""
    text = value.strip()
    if len(text) <= max_length:
        return text
    return f"{text[: max_length - 3]}..."


def normalize(value: str) -> str:
    """Normalize text for case-insensitive comparisons."""
    return value.strip().lower()


def filter_work_packages(
    work_packages: List[Dict[str, Any]],
    status_filter: Optional[str],
    assignee_filter: Optional[str],
) -> List[Dict[str, Any]]:
    """Apply client-side status and assignee filtering."""
    status_query = normalize(status_filter or "")
    assignee_query = normalize(assignee_filter or "")

    filtered: List[Dict[str, Any]] = []
    for wp in work_packages:
        status = normalize(link_title(wp, "status", ""))
        assignee = normalize(link_title(wp, "assignee", "unassigned"))

        if status_query and status_query not in status:
            continue
        if assignee_query and assignee_query not in assignee:
            continue
        filtered.append(wp)

    return filtered


def print_projects(projects: List[Dict[str, Any]]) -> None:
    """Print projects in a concise, readable table."""
    if not projects:
        print("No projects found.")
        return

    print("ID   Identifier            Name")
    print("---  --------------------  ------------------------------")
    for project in projects:
        project_id = str(project.get("id", "?"))
        identifier = str(project.get("identifier", "-") or "-")
        name = str(project.get("name", "-") or "-")
        print(f"{project_id:<3}  {truncate(identifier, 20):<20}  {truncate(name, 30)}")


def print_work_packages(work_packages: List[Dict[str, Any]]) -> None:
    """Print work package rows with the required fields."""
    if not work_packages:
        print("No matching work packages found.")
        return

    print("WP ID   Subject                              Status         Assignee        Updated")
    print("-----   -----------------------------------  -------------  --------------  ----------")
    for wp in work_packages:
        wp_id = str(wp.get("id", "?"))
        subject = truncate(str(wp.get("subject", "(no subject)")), 35)
        status = truncate(link_title(wp, "status", "-"), 13)
        assignee = truncate(link_title(wp, "assignee", "Unassigned"), 14)
        updated = format_date(str(wp.get("updatedAt", "")))
        print(f"{wp_id:<5}   {subject:<35}  {status:<13}  {assignee:<14}  {updated}")


def status_bucket(status_name: str) -> str:
    """Map a status name into high-level weekly summary buckets."""
    label = normalize(status_name)
    if any(token in label for token in ("done", "closed", "resolved", "complete", "completed")):
        return "completed"
    if any(token in label for token in ("block", "risk", "hold", "stuck")):
        return "blockers"
    if any(token in label for token in ("progress", "doing", "review", "test", "active", "open", "new")):
        return "in_progress"
    return "in_progress"


def wp_line(wp: Dict[str, Any]) -> str:
    """Return a compact markdown bullet line for a work package."""
    wp_id = wp.get("id", "?")
    subject = str(wp.get("subject", "(no subject)"))
    status = link_title(wp, "status", "-")
    assignee = link_title(wp, "assignee", "Unassigned")
    return f"- #{wp_id} {subject} ({status}; {assignee})"


def build_weekly_summary(project: Dict[str, Any], work_packages: List[Dict[str, Any]]) -> str:
    """Generate a compact markdown weekly summary grouped by status."""
    completed: List[Dict[str, Any]] = []
    in_progress: List[Dict[str, Any]] = []
    blockers: List[Dict[str, Any]] = []

    for wp in work_packages:
        status = link_title(wp, "status", "-")
        bucket = status_bucket(status)
        if bucket == "completed":
            completed.append(wp)
        elif bucket == "blockers":
            blockers.append(wp)
        else:
            in_progress.append(wp)

    project_name = str(project.get("name") or project.get("identifier") or project.get("id"))
    today = datetime.now().date().isoformat()

    lines: List[str] = [
        f"# Weekly Status - {project_name}",
        f"Date: {today}",
        "",
        "## Wins / completed",
    ]

    if completed:
        lines.extend(wp_line(wp) for wp in completed[:10])
    else:
        lines.append("- No completed items detected in current snapshot.")

    lines.extend(["", "## In progress"])
    if in_progress:
        lines.extend(wp_line(wp) for wp in in_progress[:15])
    else:
        lines.append("- No in-progress items detected.")

    lines.extend(["", "## Blockers / risks"])
    if blockers:
        lines.extend(wp_line(wp) for wp in blockers[:10])
    else:
        lines.append("- No explicit blockers inferable from current status labels.")

    lines.extend(["", "## Next focus"])
    focus_items = in_progress[:5]
    if focus_items:
        lines.extend(wp_line(wp) for wp in focus_items)
    else:
        lines.append("- Confirm priorities for the next sprint window.")

    return "\n".join(lines).strip() + "\n"


def write_text_file(path: Path, content: str) -> Path:
    """Write text content to a file, creating parent directories when needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def slugify(value: str) -> str:
    """Generate a filesystem-safe slug from free text."""
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "decision"


def unique_path(base_path: Path) -> Path:
    """Avoid overwriting an existing file by appending a numeric suffix."""
    if not base_path.exists():
        return base_path

    counter = 2
    while True:
        candidate = base_path.with_name(f"{base_path.stem}-{counter}{base_path.suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


def build_decision_markdown(
    date_text: str,
    project: str,
    title: str,
    decision: str,
    context: str,
    impact: str,
    followup: str,
) -> str:
    """Render a decision log entry in markdown."""
    context_block = context.strip() or "(none provided)"
    impact_block = impact.strip() or "(to be assessed)"
    followup_block = followup.strip() or "(none)"

    return (
        f"# Decision: {title}\n\n"
        f"Date: {date_text}\n"
        f"Project: {project}\n\n"
        "## Context\n"
        f"{context_block}\n\n"
        "## Decision\n"
        f"{decision.strip()}\n\n"
        "## Impact\n"
        f"{impact_block}\n\n"
        "## Follow-up\n"
        f"{followup_block}\n"
    )


def maybe_print_json(data: Any, enabled: bool) -> None:
    """Print debug JSON when requested."""
    if enabled:
        print(json.dumps(data, indent=2, sort_keys=True))


def command_list_projects(args: argparse.Namespace) -> None:
    client = build_client_from_env()
    projects = client.get_projects()
    print_projects(projects)
    maybe_print_json(projects, args.debug_json)


def command_list_work_packages(args: argparse.Namespace) -> None:
    project_ref = require_project(args.project)
    client = build_client_from_env()
    project = client.resolve_project(project_ref)

    work_packages = client.list_work_packages(
        int(project["id"]),
        limit=args.limit,
        status_filter=args.status,
        assignee_filter=args.assignee,
    )
    filtered = filter_work_packages(work_packages, args.status, args.assignee)

    project_label = project.get("identifier") or project.get("name") or project.get("id")
    print(f"Project: {project_label}")
    print_work_packages(filtered)
    maybe_print_json(filtered, args.debug_json)


def command_create_work_package(args: argparse.Namespace) -> None:
    project_ref = require_project(args.project)
    client = build_client_from_env()
    project = client.resolve_project(project_ref)

    created = client.create_work_package(
        project=project,
        subject=args.subject,
        type_name=args.type,
        description=args.description,
    )

    wp_id = created.get("id", "?")
    subject = created.get("subject", args.subject)
    print(f"Created work package #{wp_id}: {subject}")
    maybe_print_json(created, args.debug_json)


def command_update_work_package_status(args: argparse.Namespace) -> None:
    client = build_client_from_env()
    updated = client.update_work_package_status(args.id, args.status)

    wp_id = updated.get("id", args.id)
    status = link_title(updated, "status", args.status)
    print(f"Updated work package #{wp_id} to status '{status}'.")
    maybe_print_json(updated, args.debug_json)


def command_add_comment(args: argparse.Namespace) -> None:
    client = build_client_from_env()
    updated = client.add_comment(args.id, args.comment)

    wp_id = updated.get("id", args.id)
    print(f"Added comment to work package #{wp_id}.")
    maybe_print_json(updated, args.debug_json)


def command_weekly_summary(args: argparse.Namespace) -> None:
    project_ref = require_project(args.project)
    client = build_client_from_env()
    project = client.resolve_project(project_ref)

    work_packages = client.list_work_packages(int(project["id"]), limit=DEFAULT_WEEKLY_FETCH_LIMIT)
    summary = build_weekly_summary(project, work_packages)
    print(summary)

    if args.output:
        output_path = Path(args.output)
    else:
        today = datetime.now().date().isoformat()
        output_path = DEFAULT_WEEKLY_STATUS_DIR / f"{today}-weekly-status.md"

    written_path = write_text_file(output_path, summary)
    print(f"Saved weekly summary to {written_path}")


def command_log_decision(args: argparse.Namespace) -> None:
    project_ref = require_project(args.project)

    configured_dir = os.getenv("OPENPROJECT_DECISION_LOG_DIR", "").strip()
    decision_dir = Path(configured_dir) if configured_dir else DEFAULT_DECISION_LOG_DIR

    today = datetime.now().date().isoformat()
    filename = f"{today}_{slugify(args.title)}.md"
    file_path = unique_path(decision_dir / filename)

    markdown = build_decision_markdown(
        date_text=today,
        project=project_ref,
        title=args.title,
        decision=args.decision,
        context=args.context or "",
        impact=args.impact or "",
        followup=args.followup or "",
    )

    written_path = write_text_file(file_path, markdown)
    print(f"Created decision log: {written_path}")


def build_parser() -> argparse.ArgumentParser:
    """Build CLI argument parser and subcommands."""
    parser = argparse.ArgumentParser(
        description="OpenProject project-management and knowledge CLI (alpha)."
    )
    parser.add_argument(
        "--debug-json",
        action="store_true",
        help="Print raw JSON payloads for troubleshooting.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    parser_projects = subparsers.add_parser(
        "list-projects",
        help="List visible OpenProject projects.",
        description="Fetch and print projects from OpenProject.",
    )
    parser_projects.set_defaults(func=command_list_projects)

    parser_list_wp = subparsers.add_parser(
        "list-work-packages",
        help="List work packages for a project.",
        description="Fetch work packages and apply optional client-side filters.",
    )
    parser_list_wp.add_argument(
        "--project",
        help="Project ID or identifier. Optional when OPENPROJECT_DEFAULT_PROJECT is set.",
    )
    parser_list_wp.add_argument(
        "--status",
        help="Optional status filter (case-insensitive substring match).",
    )
    parser_list_wp.add_argument(
        "--assignee",
        help="Optional assignee filter (case-insensitive substring match).",
    )
    parser_list_wp.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Maximum number of work packages to fetch (default: 50).",
    )
    parser_list_wp.set_defaults(func=command_list_work_packages)

    parser_create_wp = subparsers.add_parser(
        "create-work-package",
        help="Create a new work package.",
        description="Create a work package in a project.",
    )
    parser_create_wp.add_argument(
        "--project",
        help="Project ID or identifier. Optional when OPENPROJECT_DEFAULT_PROJECT is set.",
    )
    parser_create_wp.add_argument("--subject", required=True, help="Work package subject/title.")
    parser_create_wp.add_argument(
        "--type",
        default="Task",
        help="Work package type name (default: Task).",
    )
    parser_create_wp.add_argument(
        "--description",
        help="Optional work package description.",
    )
    parser_create_wp.set_defaults(func=command_create_work_package)

    parser_update_status = subparsers.add_parser(
        "update-work-package-status",
        help="Update work package status.",
        description="Update status of an existing work package by status name.",
    )
    parser_update_status.add_argument("--id", type=int, required=True, help="Work package ID.")
    parser_update_status.add_argument(
        "--status",
        required=True,
        help="Target status name (case-insensitive).",
    )
    parser_update_status.set_defaults(func=command_update_work_package_status)

    parser_comment = subparsers.add_parser(
        "add-comment",
        help="Add a comment to a work package.",
        description="Add a note/comment to a work package via API v3 best effort.",
    )
    parser_comment.add_argument("--id", type=int, required=True, help="Work package ID.")
    parser_comment.add_argument("--comment", required=True, help="Comment text.")
    parser_comment.set_defaults(func=command_add_comment)

    parser_weekly = subparsers.add_parser(
        "weekly-summary",
        help="Generate a compact weekly markdown summary.",
        description="Create a weekly status summary grouped by work package status.",
    )
    parser_weekly.add_argument(
        "--project",
        help="Project ID or identifier. Optional when OPENPROJECT_DEFAULT_PROJECT is set.",
    )
    parser_weekly.add_argument(
        "--output",
        help="Optional output file path. Defaults to project-knowledge/status/YYYY-MM-DD-weekly-status.md.",
    )
    parser_weekly.set_defaults(func=command_weekly_summary)

    parser_decision = subparsers.add_parser(
        "log-decision",
        help="Write a project decision markdown entry.",
        description="Create a decision log entry in project-knowledge/decisions.",
    )
    parser_decision.add_argument(
        "--project",
        help="Project ID or identifier. Optional when OPENPROJECT_DEFAULT_PROJECT is set.",
    )
    parser_decision.add_argument("--title", required=True, help="Decision title.")
    parser_decision.add_argument("--decision", required=True, help="Decision statement.")
    parser_decision.add_argument("--context", help="Optional context notes.")
    parser_decision.add_argument("--impact", help="Optional impact notes.")
    parser_decision.add_argument("--followup", help="Optional follow-up actions.")
    parser_decision.set_defaults(func=command_log_decision)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entrypoint."""
    load_dotenv()
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if hasattr(args, "limit") and args.limit is not None and args.limit <= 0:
            raise OpenProjectError("--limit must be greater than 0.")
        args.func(args)
        return 0
    except OpenProjectError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Error: Interrupted.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
