# Conversation Stash

Summarize the current conversation and save to `docs/stashes/`.

## Steps

1. Determine today's date and the next available sequence number by scanning existing files in `docs/stashes/` matching `{YYYY-MM-DD}-*`.

2. Collect from the conversation:
   - **Branch** and **commit range** touched in this session
   - **Key changes**: files added/modified, bugs fixed, features implemented
   - **Verification status**: test count, ruff, HPC results
   - **Open risks / TODOs / blockers**
   - **Next steps** agreed with the user

3. Write a markdown file to `docs/stashes/{YYYY-MM-DD}-{SEQ}-{slug}.md` using this template:

```markdown
# {Title}

**Date:** {YYYY-MM-DD}
**Branch:** {branch}
**Status:** {one-line status}

---

## Key Changes

| File | Change |
|------|--------|
| ... | ... |

## Verification

- pytest: {N} passed
- ruff: {clean/issues}
- HPC: {result if applicable}

## Open Risks / TODOs

- ...

## Next Steps

1. ...
```

4. Keep it concise — the stash is a quick-reference snapshot, not a narrative.

5. Update project memory files if phase status or other persistent state has changed.

6. Do NOT commit the stash file — the user will decide when to commit.
