# tests/

Test suites for the agent runtime. Run from the project root.

## Test Files

| File | Checks | What It Tests |
|------|--------|---------------|
| `test_tools.py` | 19 | Echo tool, continuation update (append/replace/traversal), runtime policy |
| `test_memory.py` | 132 | VaultStore CRUD (create/read/update/delete), scoping, PII guard, bulk delete, versioning, resolve_latest, compact, stats, Memory dataclass, taxonomy constants, tiers & topics, tags & source, JSONL format, backward-compat alias |
| `test_directives.py` | 107 | Parser, store search, store list/get, scoping, injector, directives tool, scoring, manifest generation, manifest save/load, manifest helpers, manifest diff, audit changes, changes action |
| `test_boundary.py` | 41 | Boundary events, build_denial payloads, risk classification, BoundaryLogger append/flush |
| `test_governance.py` | 72 | ActiveDirectives (record/record_sections/list/ids/summary/reset/__slots__), validate_manifest (schema/enums/duplicates/missing sources/SHA-256 drift), injector integration |

**Total: 371 checks across 5 suites**

## Running Tests

```bash
# Run all suites
python -m tests.test_tools
python -m tests.test_memory
python -m tests.test_directives
python -m tests.test_boundary
python -m tests.test_governance

# Run all at once (Windows)
python -m tests.test_tools; python -m tests.test_memory; python -m tests.test_directives; python -m tests.test_boundary; python -m tests.test_governance
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


