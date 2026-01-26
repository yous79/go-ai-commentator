# Project Rules (go-ai-commentator)

## Model Identification Protocol
- **Identity**: The latest strategic intelligence model in use is **Gemini 3 Flash Preview**.
- **Constraint**: Do not append or cite other model names (API names, specific versions, etc.) in specifications, comments, or generated commentary.

## Implementation Protocols
- **Approval Requirement**: Always present a plan and obtain explicit user approval before executing code changes or refactoring.
- **No Self-starting**: Do not start implementation in the same turn you ask for permission; wait for the user's response.
- **Branching Rule**: Use `feat/` branches for new feature development.
- **Verification Obligation**: 
    1. Run `python src/utils/check_startup.py` after changes.
    2. Run `python tests/unit/run_all_logic_tests.py` for logic changes.
    3. Perform syntax checks with `python -m py_compile`.
    4. **Pre-Implementation Check**: Before any new feature, YOU MUST run the `/pre-implementation` workflow to check `PROJECT_STRUCTURE.md` and existing modules.
    5. **Recursive Proposal Check**: When proposing new ideas, verify if they already exist to avoid redundancy loops.

## Shape Detection Priorities
Use the following priority values in `ShapeDetector`:
- **100**: Bad Shapes (Aki-sankaku, etc.) and Ponnuki.
- **98**: Ryo-Atari (Double Atari).
- **95**: Atari.
- **90**: Kirichigai (Cross-cut).
- **75**: Connection techniques (Kata-tsugi, Kake-tsugi).
- **60**: Butsukari (Collision).
- **30**: Nobi and Narabi.
- **20**: General techniques (Keima, Ikken-tobi, Hane, Kosumi).
- **10**: Tsuke.
