"""Classify pr-digest analyzer signals without inline lambdas.

Codacy can misparse top-level lambda matchers as invalid returns, so these small
predicates stay named and importable while keeping the main processor focused on
artifact normalization.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

CHECK_STATUS_RULES: tuple[tuple[str, set[str], set[str]], ...] = (
    ("PASS", {"pass"}, {"success", "passed"}),
    (
        "FAIL",
        {"fail"},
        {"failure", "failed", "error", "cancelled", "timed_out", "action_required"},
    ),
    (
        "PENDING",
        {"pending", "expected"},
        {"pending", "queued", "in_progress", "waiting", "requested"},
    ),
    ("SKIPPED", {"skipping", "skipped"}, {"skipped", "neutral"}),
)
ACTION_SUMMARY_TOKENS = (
    "action required",
    "action_required",
    "not up to standards",
    "failed",
    "blocking issues",
)
REVIEW_SUMMARY_TOKENS = ("issue", "bug", "medium", "high", "low risk")
REVIEW_BOT_TOKENS = ("codacy", "qodo", "deepsource")
ThreadMatcher = Callable[[str, str], bool]


def contains_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(needle in text for needle in needles)


def text_field(mapping: dict[str, Any], key: str) -> str:
    value = mapping.get(key)
    return value if isinstance(value, str) else ""


def check_status(check: dict[str, Any]) -> str:
    bucket = text_field(check, "bucket").lower()
    state = text_field(check, "state").lower()
    for status, buckets, states in CHECK_STATUS_RULES:
        if bucket in buckets or state in states:
            return status
    return "UNKNOWN"


def issue_comment_status(author: str, body: str) -> str:
    lower = body.lower()
    if contains_any(lower, ACTION_SUMMARY_TOKENS):
        return "ACTION_SUMMARY"
    if is_review_summary(author, lower):
        return "REVIEW_SUMMARY"
    return "INFORMATIONAL"


def is_review_summary(author: str, lower_body: str) -> bool:
    return contains_any(author.lower(), REVIEW_BOT_TOKENS) and contains_any(
        lower_body, REVIEW_SUMMARY_TOKENS
    )


def thread_category(body: str) -> str:
    lower = body.lower()
    return (
        complexity_category(body, lower)
        or matched_thread_category(body, lower)
        or "review"
    )


def complexity_category(body: str, lower: str) -> str:
    if "cyclomatic complexity" not in lower:
        return ""
    match = re.search(r"`([^`]+)` has a cyclomatic complexity of\s*([0-9]+)", body)
    return f"complexity:{match.group(1)}={match.group(2)}" if match else "complexity"


def is_no_implicit_globals(body: str, _lower: str) -> bool:
    return body.startswith("Unexpected function declaration")


def is_no_explicit_any(body: str, lower: str) -> bool:
    return body.startswith("Unexpected any") or " as any" in lower


def is_empty_method(body: str, _lower: str) -> bool:
    return body.startswith("Unexpected empty method")


def is_control_regex(_body: str, lower: str) -> bool:
    return "control character" in lower and "regular expression" in lower


def is_require_unicode_regexp(_body: str, lower: str) -> bool:
    return "use the 'u' flag" in lower or 'use the "u" flag' in lower


def is_no_use_before_define(_body: str, lower: str) -> bool:
    return "used before it was defined" in lower


def is_locale_dependent_format(body: str, lower: str) -> bool:
    return "toLocaleString" in body or "locale-dependent" in lower


def is_array_guard(_body: str, lower: str) -> bool:
    return "spreading a non-iterable" in lower or "non-array" in lower


def is_render_failure_isolation(_body: str, lower: str) -> bool:
    return "render" in lower and "try" in lower and "catch" in lower


def is_test_structure(_body: str, lower: str) -> bool:
    return "split" in lower and "test" in lower


THREAD_CATEGORY_RULES: tuple[tuple[str, ThreadMatcher], ...] = (
    ("lint:no-implicit-globals", is_no_implicit_globals),
    ("lint:no-explicit-any", is_no_explicit_any),
    ("lint:empty-method", is_empty_method),
    ("lint:no-control-regex", is_control_regex),
    ("lint:require-unicode-regexp", is_require_unicode_regexp),
    ("lint:no-use-before-define", is_no_use_before_define),
    ("reliability:locale-dependent-format", is_locale_dependent_format),
    ("reliability:array-guard", is_array_guard),
    ("reliability:render-failure-isolation", is_render_failure_isolation),
    ("test-structure", is_test_structure),
)


def matched_thread_category(body: str, lower: str) -> str:
    for category, matcher in THREAD_CATEGORY_RULES:
        if matcher(body, lower):
            return category
    return ""
