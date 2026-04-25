# Cline Assessment Prompt

Paste this prompt into Cline to generate `cline_assessment.md`.

---

## PROMPT

You are doing a static code review of the Pressroom FastAPI application in `app/`. Your output will be read by Claude Code (not a human) so optimise for density, not readability. No prose introductions. No padding.

**Save your output as `cline_assessment.md` in the repository root.**

---

### What to assess

Review the following files in order. For each, report only genuine issues — bugs, broken logic, spec violations, security problems, or incomplete stubs that block runtime behaviour. Skip files with nothing to report.

**Priority 1 — core publish path (read all of these):**
- `app/routers/publish.py`
- `app/services/snapshot.py`
- `app/routers/preview.py`
- `app/services/pdf/pandoc_engine.py`
- `app/services/pdf/base.py`

**Priority 2 — auth and data layer:**
- `app/auth.py`
- `app/auth_store.py`
- `app/database.py`
- `app/routers/auth.py`

**Priority 3 — supporting services:**
- `app/services/template_resolver.py`
- `app/services/task_queue.py`
- `app/github.py`
- `app/config.py`
- `app/main.py`

**Priority 4 — remaining routers:**
- `app/routers/papers.py`
- `app/routers/status.py`
- `app/routers/templates.py`

Also read `docs/SPEC.md` sections 3, 7, 8, 9 to check for spec divergence. Do not read the whole spec — those sections only.

---

### Output format

Save as `cline_assessment.md` using **exactly** this structure:

```markdown
# Cline Assessment — {DATE}

## Blocking Issues
Issues that will cause a runtime crash or silent data corruption.

| File | Line | Issue | Severity |
|------|------|-------|----------|
| ... | ... | ... | CRITICAL/HIGH |

## Spec Violations
Code that diverges from docs/SPEC.md in a way that affects correctness.

| File | Spec Section | Expected | Actual |
|------|-------------|----------|--------|

## Security Issues
| File | Line | Issue |
|------|------|-------|

## Incomplete Stubs
Functions that are still `pass` or raise NotImplemented and are called by active code paths.

| File | Function | Called From |
|------|----------|------------|

## Inconsistencies
Logic errors, mismatched interfaces, or internal contradictions that don't fit above categories.

| File | Line | Description |
|------|------|-------------|

## Summary
- Blocking: {N}
- Spec violations: {N}  
- Security: {N}
- Stubs blocking active paths: {N}
- Inconsistencies: {N}
- Verdict: READY_TO_TEST / NEEDS_FIXES / BROKEN
```

**Rules:**
- Every row must have a file path relative to repo root
- Line numbers are required for Blocking and Security rows; best-effort for others
- Do not report stale TODO comments in docstrings as issues
- Do not report abstract base class `pass` bodies as stubs
- Do not report missing tests as issues
- If a section has no findings, write `None.` under the table
- Keep issue descriptions under 120 characters
