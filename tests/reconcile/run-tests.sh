#!/usr/bin/env bash
# Exit-code contract tests for NetClaw's MCP reconciliation checks.
#
# Contract: specs/075-mcp-config-reconciliation/contracts/reconcile-cli.md
# Requirements: FR-008 (non-zero exit on failure), FR-012 (unlocatable claim is
#               a failure), SC-002 (verified by introducing one defect per
#               surface), SC-013 (runs with no agent installed).
#
# These tests exist because the entire premise of spec 075 was once misdiagnosed
# by reading an exit code through a `| tail` pipe -- which reports the pipe's
# status, not the command's. Every assertion here captures the exit code
# directly. Never pipe a command whose exit code you are about to check.
#
# No test framework: bash + Python stdlib only, so this runs in a bare CI
# container. Fixtures are built in a temp dir; the repository is never modified.

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PASS=0
FAIL=0
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# assert_exit <expected> <description> -- command supplied via "$@"
assert_exit() {
    local expected="$1" desc="$2"; shift 2
    "$@" >"$TMP/out" 2>&1
    local actual=$?
    if [ "$actual" -eq "$expected" ]; then
        printf '  ok   %s (exit %d)\n' "$desc" "$actual"
        PASS=$((PASS + 1))
    else
        printf '  FAIL %s (expected exit %d, got %d)\n' "$desc" "$expected" "$actual"
        sed 's/^/         /' "$TMP/out" | head -6
        FAIL=$((FAIL + 1))
    fi
}

# assert_mentions <substring> <description> -- command supplied via "$@"
assert_mentions() {
    local needle="$1" desc="$2"; shift 2
    "$@" >"$TMP/out" 2>&1
    if grep -qF "$needle" "$TMP/out"; then
        printf '  ok   %s\n' "$desc"
        PASS=$((PASS + 1))
    else
        printf '  FAIL %s (output never mentioned %s)\n' "$desc" "$needle"
        FAIL=$((FAIL + 1))
    fi
}

echo "=== Clean repository: every surface reconciled ==="
assert_exit 0 "reconcile-mcp.py exits 0 on a reconciled tree" \
    python3 "$REPO_ROOT/scripts/reconcile-mcp.py"
assert_exit 0 "verify-catalog-coverage.py exits 0" \
    python3 "$REPO_ROOT/scripts/verify-catalog-coverage.py"
assert_exit 0 "verify-inventory-counts.py exits 0" \
    python3 "$REPO_ROOT/scripts/verify-inventory-counts.py"
assert_exit 0 "check-mcp-portability.py exits 0" \
    python3 "$REPO_ROOT/scripts/check-mcp-portability.py"

echo
echo "=== Portability surface: a machine-specific path must fail ==="
cat >"$TMP/machine-specific.json" <<'JSON'
{"mcpServers": {
  "broken-mcp": {"command": "/home/ubuntu/netclaw/.venv/bin/python3",
                 "args": ["-u", "/home/ubuntu/netclaw/mcp-servers/x/server.py"]}
}}
JSON
assert_exit 1 "a /home/ path fails the portability check" \
    python3 "$REPO_ROOT/scripts/check-mcp-portability.py" --config "$TMP/machine-specific.json"
assert_mentions "broken-mcp" "the failure names the offending entry" \
    python3 "$REPO_ROOT/scripts/check-mcp-portability.py" --config "$TMP/machine-specific.json"
assert_mentions "machine-specific" "the failure states what is wrong" \
    python3 "$REPO_ROOT/scripts/check-mcp-portability.py" --config "$TMP/machine-specific.json"

echo
echo "=== Portability surface: legitimate system paths must NOT fail (FR-004) ==="
cat >"$TMP/system-paths.json" <<'JSON'
{"mcpServers": {
  "sys-mcp": {"command": "/usr/bin/python3", "args": ["-m", "foo"]},
  "pkg-mcp": {"command": "npx", "args": ["-y", "@scope/pkg"]}
}}
JSON
assert_exit 0 "/usr/bin/python3 and npx package specs pass" \
    python3 "$REPO_ROOT/scripts/check-mcp-portability.py" --config "$TMP/system-paths.json"

echo
echo "=== Portability surface: --warn-only suppresses the failure exit ==="
assert_exit 0 "--warn-only exits 0 despite findings" \
    python3 "$REPO_ROOT/scripts/check-mcp-portability.py" --config "$TMP/machine-specific.json" --warn-only

echo
echo "=== Cannot-run is distinguishable from inconsistent (exit 2) ==="
assert_exit 2 "a missing config yields exit 2, not 1" \
    python3 "$REPO_ROOT/scripts/check-mcp-portability.py" --config "$TMP/does-not-exist.json"
