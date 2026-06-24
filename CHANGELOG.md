## [v0.4.0] - 2026-06-23
### Added
- `trace` command to inspect and display the detailed steps of the last agent run (show what tools were called, their inputs, and results)
- `verbose` mode toggle to stream agent steps live as they execute (replaces the spinner with real-time output during `suggest` and `changelog` operations)
- `edit_file` tool for the agent to make precise edits to existing files by replacing specific text spans (complements `write_file` for partial updates)
- `changelog` command to automatically generate and update a CHANGELOG.md file by analyzing git history between tags
- Iteration limit warning that displays when an agent run hits the maximum iteration limit before completing, alerting users that the task may be incomplete

### Changed
- CLI code reorganized from a single monolithic module into separate command modules (account_cmds, git_cmds, agent_cmds, app_cmds) and UI modules (banner, spinner, theme, output) for better maintainability

## [v0.3.2] - 2026-06-20
### Added
- Error handling for unknown tools—agent now returns an error result instead of crashing when the model requests a non-existent tool
- Exception handling for tool execution—tool errors are caught and reported back to the model as error results
- `outbox` command to display committed but unpushed commits, showing how many commits are ahead of the upstream branch
- Input validation and security checks for `read_file` and `list_directory` tools to prevent directory traversal attacks
- Enhanced tool descriptions with detailed documentation of parameters and usage examples
- Support for `required` field in tool schemas for better validation
- Comprehensive pytest test suite covering agent tool execution, config management, git diff parsing, LLM error handling, and tool schemas
- GitHub Actions CI workflow for automated testing across Python 3.10–3.13

### Changed
- Tool schema generation now includes required field declarations
- Improved error messages throughout the CLI for better user guidance
- Tool functions now validate inputs for security and proper error reporting

## [v0.3.1] - 2026-06-20

## [v0.3.0] - 2026-06-20

## [v0.2.1] - 2026-06-20
