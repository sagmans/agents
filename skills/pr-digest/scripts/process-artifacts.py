#!/usr/bin/env python3
"""Normalize fetched pr-digest artifacts into agent-ready review inputs.

This script is deterministic plumbing. It does not decide whether a PR is ready
or whether a reviewer is right; it turns GitHub payloads into compact JSON and
Markdown so agents do not write one-off parsers during a digest.
"""

from __future__ import annotations

import argparse
import html
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, cast

from process_artifacts_classify import (
    check_status,
    issue_comment_status,
    text_field,
    thread_category,
)
from process_artifacts_render import (
    processed_index,
    processed_paths,
    write_processed_outputs,
)

SNIPPET_CHARS = 320


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def as_list(value: Any) -> list[Any]:
    return cast(list[Any], value) if isinstance(value, list) else []


def object_map(value: Any) -> dict[str, Any]:
    return cast(dict[str, Any], value) if isinstance(value, dict) else {}


def object_rows(value: Any) -> list[dict[str, Any]]:
    return [cast(dict[str, Any], item) for item in as_list(value) if isinstance(item, dict)]


def first_present(*values: Any) -> Any:
    for value in values:
        if value not in (None, ""):
            return value
    return ""


def login_from_user(value: Any) -> str:
    return text_field(object_map(value), "login")


