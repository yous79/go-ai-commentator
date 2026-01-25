---
description: Standard workflow for developing new features and techniques.
---

# Feature Development Workflow

// turbo-all

1. Create a feature branch:
   `git checkout -b feat/[feature-name]`

2. Research logic and define implementation plan (use `IMPLEMENTATION_PLAN.md`).

3. Implement logic and add patterns to `knowledge/` if applicable.

4. Perform static verification:
   `python -m py_compile [modified_files]`

5. Run automated logic tests:
   `$env:PYTHONPATH="src"; python tests/unit/run_all_logic_tests.py`

6. Run startup verification:
   `python src/utils/check_startup.py`

7. Notify the user of completion and verification results.