printf 'not json at all' >"$TMP/broken.json"
assert_exit 2 "an unparseable config yields exit 2, not 1" \
    python3 "$REPO_ROOT/scripts/check-mcp-portability.py" --config "$TMP/broken.json"

echo
echo "=== Orchestrator aggregates a surface failure (FR-008) ==="
# Drive the real portability script through the orchestrator by pointing the
# orchestrator at a repo copy whose config is defective. Only the config is
# swapped; scripts are symlinked so this stays cheap.
FAKE="$TMP/repo"
mkdir -p "$FAKE/scripts" "$FAKE/config" "$FAKE/mcp-servers" "$FAKE/workspace/skills"
for f in reconcile-mcp.py check-mcp-portability.py; do
    cp "$REPO_ROOT/scripts/$f" "$FAKE/scripts/$f"
done
cp "$TMP/machine-specific.json" "$FAKE/config/openclaw.json"
assert_exit 1 "orchestrator exits 1 when the portability surface fails" \
    python3 "$FAKE/scripts/reconcile-mcp.py" --surface portability
assert_exit 0 "orchestrator --warn-only exits 0 despite a failing surface" \
    python3 "$FAKE/scripts/reconcile-mcp.py" --surface portability --warn-only

echo
echo "=== Orchestrator reports exit 2 when a check script is missing ==="
rm "$FAKE/scripts/check-mcp-portability.py"
assert_exit 2 "a missing check script yields exit 2" \
    python3 "$FAKE/scripts/reconcile-mcp.py" --surface portability

echo
echo "=== Dependency-pin surface (spec 077 / R0a) ==="
# These three classes broke FRESH installs only, which is why nothing caught them.
assert_exit 0 "check-dependency-pins.py passes on a clean tree" \
    python3 "$REPO_ROOT/scripts/check-dependency-pins.py"

# An unbounded pin on a package whose SUBMODULE is imported must fail.
DEPFIX="$TMP/depsrv/mcp-servers/probe-mcp"
mkdir -p "$DEPFIX"
printf 'mcp>=1.0.0\n' >"$DEPFIX/requirements.txt"
printf 'from mcp.server.fastmcp import FastMCP\n' >"$DEPFIX/server.py"
mkdir -p "$TMP/depsrv/scripts/lib"
cp "$REPO_ROOT/scripts/check-dependency-pins.py" "$TMP/depsrv/scripts/"
: >"$TMP/depsrv/scripts/lib/install-steps.sh"
assert_exit 1 "unbounded pin + submodule import fails" \
    python3 "$TMP/depsrv/scripts/check-dependency-pins.py"
assert_mentions "probe-mcp" "the failure names the offending server" \
    python3 "$TMP/depsrv/scripts/check-dependency-pins.py"
assert_mentions "SUBMODULE" "the failure explains why it matters" \
    python3 "$TMP/depsrv/scripts/check-dependency-pins.py"

# Bounding it must clear the finding.
printf 'mcp>=1.0.0,<2\n' >"$DEPFIX/requirements.txt"
assert_exit 0 "bounding the pin clears it" \
    python3 "$TMP/depsrv/scripts/check-dependency-pins.py"

# A bare pip invocation in install steps must fail, naming the line.
printf 'pip3 install something\n' >"$TMP/depsrv/scripts/lib/install-steps.sh"
assert_exit 1 "bare pip3 install fails" \
    python3 "$TMP/depsrv/scripts/check-dependency-pins.py"
assert_mentions "netclaw_pip_install" "the failure names the remedy" \
    python3 "$TMP/depsrv/scripts/check-dependency-pins.py"

# A comment or log message mentioning pip must NOT fail — false positives here
# would train maintainers to ignore the check.
printf '# pip3 install is what we used to do\nlog_info "pip install failed"\n' \
    >"$TMP/depsrv/scripts/lib/install-steps.sh"
assert_exit 0 "pip in a comment or log string is not a finding" \
    python3 "$TMP/depsrv/scripts/check-dependency-pins.py"

# --warn-only must report but not fail.
printf 'pip3 install something\n' >"$TMP/depsrv/scripts/lib/install-steps.sh"
assert_exit 0 "--warn-only exits 0 despite findings" \
    python3 "$TMP/depsrv/scripts/check-dependency-pins.py" --warn-only