def strip_body(value: Any, limit: int = SNIPPET_CHARS) -> str:
    text = value if isinstance(value, str) else ""
    text = re.sub(r"<!--.*?-->", " ", text, flags=re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def first_thread_comment(thread: dict[str, Any]) -> dict[str, Any]:
    comments = thread_comments(thread)
    return comments[0] if comments else {}


def thread_comments(thread: dict[str, Any]) -> list[dict[str, Any]]:
    comments = object_map(thread.get("comments")).get("nodes")
    return object_rows(comments)


def thread_location(thread: dict[str, Any]) -> str:
    line = first_present(thread.get("line"), thread.get("originalLine"))
    return f"{text_field(thread, 'path')}:{line}"


def normalize_checks(workdir: Path) -> list[dict[str, Any]]:
    return [normalize_check(check) for check in object_rows(load_json(workdir / "checks.json", []))]


def normalize_check(check: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": check_status(check),
        "name": text_field(check, "name"),
        "workflow": text_field(check, "workflow"),
        "state": text_field(check, "state"),
        "bucket": text_field(check, "bucket"),
        "link": text_field(check, "link"),
        "notes": text_field(check, "description"),
    }


def normalize_comments(
    workdir: Path, thread_comment_urls: set[str], thread_comment_ids: set[str]
) -> dict[str, Any]:
    issue_rows = normalize_issue_comments(load_json(workdir / "issue-comments.json", []))
    review_rows = normalize_review_submissions(load_json(workdir / "reviews.json", []))
    inline_rows, duplicate_count = normalize_inline_comments(
        load_json(workdir / "review-comments.json", []),
        thread_comment_urls,
        thread_comment_ids,
    )
    return comment_result(issue_rows, review_rows, inline_rows, duplicate_count)


def normalize_issue_comments(comments: Any) -> list[dict[str, Any]]:
    return [issue_comment_row(comment) for comment in object_rows(comments)]


def issue_comment_row(comment: dict[str, Any]) -> dict[str, Any]:
    author = login_from_user(comment.get("user"))
    body = strip_body(comment.get("body"))
    status = issue_comment_status(author, body)
    return {
        "status": status,
        "author": author,
        "location": text_field(comment, "html_url"),
        "digest": body,
        "needed_action": "agent triage" if status != "INFORMATIONAL" else "none",
    }


def normalize_review_submissions(reviews: Any) -> list[dict[str, Any]]:
    return [review_submission_row(review) for review in object_rows(reviews)]


def review_submission_row(review: dict[str, Any]) -> dict[str, Any]:
    state = text_field(review, "state")
    body = strip_body(review.get("body"))
    return {
        "status": "REVIEW_SUBMISSION",
        "author": login_from_user(review.get("user")),
        "location": text_field(review, "html_url"),
        "digest": f"{state}: {body}".strip(),
        "needed_action": "agent triage" if state not in {"COMMENTED", "APPROVED"} else "none",
    }


def normalize_inline_comments(
    comments: Any, thread_urls: set[str], thread_ids: set[str]
) -> tuple[list[dict[str, Any]], int]:
    rows: list[dict[str, Any]] = []
    duplicate_count = 0
    for comment in object_rows(comments):
        if is_thread_comment(comment, thread_urls, thread_ids):
            duplicate_count += 1
            continue
        rows.append(inline_comment_row(comment))
    return rows, duplicate_count


def is_thread_comment(
    comment: dict[str, Any], thread_urls: set[str], thread_ids: set[str]
) -> bool:
    return (
        text_field(comment, "html_url") in thread_urls
        or text_field(comment, "node_id") in thread_ids
    )


def inline_comment_row(comment: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": "INLINE_STANDALONE",
        "author": login_from_user(comment.get("user")),
        "location": text_field(comment, "html_url"),
        "path": text_field(comment, "path"),
        "line": first_present(comment.get("line"), comment.get("original_line")),
        "digest": strip_body(comment.get("body")),
        "needed_action": "agent triage",
    }


def comment_result(
    issue_rows: list[dict[str, Any]],
    review_rows: list[dict[str, Any]],
    inline_rows: list[dict[str, Any]],
    duplicate_count: int,
) -> dict[str, Any]:
    return {
        "issue": issue_rows,
        "reviews": review_rows,
        "standalone_inline": inline_rows,
        "deduped_inline_count": duplicate_count,
        "informational_counts": informational_counts(issue_rows),
    }


def informational_counts(issue_rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter(
        row["author"] for row in issue_rows if row["status"] == "INFORMATIONAL"
    )
    return dict(sorted(counts.items()))


def normalize_threads(workdir: Path) -> dict[str, Any]:
    raw_threads = object_rows(load_json(workdir / "review-threads.json", []))
    rows = [thread_row(thread) for thread in raw_threads]
    open_rows, resolved_rows = partition_threads(rows)
    urls, ids = collect_thread_comment_refs(raw_threads)
    return {
        "counts": thread_counts(raw_threads, open_rows, resolved_rows),
        "unresolved": open_rows,
        "resolved": resolved_rows,
        "groups": group_thread_rows(open_rows),
        "thread_comment_urls": sorted(urls),
        "thread_comment_ids": sorted(ids),
    }


def thread_row(thread: dict[str, Any]) -> dict[str, Any]:
    first = first_thread_comment(thread)
    body = strip_body(first.get("body"))
    return {
        "id": text_field(thread, "id"),
        "url": text_field(first, "url"),
        "isResolved": bool(thread.get("isResolved")),
        "isOutdated": bool(thread.get("isOutdated")),
        "path": text_field(thread, "path"),
        "line": first_present(thread.get("line"), thread.get("originalLine")),
        "location": thread_location(thread),
        "reviewer": login_from_user(first.get("author")),
        "category": thread_category(body),
        "digest": body,
        "comments": len(thread_comments(thread)),
    }


def partition_threads(
    rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    open_rows: list[dict[str, Any]] = []
    resolved_rows: list[dict[str, Any]] = []
    for row in rows:
        (resolved_rows if row["isResolved"] else open_rows).append(row)
    return open_rows, resolved_rows


def collect_thread_comment_refs(
    threads: list[dict[str, Any]],
) -> tuple[set[str], set[str]]:
    urls: set[str] = set()
    ids: set[str] = set()
    for thread in threads:
        add_comment_refs(thread_comments(thread), urls, ids)
    return urls, ids


def add_comment_refs(
    comments: list[dict[str, Any]], urls: set[str], ids: set[str]
) -> None:
    for comment in comments:
        add_if_present(urls, text_field(comment, "url"))
        add_if_present(ids, text_field(comment, "id"))


def add_if_present(values: set[str], value: str) -> None:
    if value:
        values.add(value)


def thread_counts(
    raw_threads: list[dict[str, Any]],
    open_rows: list[dict[str, Any]],
    resolved_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "total": len(raw_threads),
        "resolved": len(resolved_rows),
        "unresolved": len(open_rows),
        "unresolved_outdated": sum(1 for row in open_rows if row["isOutdated"]),
        "unresolved_by_reviewer": dict(
            sorted(Counter(row["reviewer"] for row in open_rows).items())
        ),
    }


def group_thread_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped = collect_thread_groups(rows)
    return [
        thread_group_row(reviewer, category, items)
        for (reviewer, category), items in sorted_thread_groups(grouped)
    ]


def collect_thread_groups(
    rows: list[dict[str, Any]],
) -> dict[tuple[str, str], list[dict[str, Any]]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(row["reviewer"], row["category"])].append(row)
    return grouped


def sorted_thread_groups(
    grouped: dict[tuple[str, str], list[dict[str, Any]]],
) -> list[tuple[tuple[str, str], list[dict[str, Any]]]]:
    return sorted(
        grouped.items(), key=lambda item: (-len(item[1]), item[0][0], item[0][1])
    )


def thread_group_row(
    reviewer: str, category: str, items: list[dict[str, Any]]
) -> dict[str, Any]:
    return {
        "reviewer": reviewer,
        "category": category,
        "count": len(items),
        "ids": [item["id"] for item in items],
        "locations": [item["location"] for item in items],
    }


def normalize_pr(workdir: Path) -> dict[str, Any]:
    pr_data = object_map(load_json(workdir / "pr.json", {}))
    coords_data = object_map(load_json(workdir / "coords.json", {}))
    files = object_rows(pr_data.get("files"))
    commits = object_rows(pr_data.get("commits"))
    fields = pr_fields(pr_data, coords_data, files)
    fields.update({"files": pr_files(files), "commits": pr_commits(commits)})
    return fields


def pr_fields(
    pr: dict[str, Any], coords: dict[str, Any], files: list[dict[str, Any]]
) -> dict[str, Any]:
    return {
        "owner": first_present(coords.get("owner")),
        "repo": first_present(coords.get("repo")),
        "number": first_present(coords.get("number"), pr.get("number")),
        "url": first_present(pr.get("url"), coords.get("url")),
        "title": text_field(pr, "title"),
        "body": text_field(pr, "body"),
        "author": login_from_user(pr.get("author")),
        "state": text_field(pr, "state"),
        "isDraft": bool(pr.get("isDraft")),
        "headRefName": first_present(pr.get("headRefName"), coords.get("headRefName")),
        "baseRefName": first_present(pr.get("baseRefName"), coords.get("baseRefName")),
        "mergeable": text_field(pr, "mergeable"),
        "reviewDecision": text_field(pr, "reviewDecision"),
        "changedFiles": first_present(pr.get("changedFiles"), len(files)),
        "additions": first_present(pr.get("additions"), 0),
        "deletions": first_present(pr.get("deletions"), 0),
    }


def pr_files(files: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [pr_file_row(item) for item in files]


def pr_file_row(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "path": text_field(item, "path"),
        "changeType": text_field(item, "changeType"),
        "additions": first_present(item.get("additions"), 0),
        "deletions": first_present(item.get("deletions"), 0),
    }


def pr_commits(commits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [pr_commit_row(item) for item in commits]


def pr_commit_row(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "oid": text_field(item, "oid"),
        "headline": text_field(item, "messageHeadline"),
        "body": text_field(item, "messageBody"),
    }


def coverage(workdir: Path, data: dict[str, Any]) -> dict[str, Any]:
    gaps = coverage_gaps(workdir)
    return {
        "metadata": bool(data["pr"].get("url")),
        "diff": (workdir / "diff.patch").exists(),
        "commits": bool(data["pr"].get("commits")),
        "comments": True,
        "threads": True,
        "checks": not (workdir / "checks.failed").exists(),
        "gaps": gaps,
    }


def coverage_gaps(workdir: Path) -> list[str]:
    gaps: list[str] = []
    append_check_gap(workdir, gaps)
    append_thread_gap(workdir, gaps)
    return gaps


def append_check_gap(workdir: Path, gaps: list[str]) -> None:
    if (workdir / "checks.failed").exists():
        gaps.append("checks.failed present; gh pr checks output may be partial")


def append_thread_gap(workdir: Path, gaps: list[str]) -> None:
    gaps_file = workdir / "thread-pagination-gaps.txt"
    if gaps_file.exists() and gaps_file.read_text(encoding="utf-8").strip():
        gaps.append("review thread comment pagination gaps recorded")


def process(workdir: Path) -> dict[str, str]:
    outdir = workdir / "processed"
    pr = normalize_pr(workdir)
    checks = normalize_checks(workdir)
    threads = normalize_threads(workdir)
    comments = normalize_comments(
        workdir, set(threads["thread_comment_urls"]), set(threads["thread_comment_ids"])
    )
    data = processed_data(workdir, pr, checks, threads, comments)
    paths = processed_paths(outdir)
    write_processed_outputs(paths, data)
    return processed_index(workdir, paths)


def processed_data(
    workdir: Path,
    pr: dict[str, Any],
    checks: list[dict[str, Any]],
    threads: dict[str, Any],
    comments: dict[str, Any],
) -> dict[str, Any]:
    data: dict[str, Any] = {
        "pr": pr,
        "checks": checks,
        "threads": public_thread_data(threads),
        "comments": comments,
    }
    data["coverage"] = coverage(workdir, data)
    return data


def public_thread_data(threads: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in threads.items()
        if key not in {"thread_comment_urls", "thread_comment_ids"}
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Process pr-digest artifacts into agent-ready files"
    )
    parser.add_argument("workdir", type=Path)
    args = parser.parse_args()
    result = process(args.workdir)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
