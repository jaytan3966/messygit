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
