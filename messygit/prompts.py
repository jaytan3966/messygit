COMMIT_SYSTEM_PROMPT = """You write git commit messages in Conventional Commits format.

Output exactly one line, no markdown, no quotes, no explanation.

Format: type(scope): description

Types (pick one): feat, fix, docs, style, refactor, test, chore
- scope: short noun for the area changed (omit only if no sensible scope exists)
- description: imperative mood, lowercase, no trailing period, max 72 characters for the full line

Base the message only on the staged diff the user provides."""

## TODO: optimize the prompt to be more specific to the user's changes
## TODO: summarize large refactors into smaller commits with more descriptive messages (15000 tokens threshold)

def build_user_prompt(staged_diff: str) -> str:
    return (
        "Here is the output of `git diff --staged`. "
        "Propose the single best commit subject line:\n\n"
        f"{staged_diff}"
    )
