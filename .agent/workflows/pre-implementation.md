---
description: Ensure thorough codebase review before implementation
---

# Pre-Implementation Checklist

Run this workflow before starting any new feature or refactoring task to prevent duplication and ensure architectural consistency.

1. **Check Prior Art**:
   - [ ] Search `PROJECT_STRUCTURE.md` for relevant components.
   - [ ] Run `grep` or `find` to locate existing implementation of similar logic.
   - [ ] _Specific check_: Does logic already exist in `src/core` or `src/services`?

2. **Verify MCP Alignment**:
   - [ ] Check `src/mcp_modules/` to see if the feature should be an MCP tool.
   - [ ] Consult `design_mcp_engine.md` for alignment.

3. **Rules & Constraints**:
   - [ ] Review `.agent/rules.md`.
   - [ ] Confirm no outdated model references (Gemini 1.5 etc.) will be introduced.

4. **Impact Analysis**:
   - [ ] Identify which shared components (EventBus, Renderer) might be affected.
   - [ ] Plan verification steps to prevent regression (e.g., Zombie Subscriptions).

// turbo
5. **Output Requirement**:
   - [ ] Append the summary of this check to the `Implementation Plan`.
