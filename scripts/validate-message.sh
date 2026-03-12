#!/usr/bin/env bash
# validate-message.sh — Validates a message file against Hard Rules
# Usage: ./scripts/validate-message.sh <message_file>
# Exit 0 = PASS, Exit 1 = FAIL

set -euo pipefail

FILE="${1:-}"
if [[ -z "$FILE" || ! -f "$FILE" ]]; then
    echo "Usage: $0 <message_file>"
    exit 1
fi

CONTENT=$(cat "$FILE")
ERRORS=()

# Rule 1: Connection notes must be under 300 chars
# Only check if file contains a connection_note section
if echo "$CONTENT" | grep -qi "connection_note\|connection note"; then
    NOTE=$(echo "$CONTENT" | sed -n '/connection_note/,/^---/p' | tail -n +2 | head -n -1)
    NOTE_LEN=${#NOTE}
    if [[ $NOTE_LEN -gt 300 ]]; then
        ERRORS+=("Rule 1 FAIL: Connection note is $NOTE_LEN chars (max 300)")
    fi
fi

# Rule 2: "I" used more than twice
I_COUNT=$(echo "$CONTENT" | grep -o '\bI\b' | wc -l | tr -d ' ')
if [[ $I_COUNT -gt 2 ]]; then
    ERRORS+=("Rule 2 FAIL: 'I' appears $I_COUNT times (max 2)")
fi

# Rule 3: Salesy language
SALESY_WORDS="guaranteed|proven ROI|best in class|game.changing|synergy|leverage|revolutionary|disruptive|paradigm|world.class"
if echo "$CONTENT" | grep -qiE "$SALESY_WORDS"; then
    MATCH=$(echo "$CONTENT" | grep -iEo "$SALESY_WORDS" | head -1)
    ERRORS+=("Rule 3 FAIL: Salesy language detected: '$MATCH'")
fi

# Rule 4: [SPECIFIC:] marker required
if ! echo "$CONTENT" | grep -q '\[SPECIFIC:'; then
    ERRORS+=("Rule 4 FAIL: Missing [SPECIFIC: <hook>] marker")
fi

# Rule 5: "checking in" follow-up pattern
if echo "$CONTENT" | grep -qi "just checking in\|following up to check\|circling back"; then
    ERRORS+=("Rule 5 FAIL: Generic follow-up detected ('checking in')")
fi

# Report
if [[ ${#ERRORS[@]} -eq 0 ]]; then
    echo "✅ PASS — all rules satisfied"
    exit 0
else
    echo "❌ FAIL — ${#ERRORS[@]} violation(s):"
    for err in "${ERRORS[@]}"; do
        echo "  • $err"
    done
    exit 1
fi
