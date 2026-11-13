---
name: report-card
description: Use when closing finished work in Claude Code, to render the report card as one inline widget with live links.
---

# Report card

The [report card specification](references/report-card-spec.md) defines the
report card's sections, statuses, and evidence rules. This skill owns the
widget render, so every session draws the same card.

## Steps

1. **Pick the surface.** When `mcp__visualize__show_widget` exists in this
   session (load it with `ToolSearch` if it is deferred), use the widget.
   Otherwise do step 2, then render the report in a form that this surface
   renders inline, with clickable links and copyable commands, and stop.
2. **Collect fresh links.** Build every link from tool output in this
   session, at report time: `git remote get-url origin` for the repository
   URL, `git rev-parse HEAD` or the commit output for SHAs, the issue or PR
   URL that its API returned. A link from memory goes stale; leave it out.
   - Repository URL: rewrite the remote as `https://<host>/<owner>/<repo>`.
     Drop any `user:token@` part and the `.git` suffix, and turn the SSH form
     `git@host:owner/repo` into that https form. If you cannot, leave the link
     out.
   - Commit: `<repo>/commit/<sha>`. File at that commit:
     `<repo>/blob/<sha>/<path>`. Only for pushed commits.
   - Unpushed or local-only items have no web URL: list them in the
     Markdown block under the widget (step 6).
3. **Load the design rules.** Call `mcp__visualize__read_me` with
   `modules: ["mockup"]` once per session.
4. **Fill the template.** Read [`template.html`](template.html) and copy it.
   Replace every `{{...}}` placeholder. Repeat a tile, `<tr>`, checklist
   `<div>`, or link `<a>` per entry.
   - Escape `& < > "` in every placeholder value, because titles and API
     output are untrusted. An `href` takes only an `https://` URL.
   - Tables stay in the widget on purpose: the card must render as one
     unit.
   - Tiles: two to four real numbers (tests, files changed, commits, A/B
     score). Delete the tile row when there are none.
   - Status class per section: `ok` Done, `part` Partial, `block` Blocked,
     `none` None. The chip word is the status word. Next is `none` only when
     it has no item; any open item makes it `part` or `block`, per the global
     rule.
   - A section with nothing to report keeps its card and status `none`, with
     one short line instead of a table.
   - Overall chip: the worst section status, ignoring `none`; all `none`
     gives `none`. `OVERALL_CLASS` and `OVERALL_WORD` are that status's
     class and word. `OVERALL_ROLE` is `success` (for `ok` or `none`),
     `warning`, or `danger`.
   - Results chart: keep the bar rows only for real numbers. `BAR_PERCENT` is
     the value divided by the largest value, times 100. `BAR_COLOR` is
     `fill-success` for the result bar and `border-strong` for the baseline.
     Otherwise delete the caption and the grid.
   - `NOT_CHECKED`: what you did not verify, or `nothing`.
   - Link icons: `ticket` issue, `git-commit` commit, `git-pull-request` PR,
     `file-code` file, `book` doc, `external-link` other. `LINK_KIND` is that
     word.
   - Keep cell text short: one claim, one evidence summary with its SHA and
     source. Never put secrets, tokens, or personal data in the widget.
5. **Render.** Call `mcp__visualize__show_widget` with the title
   `report_card_<task_slug>`.
6. **Add the Markdown block under the widget.** Repeat the links as
   clickable Markdown, add local file paths as workspace links, and put full
   commands and long output in fenced blocks, so the reader can copy them.

Done when the report rendered (as the widget when the tool exists), each
section shows its status word, each Results claim has its evidence next to
it, and every link came from this session's tool output.