# ── Startup surface (spec 088) ────────────────────────────────────────────────
# This surface exists because the four checks above validate DECLARATIONS and none
# of them ran anything: seven registered servers could not start while
# reconcile-mcp.py exited 0. These tests build fixture servers whose startup
# behaviour is known, since the real failure was found only by launching.
echo
echo "--- startup surface ---"
SUP="$TMP/startup"
mkdir -p "$SUP/scripts" "$SUP/mcp-servers/good-mcp" "$SUP/mcp-servers/broken-mcp"
cp "$REPO_ROOT/scripts/check-server-startup.py" "$SUP/scripts/"

# A server that imports cleanly and then blocks reading stdio is CORRECT MCP
# behaviour -- a timeout must never be reported as a failure. Getting this
# backwards would flag all 75 working servers.
cat >"$SUP/mcp-servers/good-mcp/server.py" <<'EOF'
import sys, json
sys.stdin.read()
EOF
cat >"$SUP/mcp-servers/broken-mcp/server.py" <<'EOF'
import nonexistent_module_xyz
EOF
write_cfg() { printf '%s
' "$1" >"$SUP/config.json"; }
mkdir -p "$SUP/config"
run_startup() { python3 "$SUP/scripts/check-server-startup.py" --config "$SUP/config/openclaw.json" "$@"; }

python3 - "$SUP" <<'EOF'
import json, sys, os
root = sys.argv[1]
cfg = {"mcpServers": {"good-mcp": {"command": "python3",
        "args": [os.path.join(root, "mcp-servers/good-mcp/server.py")]}}}
os.makedirs(os.path.join(root, "config"), exist_ok=True)
json.dump(cfg, open(os.path.join(root, "config/openclaw.json"), "w"))
EOF
assert_exit 0 "a server that blocks on stdio is not a failure (timeout != broken)" \
    run_startup

# Missing module must fail, and must name both the server and the module -- a
# finding that says only "failed" sends the reader back to the shell.
python3 - "$SUP" <<'EOF'
import json, sys, os
root = sys.argv[1]
cfg = {"mcpServers": {"broken-mcp": {"command": "python3",
        "args": [os.path.join(root, "mcp-servers/broken-mcp/server.py")]}}}
json.dump(cfg, open(os.path.join(root, "config/openclaw.json"), "w"))
EOF
assert_exit 1 "a server with a missing module fails" run_startup
assert_mentions "broken-mcp" "the finding names the server" run_startup
assert_mentions "nonexistent_module_xyz" "the finding names the missing module" run_startup

# A registered server whose file is absent -- the aruba-cx-mcp case, which no
# amount of installing packages would have fixed.
python3 - "$SUP" <<'EOF'
import json, sys, os
root = sys.argv[1]
cfg = {"mcpServers": {"absent-mcp": {"command": "python3",
        "args": [os.path.join(root, "mcp-servers/absent-mcp/server.py")]}}}
json.dump(cfg, open(os.path.join(root, "config/openclaw.json"), "w"))
EOF
assert_exit 1 "a registered server with no entry point fails" run_startup
assert_mentions "does not exist" "the finding distinguishes absent file from missing module" \
    run_startup

# --warn-only reports without failing, matching every other surface.
python3 - "$SUP" <<'EOF'
import json, sys, os
root = sys.argv[1]
cfg = {"mcpServers": {"broken-mcp": {"command": "python3",
        "args": [os.path.join(root, "mcp-servers/broken-mcp/server.py")]}}}
json.dump(cfg, open(os.path.join(root, "config/openclaw.json"), "w"))
EOF
assert_exit 0 "--warn-only exits 0 despite startup findings" run_startup --warn-only

# STARTUP_EXCEPTIONS is the documented escape hatch, so it must actually work --
# an untested suppression list is how a check quietly stops checking.
sed 's/^STARTUP_EXCEPTIONS: dict\[str, str\] = {}/STARTUP_EXCEPTIONS = {"broken-mcp": "known"}/' \
    "$REPO_ROOT/scripts/check-server-startup.py" >"$SUP/scripts/excepted.py"
assert_exit 0 "a server in STARTUP_EXCEPTIONS is suppressed" \
    python3 "$SUP/scripts/excepted.py" --config "$SUP/config/openclaw.json"

# A remote/HTTP server has no local process to launch and must be skipped, not
# reported as broken.
python3 - "$SUP" <<'EOF'
import json, sys, os
root = sys.argv[1]
cfg = {"mcpServers": {"remote-mcp": {"type": "http",
        "url": "https://example.invalid/mcp"}}}
json.dump(cfg, open(os.path.join(root, "config/openclaw.json"), "w"))
EOF
assert_exit 0 "a remote server is skipped, not failed" run_startup

echo
echo "=== Summary ==="
printf '  passed: %d\n  failed: %d\n' "$PASS" "$FAIL"
[ "$FAIL" -eq 0 ] || exit 1
echo "  all reconciliation contract tests passed"
