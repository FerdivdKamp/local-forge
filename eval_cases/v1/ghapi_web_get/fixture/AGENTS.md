# Fixture rules

Use ghapi 2.1.4 and the Python standard library. Do not use PyGithub or make a real GitHub request. Add a mock based test and run it. Look up the official online ghapi documentation before coding.

## Windows PowerShell commands

Commands run in Windows PowerShell 5.1.

- Do not use Bash syntax: no heredocs (`<<`), `&&`, or Bash redirection idioms.
- Do not recursively list the workspace, `.git`, or installed packages. Inspect only the specific file, signature, or source range needed.
- Keep command output short and targeted. After identifying the relevant ghapi API, implement the function and mock test immediately.
- If a command fails, read the PowerShell error, use a simpler PowerShell command, and continue. Do not repeat the failed Bash-style command.
- Prefer `apply_patch` for repository edits. If writing text from PowerShell is necessary, use `Set-Content -LiteralPath <path> -Value <content> -Encoding utf8`.

## Documentation fallback and stop condition

If web access is unavailable, state that in the final response and proceed using
the installed ghapi 2.1.4 package. Do not inspect MCP resources or plugins, and
make at most one documentation or network attempt. Once `GhApi` and
`client.issues.get(issue_number)` are identified, immediately implement the
function, add its mock test, and run it.
