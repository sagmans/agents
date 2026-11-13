"""Render normalized pr-digest data into compact Markdown and triage templates.

Keeping Markdown table generation and processed output writing separate from
artifact ingestion keeps both modules focused and under complexity thresholds.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


def write_private(path: Path, content: str) -> None:
    """Persist processed output atomically with owner-only permissions."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(content)
        os.chmod(tmp_path, 0o600)
        os.replace(tmp_path, path)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise


def write_private_json(path: Path, value: Any) -> None:
    """Serialize JSON deterministically before writing with restricted permissions."""
    write_private(path, json.dumps(value, indent=2, sort_keys=True) + "\n")


def single_line(value: Any) -> str:
    """Flatten line breaks so untrusted PR text cannot inject Markdown headers."""
    text = "" if value is None else str(value)
    return text.replace("\r\n", " ").replace("\r", " ").replace("\n", " ")


def md(value: Any) -> str:
    """Escape Markdown table separators and line breaks cleanly per cell."""
    return single_line(value).replace("|", "\\|")


def markdown_table(headers: list[str], rows: list[list[Any]]) -> str:
    """Render a GFM Markdown table from string headers and row cells."""
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    lines.extend("| " + " | ".join(md(cell) for cell in row) + " |" for row in rows)
    return "\n".join(lines)


def render_checks_md(checks: list[dict[str, Any]]) -> str:
    """Render normalized check runs as a summary Markdown table."""
    rows: list[list[Any]] = [
        [c["status"], c["name"], c["workflow"], c["state"], c["link"], c["notes"]]
        for c in checks
    ]
    return (
        "# Checks\n\n"
        + markdown_table(
            ["Status", "Check", "Workflow", "State", "Link", "Notes"],
            rows,
        )
        + "\n"
    )


def comment_table_row(source: str, row: dict[str, Any]) -> list[Any]:
    """Flatten one comment record into table columns."""
    return [
        source,
        row["status"],
        row["author"],
        row["location"],
        row["digest"],
        row["needed_action"],
    ]


def comment_table_rows(comments: dict[str, Any]) -> list[list[Any]]:
    """Collect comment rows across issue, review, and inline sources."""
    rows: list[list[Any]] = []
    for source in ("issue", "reviews", "standalone_inline"):
        rows.extend(comment_table_row(source, row) for row in comments[source])
    return rows


def informational_summary(counts: dict[str, int]) -> str:
    """Summarize informational comment volume by author."""
    return ", ".join(f"{author}: {count}" for author, count in counts.items()) or "0"


def render_comments_md(comments: dict[str, Any]) -> str:
    """Render PR comment digest Markdown with deduplication counts."""
    rows = comment_table_rows(comments)
    info = informational_summary(comments["informational_counts"])
    return (
        "# Comments\n\n"
        + markdown_table(
            ["Source", "Status", "Author", "Location", "Digest", "Needed action"],
            rows,
        )
        + f"\n\nDeduped inline comments already represented by threads: {comments['deduped_inline_count']}\n"
        + f"Informational issue comments: {info}\n"
    )


def thread_summary(counts: dict[str, Any]) -> str:
    """Render aggregate review-thread counts."""
    return (
        "# Review threads\n\n"
        f"Total: {counts['total']} · Resolved: {counts['resolved']} · Unresolved: {counts['unresolved']} · "
        f"Unresolved outdated: {counts['unresolved_outdated']}\n\n"
    )


def thread_groups_md(groups: list[dict[str, Any]]) -> str:
    """Render grouped unresolved review threads by reviewer and category."""
    rows: list[list[Any]] = [
        [g["count"], g["reviewer"], g["category"], ", ".join(g["ids"])] for g in groups
    ]
    return "## Unresolved groups\n\n" + markdown_table(
        ["Count", "Reviewer", "Category", "Thread ids"],
        rows,
    )


def thread_table_row(row: dict[str, Any]) -> list[Any]:
    """Flatten one unresolved review thread for triage tabular output."""
    return [
        "OUTDATED" if row["isOutdated"] else "OPEN_NEEDS_TRIAGE",
        row["id"],
        row["url"],
        row["location"],
        row["reviewer"],
        row["category"],
        row["digest"],
    ]


def thread_rows_md(rows: list[dict[str, Any]]) -> str:
    """Render detailed table of all unresolved threads."""
    table_rows = [thread_table_row(row) for row in rows]
    headers = ["Status", "Thread", "URL", "File/line", "Reviewer", "Category", "Digest"]
    return "\n\n## Unresolved threads\n\n" + markdown_table(headers, table_rows) + "\n"


def render_threads_md(threads: dict[str, Any]) -> str:
    """Render full review-threads Markdown artifact."""
    return (
        thread_summary(threads["counts"])
        + thread_groups_md(threads["groups"])
        + thread_rows_md(threads["unresolved"])
    )


def append_coverage_gaps(text: str, gaps: Any) -> str:
    """Append partial-fetch warnings when artifact acquisition hit incomplete pages."""
    return text + "; gaps: " + "; ".join(gaps) if gaps else text


