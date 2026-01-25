---
description: A checklist to ensure compliance with .agent/rules.md before concluding a task.
---

# Self-Audit Workflow

// turbo-all

1. Verify IDENTITY:
   - Ensure the model name is correctly stated as `Gemini 3 Flash Preview` if mentioned.
   - Check that no other model names (e.g., GPT, Claude, etc.) have been introduced.

2. Verify TERMINOLOGY:
   - Check if any "medical metaphors" (diagnosis, prescription, pathology, surgery, scalpel, etc.) were used in generated commentary.
   - Replace them with Go-specific terminology (Triage is allowed as an intellectual framework, but not clinical).

3. Verify TECHNICAL SPECS:
   - Check if hand-tuned priority scores match `rules.md` (e.g., bad shapes = 100, Atari = 95).
   - Ensure all new shapes are defined in `knowledge/` JSON rather than Python code.

4. Verify VERIFICATION:
   - Ensure `python src/utils/check_startup.py` was run.
   - Ensure `python tests/unit/run_all_logic_tests.py` was run for logic changes.
   - Ensure `python -m py_compile` was run for syntax checks.

5. Finalizing:
   - Only after all checks pass, notify the user of task completion.
