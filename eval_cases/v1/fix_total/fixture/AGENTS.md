# Fixture rules

Use the Python standard library and `unittest`. Run the visible tests before finishing.

## Windows PowerShell editing

Commands run in Windows PowerShell 5.1.

- Prefer an `apply_patch` tool for source edits when one is available.
- Do not use `>`, `>>`, `Out-File`, `echo`, or Bash syntax such as `&&` to
  write source files.
- If writing a text file from PowerShell, use `Set-Content -LiteralPath <path>
  -Value <content> -Encoding utf8`.
- Run the relevant test immediately after each edit.
- If Python reports null bytes or an encoding error, rewrite the affected file
  as UTF-8 before continuing.