def coverage_text(coverage_data: dict[str, Any]) -> str:
    """Format fetched sections and gap notices cleanly."""
    text = ", ".join(key for key, ok in coverage_data.items() if ok is True)
    return append_coverage_gaps(text, coverage_data.get("gaps"))


def pr_digest_header(pr: dict[str, Any], coverage_data: dict[str, Any]) -> str:
    """Render top-level PR metadata summary section."""
    return (
        f"# Processed PR digest inputs: {single_line(pr['owner'])}/{single_line(pr['repo'])}#{single_line(pr['number'])}\n\n"
        "## PR\n\n"
        f"- URL: {single_line(pr['url'])}\n"
        f"- Title: {single_line(pr['title'])}\n"
        f"- Head/base: `{single_line(pr['headRefName'])}` into `{single_line(pr['baseRefName'])}`\n"
        f"- State: {single_line(pr['state'])} · Draft: {pr['isDraft']} · Mergeable: {single_line(pr['mergeable'])} · Review decision: {single_line(pr['reviewDecision'])}\n"
        f"- Read coverage: {single_line(coverage_text(coverage_data))}\n\n"
    )


def development_shape_md(pr: dict[str, Any]) -> str:
    """Render changed-file additions and deletions overview."""
    rows: list[list[Any]] = [
        [f["path"], f["changeType"], f["additions"], f["deletions"]]
        for f in pr["files"]
    ]
    return (
        "## Development shape\n\n"
        f"- Changed files: {pr['changedFiles']} · Additions: {pr['additions']} · Deletions: {pr['deletions']}\n\n"
        + markdown_table(["File", "Change", "+", "-"], rows)
        + "\n\n"
    )


def commits_md(pr: dict[str, Any]) -> str:
    """Render compact commit SHA and headline list."""
    rows: list[list[Any]] = [
        [commit["oid"][:7], commit["headline"]] for commit in pr["commits"]
    ]
    return "## Commits\n\n" + markdown_table(["Commit", "Headline"], rows) + "\n\n"


def check_count(checks: list[dict[str, Any]], status: str) -> int:
    """Count check entries matching `status`."""
    return sum(1 for check in checks if check["status"] == status)


def check_signals_md(checks: list[dict[str, Any]]) -> str:
    """Summarize failing and pending checks above the detailed table."""
    return (
        "## Check signals\n\n"
        f"- Failed checks: {check_count(checks, 'FAIL')}\n"
        f"- Pending checks: {check_count(checks, 'PENDING')}\n\n"
    )


def render_digest_input_md(data: dict[str, Any]) -> str:
    """Assemble combined PR digest Markdown document for agent consumption."""
    return (
        pr_digest_header(data["pr"], data["coverage"])
        + development_shape_md(data["pr"])
        + commits_md(data["pr"])
        + check_signals_md(data["checks"])
        + render_checks_md(data["checks"])
        + "\n"
        + render_comments_md(data["comments"])
        + "\n"
        + render_threads_md(data["threads"])
    )


def triage_template_row(row: dict[str, Any]) -> dict[str, Any]:
    """Build one editable triage candidate entry defaulting to stale/invalid."""
    return {
        "id": row["id"],
        "status": "STALE_INVALID_OR_ADDRESSED_ONLY",
        "evidence": "",
        "reviewer": row["reviewer"],
        "path": row["path"],
        "line": row["line"],
        "category": row["category"],
        "digest": row["digest"],
    }


def triage_template(threads: dict[str, Any]) -> list[dict[str, Any]]:
    """Build candidate template entries for non-outdated unresolved threads."""
    return [
        triage_template_row(row)
        for row in threads["unresolved"]
        if not row["isOutdated"]
    ]


def processed_paths(outdir: Path) -> dict[str, Path]:
    """Return output artifact paths under `outdir`."""
    return {
        "reportData": outdir / "report-data.json",
        "checks": outdir / "checks.md",
        "comments": outdir / "comments.md",
        "threads": outdir / "threads.md",
        "digestInput": outdir / "digest-input.md",
        "triageTemplate": outdir / "triage-candidates.template.json",
        "emptyTriage": outdir / "triage-candidates.empty.json",
    }


def write_processed_outputs(
    paths: dict[str, Path],
    data: dict[str, Any],
) -> None:
    """Write every normalized JSON and Markdown artifact atomically with 0600 mode."""
    write_private_json(paths["reportData"], data)
    write_private(paths["checks"], render_checks_md(data["checks"]))
    write_private(paths["comments"], render_comments_md(data["comments"]))
    write_private(paths["threads"], render_threads_md(data["threads"]))
    write_private(paths["digestInput"], render_digest_input_md(data))
    write_private_json(paths["triageTemplate"], triage_template(data["threads"]))
    write_private_json(paths["emptyTriage"], [])


def processed_index(workdir: Path, paths: dict[str, Path]) -> dict[str, str]:
    """Serialize output file index returned on stdout by `process-artifacts.py`."""
    result = {key: str(path) for key, path in paths.items()}
    result["workdir"] = str(workdir)
    return result
