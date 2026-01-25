---
name: go_logic
description: Specialized geometric and strategic logic for Go board analysis.
---

# Go Logic Skill

This skill provides technical specifications for identifying Go shapes and assessing board states.

## Shape Definitions
- **Aki-sankaku**: 3 stones in a 2x2 square with one empty corner. High priority warning.
- **Sakare-gata**: Divided shape. Pathfinding (BFS) check for physical/logical connection.
- **Kata-tsugi**: L-shaped connection completing a 2x2 with 1 opponent stone.
- **Kake-tsugi**: V-shaped (Tiger's Mouth) connection with internal purity and opponent pressure.

## Analysis Logic
- **Stability Score**: 5-level status (Dead / Critical / Weak / Stable / Strong) based on Ownership data.
- **Endgame Recognition**: Phase detection based on regional ownership certainty (Threshold > 0.9).
- **Kasu-ishi (Junk Stone)**: Interference detection for moves played near dead stones with Ownership > 0.8.

## Resources
- Patterns: `knowledge/` directory.
- Verification: `test_play.py` and unit tests.
