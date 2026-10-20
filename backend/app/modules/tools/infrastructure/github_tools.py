"""Read-only GitHub tools that act as the signed-in user, via the GitHub REST API."""

from __future__ import annotations

import base64
import json
import re
from collections.abc import Awaitable, Callable
from typing import Any
from urllib.parse import quote

import httpx

from app.core.logging import get_logger
from app.modules.llm.domain.models import ToolDefinition
from app.modules.tools.domain.interfaces import ToolExecutor
from app.modules.tools.domain.models import ToolResult
from app.modules.tools.infrastructure.mcp_hub import MAX_TOOL_OUTPUT_CHARS


GITHUB_API_URL = "https://api.github.com"
_MAX_LIMIT = 50
_MAX_BODY_CHARS = 2000
_NAME_PATTERN = re.compile(r"[A-Za-z0-9_.-]{1,100}")

_REPO = {"owner": {"type": "string", "description": "Account or organization that owns the repository."}, "repo": {"type": "string", "description": "Repository name."}}
_LIMIT = {"limit": {"type": "integer", "description": f"How many results to return (1-{_MAX_LIMIT}).", "default": 10}}
_STATE = {"state": {"type": "string", "enum": ["open", "closed", "all"], "default": "open"}}


def _schema(properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {"type": "object", "properties": properties, "required": required}


TOOL_DEFINITIONS = [
    ToolDefinition(name="github__get_me", description="Get the connected GitHub user's profile.", input_schema=_schema({}, [])),
    ToolDefinition(
        name="github__list_my_repositories",
        description="List repositories the connected GitHub user owns or can access, most recently updated first.",
        input_schema=_schema(_LIMIT, []),
    ),
    ToolDefinition(
        name="github__search_repositories",
        description="Search GitHub repositories using GitHub search syntax, e.g. 'fastapi language:python' or 'user:octocat'.",
        input_schema=_schema({"query": {"type": "string"}, **_LIMIT}, ["query"]),
    ),
    ToolDefinition(name="github__get_repository", description="Get a repository's details.", input_schema=_schema(_REPO, ["owner", "repo"])),
    ToolDefinition(
        name="github__list_issues",
        description="List issues (not pull requests) in a repository.",
        input_schema=_schema({**_REPO, **_STATE, **_LIMIT}, ["owner", "repo"]),
    ),
    ToolDefinition(
        name="github__get_issue",
        description="Get one issue or pull request's description and recent comments.",
        input_schema=_schema({**_REPO, "number": {"type": "integer"}}, ["owner", "repo", "number"]),
    ),
    ToolDefinition(
        name="github__list_pull_requests",
        description="List pull requests in a repository.",
        input_schema=_schema({**_REPO, **_STATE, **_LIMIT}, ["owner", "repo"]),
    ),
    ToolDefinition(
        name="github__list_commits",
        description="List recent commits on a repository's default branch or a given branch.",
        input_schema=_schema({**_REPO, "branch": {"type": "string"}, **_LIMIT}, ["owner", "repo"]),
    ),
    ToolDefinition(
        name="github__get_file_contents",
        description="Read a file, or list a directory, in a repository. Use an empty path for the root.",
        input_schema=_schema({**_REPO, "path": {"type": "string", "default": ""}, "ref": {"type": "string", "description": "Branch, tag or commit."}}, ["owner", "repo"]),
    ),
]


class GitHubToolset(ToolExecutor):
    """GitHub tools bound to one user's token. Nothing here can write to GitHub."""

    def __init__(self, http_client: httpx.AsyncClient, token: str) -> None:
        self._http = http_client
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        self._handlers: dict[str, Callable[[dict[str, Any]], Awaitable[Any]]] = {
            "github__get_me": self._get_me,
            "github__list_my_repositories": self._list_my_repositories,
            "github__search_repositories": self._search_repositories,
            "github__get_repository": self._get_repository,
            "github__list_issues": self._list_issues,
            "github__get_issue": self._get_issue,
            "github__list_pull_requests": self._list_pull_requests,
            "github__list_commits": self._list_commits,
            "github__get_file_contents": self._get_file_contents,
        }
        self._logger = get_logger(__name__)

    def list_tools(self) -> list[ToolDefinition]:
        """Return the GitHub tool definitions."""
        return TOOL_DEFINITIONS

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        """Run a GitHub tool and return compact JSON, or an error the model can act on."""
        handler = self._handlers.get(name)
        if handler is None:
            return ToolResult(output=f"Unknown tool '{name}'.", is_error=True)
        try:
            result = await handler(arguments)
        except KeyError as error:
            return ToolResult(output=f"Missing required argument {error}.", is_error=True)
        except httpx.HTTPStatusError as error:
            status = error.response.status_code
            self._logger.info("GitHub tool failed | tool=%s status=%s", name, status)
            if status == 401:
                return ToolResult(output="GitHub rejected the token. Ask the user to reconnect GitHub in Setu.", is_error=True)
            if status == 404:
                return ToolResult(output="Not found, or the connected account cannot see it.", is_error=True)
            if status in {403, 429}:
                return ToolResult(output="GitHub refused the request (rate limit or missing permission).", is_error=True)
            return ToolResult(output=f"GitHub returned HTTP {status}.", is_error=True)
        except httpx.HTTPError as error:
            return ToolResult(output=f"Could not reach GitHub ({type(error).__name__}).", is_error=True)
        text = result if isinstance(result, str) else json.dumps(result, ensure_ascii=False, separators=(",", ":"))
        if len(text) > MAX_TOOL_OUTPUT_CHARS:
            text = text[:MAX_TOOL_OUTPUT_CHARS] + "\n...[output truncated]"
        return ToolResult(output=text)

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        response = await self._http.get(f"{GITHUB_API_URL}{path}", headers=self._headers, params=params)
        response.raise_for_status()
        return response.json()

    @staticmethod
    def _limit(arguments: dict[str, Any]) -> int:
        try:
            return max(1, min(int(arguments.get("limit") or 10), _MAX_LIMIT))
        except (TypeError, ValueError):
            return 10

    @staticmethod
    def _repo_path(arguments: dict[str, Any]) -> str:
        owner, repo = str(arguments["owner"]), str(arguments["repo"])
        if not _NAME_PATTERN.fullmatch(owner) or not _NAME_PATTERN.fullmatch(repo):
            raise KeyError("owner/repo (use plain names such as 'octocat' and 'hello-world')")
        return f"/repos/{owner}/{repo}"

    @staticmethod
    def _repo(raw: dict[str, Any]) -> dict[str, Any]:
        return {
            "full_name": raw.get("full_name"),
            "private": raw.get("private"),
            "description": raw.get("description"),
            "language": raw.get("language"),
            "stars": raw.get("stargazers_count"),
            "open_issues": raw.get("open_issues_count"),
            "default_branch": raw.get("default_branch"),
            "updated_at": raw.get("updated_at"),
            "url": raw.get("html_url"),
        }

    @staticmethod
    def _issue(raw: dict[str, Any]) -> dict[str, Any]:
        return {
            "number": raw.get("number"),
            "title": raw.get("title"),
            "state": raw.get("state"),
            "author": (raw.get("user") or {}).get("login"),
            "labels": [label.get("name") for label in raw.get("labels") or [] if isinstance(label, dict)],
            "comments": raw.get("comments"),
            "updated_at": raw.get("updated_at"),
            "url": raw.get("html_url"),
        }

    async def _get_me(self, _: dict[str, Any]) -> Any:
        me = await self._get("/user")
        return {key: me.get(key) for key in ("login", "name", "bio", "company", "public_repos", "followers", "html_url")}

    async def _list_my_repositories(self, arguments: dict[str, Any]) -> Any:
        repos = await self._get("/user/repos", {"sort": "updated", "per_page": self._limit(arguments)})
        return [self._repo(repo) for repo in repos]

    async def _search_repositories(self, arguments: dict[str, Any]) -> Any:
        found = await self._get("/search/repositories", {"q": arguments["query"], "per_page": self._limit(arguments)})
        return {"total": found.get("total_count"), "items": [self._repo(repo) for repo in found.get("items", [])]}

    async def _get_repository(self, arguments: dict[str, Any]) -> Any:
        repo = await self._get(self._repo_path(arguments))
        return {**self._repo(repo), "topics": repo.get("topics"), "forks": repo.get("forks_count"), "license": (repo.get("license") or {}).get("name")}

    async def _list_issues(self, arguments: dict[str, Any]) -> Any:
        params = {"state": arguments.get("state") or "open", "per_page": self._limit(arguments)}
        issues = await self._get(f"{self._repo_path(arguments)}/issues", params)
        return [self._issue(issue) for issue in issues if "pull_request" not in issue]

    async def _get_issue(self, arguments: dict[str, Any]) -> Any:
        path = f"{self._repo_path(arguments)}/issues/{int(arguments['number'])}"
        issue = await self._get(path)
        comments = await self._get(f"{path}/comments", {"per_page": 10}) if issue.get("comments") else []
        return {
            **self._issue(issue),
            "is_pull_request": "pull_request" in issue,
            "body": (issue.get("body") or "")[:_MAX_BODY_CHARS],
            "recent_comments": [
                {"author": (comment.get("user") or {}).get("login"), "body": (comment.get("body") or "")[:500]} for comment in comments
            ],
        }

    async def _list_pull_requests(self, arguments: dict[str, Any]) -> Any:
        params = {"state": arguments.get("state") or "open", "per_page": self._limit(arguments)}
        pulls = await self._get(f"{self._repo_path(arguments)}/pulls", params)
        return [
            {**self._issue(pull), "draft": pull.get("draft"), "head": (pull.get("head") or {}).get("ref"), "base": (pull.get("base") or {}).get("ref")}
            for pull in pulls
        ]

    async def _list_commits(self, arguments: dict[str, Any]) -> Any:
        params: dict[str, Any] = {"per_page": self._limit(arguments)}
        if arguments.get("branch"):
            params["sha"] = arguments["branch"]
        commits = await self._get(f"{self._repo_path(arguments)}/commits", params)
        return [
            {
                "sha": (commit.get("sha") or "")[:7],
                "message": ((commit.get("commit") or {}).get("message") or "").split("\n", 1)[0],
                "author": ((commit.get("commit") or {}).get("author") or {}).get("name"),
                "date": ((commit.get("commit") or {}).get("author") or {}).get("date"),
            }
            for commit in commits
        ]

    async def _get_file_contents(self, arguments: dict[str, Any]) -> Any:
        path = quote(str(arguments.get("path") or "").strip("/"), safe="/")
        if ".." in path.split("/"):
            raise KeyError("path (no '..' segments)")
        params = {"ref": arguments["ref"]} if arguments.get("ref") else None
        content = await self._get(f"{self._repo_path(arguments)}/contents/{path}", params)
        if isinstance(content, list):
            return [{"name": entry.get("name"), "type": entry.get("type"), "size": entry.get("size")} for entry in content]
        if content.get("encoding") != "base64":
            return f"{content.get('path')} is a {content.get('type')} and cannot be shown as text."
        raw = base64.b64decode(content.get("content") or "")
        try:
            return f"{content.get('path')}:\n{raw.decode('utf-8')}"
        except UnicodeDecodeError:
            return f"{content.get('path')} is a binary file ({content.get('size')} bytes)."
