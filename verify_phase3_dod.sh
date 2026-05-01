#!/usr/bin/env bash
# =============================================================================
# verify_phase3_dod.sh — Phase 3 Definition of Done Verification (#35)
# Run from the project root: bash verify_phase3_dod.sh
# =============================================================================

set -uo pipefail

exec > >(tee "phase3_dod_results.txt") 2>&1

export PYTHONPATH="$(pwd)"

PASS=0
FAIL=0
SKIP=0

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
RESET='\033[0m'

pass() { echo -e "  ${GREEN}✔${RESET}  $1"; ((PASS++)); }
fail() { echo -e "  ${RED}✘${RESET}  $1"; ((FAIL++)); }
skip() { echo -e "  ${YELLOW}–${RESET}  $1 ${YELLOW}(skipped — no API key)${RESET}"; ((SKIP++)); }

divider() { echo -e "\n${BOLD}──── $1 ────${RESET}"; }

echo ""
echo -e "${BOLD}Phase 3 — Definition of Done Verification${RESET}"
echo "$(date)"
echo ""

# ─── 1. Dependencies ─────────────────────────────────────────────────────────
divider "1. Dependencies"

if uv sync --quiet 2>/dev/null; then
    pass "uv sync resolves cleanly"
else
    fail "uv sync failed — check pyproject.toml"
fi

for pkg in groq httpx feedparser tenacity google.generativeai; do
    if python -c "import ${pkg}" 2>/dev/null; then
        pass "Python package importable: ${pkg}"
    else
        fail "Python package missing: ${pkg}"
    fi
done

# ─── 2. FFmpeg ───────────────────────────────────────────────────────────────
divider "2. FFmpeg / FFprobe"

if ffmpeg -version &>/dev/null; then
    FFMPEG_VER=$(ffmpeg -version 2>&1 | head -1)
    pass "ffmpeg found — ${FFMPEG_VER}"
else
    fail "ffmpeg not found — install from https://ffmpeg.org/download.html and add bin/ to PATH"
fi

if ffprobe -version &>/dev/null; then
    FFPROBE_VER=$(ffprobe -version 2>&1 | head -1)
    pass "ffprobe found — ${FFPROBE_VER}"
else
    fail "ffprobe not found — should come with ffmpeg"
fi

# ─── 3. Module Imports ───────────────────────────────────────────────────────
divider "3. Module Imports"

imports=(
    "from utils.retry import with_standard_retry, TransientError"
    "from utils.retry import with_aggressive_retry, PermanentError, AudioProcessingError, TranscriptionError, CaptionError, RSSError"
    "from utils.hashing import sha256_str, sha256_dict"
    "from utils.time import utcnow_iso, ms_since"
    "from services.rss import fetch_feed, match_episode"
    "from services.audio import get_duration, compress_audio, needs_chunking, split_into_chunks"
    "from services.groq import transcribe_file, transcribe_chunks, GroqTranscriptResult"
    "from services.gemini import generate_caption, generate_all_captions, CaptionResult"
    "from services.whisper import transcribe_file as whisper_transcribe"
)

for stmt in "${imports[@]}"; do
    error_output=$(python -c "${stmt}" 2>&1)
    if [[ $? -eq 0 ]]; then
        pass "Import OK: ${stmt}"
    else
        fail "Import FAILED: ${stmt}"
        echo "      → ${error_output}" | head -5
    fi
done

# ─── 4. Pytest Marker Configured ─────────────────────────────────────────────
divider "4. Pytest Integration Marker"

if grep -q '"integration"' pyproject.toml 2>/dev/null || grep -q "integration" pyproject.toml 2>/dev/null; then
    pass "integration marker found in pyproject.toml"
else
    fail "integration marker missing from pyproject.toml [tool.pytest.ini_options]"
fi

# ─── 5. Unit Tests (fast — no network required) ───────────────────────────────
divider "5. Unit Tests (no network)"

echo "  Running: pytest tests/ -m 'not integration' -v --tb=short"
if pytest tests/ -m "not integration" -v --tb=short 2>&1 | tee /tmp/unit_test_output.txt | tail -5; then
    if grep -q "passed" /tmp/unit_test_output.txt && ! grep -q "error" /tmp/unit_test_output.txt; then
        pass "All unit tests passed"
    else
        fail "Unit tests had failures — see output above"
    fi
