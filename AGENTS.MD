# Project rules

- Read README.md before implementing changes.
- Use `ghapi` for GitHub API access.
- Do not use PyGithub.
- V1 must not push branches or create pull requests.
- Keep abstractions small and focused.
- Do not add dependencies without checking `pyproject.toml`.

## Execution discipline

- Work in short cycles: inspect only what is needed, implement the smallest complete change, then run the relevant test.
- If a required capability is unavailable, record that fact and proceed using available local evidence when the task can still be completed. Do not repeatedly search for the unavailable capability.
- After a failed command, use its error to choose a simpler alternative; do not repeat the same failing approach.
- Do not enumerate unrelated tools, plugins, directories, or package files. Stop investigating once the task has enough information to implement and verify the change.
