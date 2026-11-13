# AGENTS.md conventions

Use these as design guidance, not a rigid schema.

## Standard

- `AGENTS.md` is standard Markdown with no required headings or fields.
- Put a file at repository root when its guidance applies repository-wide.
- Use nested files for materially different subtree guidance.
- Treat nesting conservatively: tools differ between nearest-file precedence and
  combining multiple files, so root and nested instructions should not conflict.
- Keep guidance current and repository-specific.

Primary sources:

- [agents.md](https://agents.md/)
- [agents.md source and FAQ](https://github.com/agentsmd/agents.md)
- [OpenAI Codex AGENTS.md guidance](https://developers.openai.com/codex/guides/agents-md)

## Useful evidence-backed content

Agents most often benefit from:

- project overview and runtime boundary
- authoritative setup/build/test commands
- focused test syntax and completion gates
- important source, test, generated, and configuration paths
- repository-specific conventions and architecture constraints
- security, privacy, secret, dependency, migration, and release boundaries
- pointers to durable human documentation

These are choices, not mandatory sections. Omit any category that adds no
project-specific operational value.

## Quality test

For each line, ask:

1. Is it verified by current repository evidence?
2. Does it change how an agent should work here?
3. Is `AGENTS.md` the narrowest durable source, or should it link elsewhere?
4. Can an agent tell when the instruction is satisfied?
5. Will it remain accurate when routine implementation details change?

Delete lines that fail these tests.

## Example patterns

Representative public files show useful patterns, but their commands and rules
must never be copied without target-repository evidence:

- [agents.md examples](https://agents.md/#examples)
- [Apache Airflow AGENTS.md](https://github.com/apache/airflow/blob/main/AGENTS.md)
- [Temporal Java SDK AGENTS.md](https://github.com/temporalio/sdk-java/blob/master/AGENTS.md)

Prefer their structure—operational commands, maps, boundaries, and references—
over their repository-specific content.