else
    fail "pytest exited with non-zero status"
fi

# ─── 6. Integration Tests (requires API keys) ─────────────────────────────────
divider "6. Integration Tests (API keys required)"

HAS_GROQ=false
HAS_GEMINI=false

if [[ -f ".env" ]]; then
    source <(grep -E "^(GROQ|GEMINI)_API_KEY=" .env | sed 's/^/export /')
fi

if [[ -n "${GROQ_API_KEY:-}" ]]; then
    HAS_GROQ=true
fi
if [[ -n "${GEMINI_API_KEY:-}" ]]; then
    HAS_GEMINI=true
fi

if $HAS_GROQ || $HAS_GEMINI; then
    echo "  Running: pytest tests/test_integrations/ -m integration -v --tb=short"
    if pytest tests/test_integrations/ -m integration -v --tb=short 2>&1 | tee /tmp/integration_test_output.txt | tail -5; then
        pass "Integration tests passed"
    else
        fail "Integration tests had failures — see output above"
    fi
else
    skip "No API keys found in .env — skipping integration test run"
fi

# ─── 7. .env.example Keys Documented ─────────────────────────────────────────
divider "7. .env.example"

if [[ -f ".env.example" ]]; then
    if grep -q "GROQ_API_KEY" .env.example; then
        pass "GROQ_API_KEY documented in .env.example"
    else
        fail "GROQ_API_KEY missing from .env.example"
    fi
    if grep -q "GEMINI_API_KEY" .env.example; then
        pass "GEMINI_API_KEY documented in .env.example"
    else
        fail "GEMINI_API_KEY missing from .env.example"
    fi
else
    fail ".env.example not found"
fi

# ─── 8. Git Status ────────────────────────────────────────────────────────────
divider "8. Git Status"

if git diff --quiet && git diff --cached --quiet; then
    pass "Working tree is clean — no uncommitted changes"
else
    fail "Uncommitted changes detected — commit or stash before Phase 4"
    git status --short
fi

CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")
if [[ "${CURRENT_BRANCH}" == "main" ]]; then
    pass "On main branch"
else
    fail "Not on main — currently on '${CURRENT_BRANCH}'. Merge all feature branches before Phase 4."
fi

# ─── 9. Feature Branch Check ─────────────────────────────────────────────────
divider "9. Feature Branch Merge Status"

FEATURE_BRANCHES=(
    "feat/retry-utility"
    "feat/service-rss"
    "feat/service-audio"
    "feat/service-groq"
    "feat/service-whisper"
    "feat/service-gemini"
    "test/integrations"
)

for branch in "${FEATURE_BRANCHES[@]}"; do
    if git branch --merged main 2>/dev/null | grep -q "${branch}"; then
        pass "Merged to main: ${branch}"
    else
        # Branch might not exist locally if deleted after merge — that's fine too
        if ! git show-ref --verify --quiet "refs/heads/${branch}" 2>/dev/null; then
            pass "Merged and deleted: ${branch}"
        else
            fail "Not yet merged to main: ${branch}"
        fi
    fi
done

# ─── Summary ─────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}══════════════════════════════════════════${RESET}"
echo -e "${BOLD}  Results: ${GREEN}${PASS} passed${RESET}  ${RED}${FAIL} failed${RESET}  ${YELLOW}${SKIP} skipped${RESET}"
echo -e "${BOLD}══════════════════════════════════════════${RESET}"
echo ""

if [[ ${FAIL} -eq 0 ]]; then
    echo -e "${GREEN}${BOLD}✔ Phase 3 Definition of Done — ALL CHECKS PASSED${RESET}"
    echo -e "  You're clear to start Phase 4 — Core Business Logic."
    exit 0
else
    echo -e "${RED}${BOLD}✘ Phase 3 Definition of Done — ${FAIL} CHECK(S) FAILED${RESET}"
    echo -e "  Resolve the failures above before merging to Phase 4."
    exit 1
fi