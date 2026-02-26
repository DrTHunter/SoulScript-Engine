# tests/

Test suites for the agent runtime. Run from the project root.

## Test Files

| File | Checks | What It Tests |
|------|--------|---------------|
| `test_tools.py` | 58 | Echo, task inbox (add/next/ack/dry_run), continuation update, router, runtime policy, state store, journal store, allowlist enforcement |
| `test_memory.py` | 165 | Memory add/recall, scoping, duplicate detection, PII guard, search, update (versioning), soft delete, bulk delete, bulk add, validation, injector |
| `test_directives.py` | 107 | Parser, store search, store list/get, scoping, injector, directives tool, scoring, manifest generation, manifest save/load, manifest helpers, manifest diff, audit changes, changes action |
| `test_burst.py` | 63 | Burst runner types, tick execution, prompt assembly, structured output parsing, tool dispatch, memory flush, PII guard, task inbox burst gating (allowlist/1-per-tick/dry_run) |
| `test_runtime_info.py` | 58 | Runtime info tool definition, default state, core fields, base_url redaction, execution modes, policy snapshot, stasis reflection, registry integration, diff ritual, required fields, burst config |
| `test_tool_requests.py` | 32 | Tool request writer file creation, header dedup, field presence, action extraction, context truncation, multi-agent append, registry get_description |
| `test_narrative.py` | 35 | Narrative writer file creation, header dedup, burst session flow, interactive session, auto-summary replacement, separator formatting |
| `test_boundary.py` | 61 | Boundary events, build_denial payloads, risk classification, BoundaryLogger append/flush, registry denial for unknown/disallowed tools |
| `test_creator_inbox.py` | 69 | Creator Inbox tool definition, send/validation, all types/priorities, needs_approval, multi-agent, derived markdown, registry, burst config, concurrent appends |
| `test_governance.py` | 127 | ActiveDirectives (record/record_sections/list/ids/summary/reset/__slots__), ChangeLog (snapshot builder/diff_summary/change_record/append/read/JSONL format), validate_manifest (schema/enums/duplicates/missing sources/SHA-256 drift), RuntimeInfoTool integration, injector integration |
| `test_routing.py` | 44 | Task classification, tier routing decisions, stuck loop escalation, budget enforcement (hard/soft limits), budget month rollover, context window trimming, working set management, TickScheduler finite loop completion |

**Total: 819 checks across 11 suites**

## Running Tests

```bash
# Run all suites
python -m tests.test_tools
python -m tests.test_memory
python -m tests.test_directives
python -m tests.test_burst
python -m tests.test_runtime_info
python -m tests.test_tool_requests
python -m tests.test_narrative
python -m tests.test_boundary
python -m tests.test_creator_inbox
python -m tests.test_governance
python -m tests.test_routing

# Run all at once (Windows)
python -m tests.test_tools; python -m tests.test_memory; python -m tests.test_directives; python -m tests.test_burst; python -m tests.test_runtime_info; python -m tests.test_tool_requests; python -m tests.test_narrative; python -m tests.test_boundary; python -m tests.test_creator_inbox; python -m tests.test_governance; python -m tests.test_routing
```

## Syntax Check (all Python files)

```bash
python -c "
import py_compile, glob
files = glob.glob('src/**/*.py', recursive=True) + glob.glob('tests/**/*.py', recursive=True)
for f in sorted(files):
    py_compile.compile(f, doraise=True)
print('All files OK')
"
```

## Test Framework

Most tests use a lightweight manual framework (no pytest dependency). Each test function calls `check(label, condition)` which prints PASS/FAIL and tracks counts. Exit code 1 if any failures.

`test_routing.py` uses Python's built-in `unittest` framework instead.
