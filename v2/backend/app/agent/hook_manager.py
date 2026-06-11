"""
Hook Manager — Python-based pre/post-execution hooks.

Security patterns are derived from ECC's hooks system (hooks/hooks.json).
ECC hooks are Node.js scripts that cannot run directly; this module implements
equivalent checks in pure Python.

Design principles (from ECC):
  - Fail-open: if a hook errors out, allow execution to continue.
  - Audit trail: all tool invocations are logged.
  - Defense in depth: multiple layers of pattern matching.
"""

import logging
import re

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Dangerous shell command patterns
#   Source: ECC pre:bash:dispatcher (GateGuard, quality, push checks)
# ---------------------------------------------------------------------------
DANGEROUS_COMMAND_PATTERNS: list[tuple[str, str]] = [
    # Destructive filesystem operations
    (r"rm\s+(-[a-zA-Z]*f[a-zA-Z]*\s+)?/\s*$", "rm -rf / (root filesystem deletion)"),
    (r"rm\s+-[a-zA-Z]*r[a-zA-Z]*f[a-zA-Z]*\s+/", "Recursive force-delete from root"),
    (r"rm\s+-[a-zA-Z]*f[a-zA-Z]*r[a-zA-Z]*\s+/", "Recursive force-delete from root"),
    # Fork bomb
    (r":\(\)\s*\{\s*:\|:\s*&\s*\}\s*;?\s*:", "Fork bomb detected"),
    # Disk destruction
    (r"mkfs\.", "Filesystem format command"),
    (r"dd\s+if=/dev/(zero|random|urandom)", "dd disk write from device"),
    # Chmod world-writable
    (r"chmod\s+(-[a-zA-Z]*\s+)?777\s+/", "chmod 777 on root paths"),
    (r"chmod\s+(-[a-zA-Z]*\s+)?777\s+\.", "chmod 777 on current directory"),
    # Remote code execution via pipe
    (r"(curl|wget)\s+.*\|\s*(bash|sh|zsh|dash|ksh|python|perl|ruby)", "Piping remote content to shell"),
    # System shutdown / reboot
    (r"\b(shutdown|reboot|halt|poweroff|init\s+[06])\b", "System shutdown/reboot command"),
    # Aggressive kill
    (r"kill\s+-9\s+-1", "kill -9 -1 (kill all processes)"),
    (r"killall\s+-9", "killall -9 (aggressive kill all)"),
    # Dangerous disk/partition tools
    (r"\bfdisk\b", "Partition editor"),
    (r"\bparted\b", "Partition manipulator"),
    # Network backdoors
    (r"\b(nc|ncat|netcat)\s+.*-[a-zA-Z]*e\s+/(bin/)?(ba)?sh", "Reverse shell via netcat"),
    # History destruction
    (r"history\s+-c\s*&&\s*rm", "History clearing + file removal"),
    # /etc/passwd or /etc/shadow manipulation
    (r">\s*/etc/(passwd|shadow)", "Overwriting system auth files"),
]

# Compiled for performance (done once at import time)
_DANGEROUS_PATTERNS_COMPILED = [
    (re.compile(pat, re.IGNORECASE), desc) for pat, desc in DANGEROUS_COMMAND_PATTERNS
]


# ---------------------------------------------------------------------------
# Config file protection
#   Source: ECC pre:config-protection hook
#   "Block modifications to linter/formatter config files.
#    Steers agent to fix code instead of weakening configs."
# ---------------------------------------------------------------------------
PROTECTED_CONFIG_FILES: set[str] = {
    ".eslintrc",
    ".eslintrc.js",
    ".eslintrc.json",
    ".eslintrc.yml",
    ".eslintrc.yaml",
    "eslint.config.js",
    "eslint.config.mjs",
    "eslint.config.cjs",
    ".prettierrc",
    ".prettierrc.js",
    ".prettierrc.json",
    ".prettierrc.yml",
    ".prettierrc.yaml",
    "prettier.config.js",
    "prettier.config.mjs",
    "tsconfig.json",
    "tsconfig.build.json",
    "biome.json",
    "biome.jsonc",
    ".stylelintrc",
    ".stylelintrc.json",
    ".markdownlint.json",
    ".markdownlintrc",
    # Python linter configs — protect linter sections
    "pyproject.toml",
    "setup.cfg",
    ".flake8",
    ".pylintrc",
    "ruff.toml",
}


# ---------------------------------------------------------------------------
# Secret / credential detection patterns
#   Source: ECC pre:governance-capture hook
#   "Capture governance events (secrets, policy violations, approval requests)"
# ---------------------------------------------------------------------------
SECRET_PATTERNS: list[tuple[str, str]] = [
    # Generic API keys
    (r"(?:api[_-]?key|apikey)\s*[:=]\s*['\"][A-Za-z0-9_\-]{16,}['\"]", "API key"),
    # AWS
    (r"AKIA[0-9A-Z]{16}", "AWS Access Key ID"),
    (r"aws[_-]?secret[_-]?access[_-]?key\s*[:=]\s*['\"][A-Za-z0-9/+=]{20,}['\"]", "AWS Secret Key"),
    # GitHub tokens
    (r"gh[pousr]_[A-Za-z0-9_]{36,}", "GitHub token"),
    # Slack tokens
    (r"xox[baprs]-[0-9A-Za-z\-]{10,}", "Slack token"),
    # JWT-style tokens
    (r"eyJ[A-Za-z0-9_-]{20,}\.eyJ[A-Za-z0-9_-]{20,}\.", "JWT token"),
    # Generic secrets in assignment
    (r"(?:password|passwd|secret|token|credentials?)\s*[:=]\s*['\"][^\s'\"]{8,}['\"]", "Hardcoded secret"),
    # Private keys
    (r"-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY-----", "Private key"),
    # Generic Bearer tokens
    (r"Bearer\s+[A-Za-z0-9_\-\.]{20,}", "Bearer token"),
    # Stripe keys
    (r"sk_live_[A-Za-z0-9]{20,}", "Stripe live secret key"),
    (r"rk_live_[A-Za-z0-9]{20,}", "Stripe restricted key"),
    # SendGrid
    (r"SG\.[A-Za-z0-9_\-]{22}\.[A-Za-z0-9_\-]{43}", "SendGrid API key"),
    # Database connection strings with embedded credentials
    (r"(?:postgres|mysql|mongodb)://[^:]+:[^@]+@", "Database connection string with credentials"),
]

_SECRET_PATTERNS_COMPILED = [
    (re.compile(pat), desc) for pat, desc in SECRET_PATTERNS
]


# ===========================================================================
# Hook Manager
# ===========================================================================

class HookManager:
    def __init__(self):
        self.pre_hooks: list = []
        self.post_hooks: list = []

    def register_pre_hook(self, func):
        self.pre_hooks.append(func)

    def register_post_hook(self, func):
        self.post_hooks.append(func)

    async def execute_pre_hooks(
        self, tool_name: str, tool_input: dict, session_id: str
    ) -> tuple[bool, str | None]:
        """Run all pre-hooks. If any returns (False, reason), execution is blocked.

        Fail-open: hook exceptions are logged but do not block execution.
        """
        for hook in self.pre_hooks:
            try:
                ret = await hook(tool_name, tool_input, session_id)
                # Validate shape: a pre-hook MUST return (bool, str|None). A
                # malformed hook (e.g. returns a bare string) fails open instead
                # of crashing tool dispatch.
                if not (isinstance(ret, tuple) and len(ret) == 2):
                    logger.error(f"Pre-hook {getattr(hook, '__name__', hook)} returned bad shape {type(ret)}; ignoring (fail-open)")
                    continue
                allowed, reason = ret
                if not allowed:
                    logger.warning(f"Tool {tool_name} blocked by pre-hook: {reason}")
                    return False, reason
            except Exception as e:
                logger.error(f"Error in pre-hook for {tool_name}: {e}")
                # Fail-open: allow execution to continue
        return True, None

    async def execute_post_hooks(
        self, tool_name: str, tool_input: dict, result: str, session_id: str
    ) -> str:
        """Run all post-hooks. Hooks can mutate and return the result string.

        Fail-open: hook exceptions are logged but do not corrupt the result.
        """
        mutated_result = result
        for hook in self.post_hooks:
            try:
                out = await hook(tool_name, tool_input, mutated_result, session_id)
                # A post-hook MUST return a str (the possibly-mutated result). If it
                # returns something else, keep the previous result (fail-open).
                if isinstance(out, str):
                    mutated_result = out
                else:
                    logger.error(f"Post-hook {getattr(hook, '__name__', hook)} returned {type(out)} (expected str); keeping prior result")
            except Exception as e:
                logger.error(f"Error in post-hook for {tool_name}: {e}")
        return mutated_result


# Module-level singleton
hook_manager = HookManager()


# ===========================================================================
# Built-in Pre-Hooks
# ===========================================================================

async def dangerous_command_pre_hook(
    tool_name: str, tool_input: dict, session_id: str
) -> tuple[bool, str | None]:
    """Block dangerous shell commands using patterns derived from ECC GateGuard."""
    if tool_name != "shell_exec":
        return True, None

    command = tool_input.get("command", "")
    for pattern, description in _DANGEROUS_PATTERNS_COMPILED:
        if pattern.search(command):
            return False, (
                f"🛡️ Security Shield: Blocked — {description}. "
                f"If you need to perform this action, ask the user for explicit approval."
            )
    return True, None


async def config_protection_pre_hook(
    tool_name: str, tool_input: dict, session_id: str
) -> tuple[bool, str | None]:
    """Block modifications to linter/formatter config files.

    Derived from ECC pre:config-protection:
    'Steers agent to fix code instead of weakening configs.'
    """
    if tool_name != "write_file":
        return True, None

    path = tool_input.get("path", "")
    # Extract the filename from the path
    filename = path.rsplit("/", 1)[-1] if "/" in path else path

    if filename in PROTECTED_CONFIG_FILES:
        # Special handling for pyproject.toml — only block if touching linter sections
        if filename == "pyproject.toml":
            content = tool_input.get("content", "")
            linter_sections = [
                "[tool.ruff", "[tool.pylint", "[tool.flake8",
                "[tool.mypy", "[tool.black", "[tool.isort",
                "[tool.pytest", "[tool.pyright",
            ]
            if any(section in content for section in linter_sections):
                return False, (
                    "🛡️ Config Protection: Modifying linter/formatter settings in pyproject.toml is blocked. "
                    "Fix the code to satisfy the linter instead of weakening the configuration."
                )
            return True, None

        return False, (
            f"🛡️ Config Protection: Modifying '{filename}' is blocked. "
            "Fix the code to satisfy the linter/formatter instead of weakening the configuration."
        )
    return True, None


async def secret_detection_pre_hook(
    tool_name: str, tool_input: dict, session_id: str
) -> tuple[bool, str | None]:
    """Check for leaked secrets/credentials in write_file content.

    Derived from ECC pre:governance-capture:
    'Capture governance events (secrets, policy violations, approval requests)'
    """
    if tool_name != "write_file":
        return True, None

    content = tool_input.get("content", "")
    path = tool_input.get("path", "")

    # Skip detection for known safe file types (env examples, docs)
    safe_suffixes = (".md", ".txt", ".example", ".template", ".sample")
    if any(path.endswith(s) for s in safe_suffixes):
        return True, None

    detected = []
    for pattern, desc in _SECRET_PATTERNS_COMPILED:
        if pattern.search(content):
            detected.append(desc)

    if detected:
        findings = ", ".join(set(detected))
        return False, (
            f"🛡️ Secret Detection: Potential credentials found in file content: {findings}. "
            f"Use environment variables or a secrets manager instead of hardcoding credentials. "
            f"If this is intentional (e.g. test fixtures), ask the user for approval."
        )
    return True, None


# ===========================================================================
# Built-in Post-Hooks
# ===========================================================================

async def audit_post_hook(
    tool_name: str, tool_input: dict, result: str, session_id: str
) -> str:
    """Audit logging for all tool invocations."""
    # Truncate large inputs/results for log readability
    input_summary = str(tool_input)[:200]
    result_summary = result[:200] if result else "(empty)"
    logger.info(
        f"[AUDIT] Session {session_id} | Tool: {tool_name} | "
        f"Input: {input_summary} | Result: {result_summary}"
    )
    return result


async def quality_gate_post_hook(
    tool_name: str, tool_input: dict, result: str, session_id: str
) -> str:
    """Quality gate check for written files.

    Derived from ECC post:quality-gate:
    'Enforce quality standards after edits — warn about large files without tests.'
    """
    if tool_name != "write_file":
        return result

    content = tool_input.get("content", "")
    path = tool_input.get("path", "")
    line_count = content.count("\n") + 1

    # Skip non-code files
    code_extensions = (".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".rs")
    if not any(path.endswith(ext) for ext in code_extensions):
        return result

    warnings = []

    # Warn about very large files
    if line_count > 500:
        warnings.append(
            f"⚠️ File is {line_count} lines — consider splitting into smaller modules."
        )

    # Warn if writing code but no test file reference
    if line_count > 100:
        test_indicators = ("test_", "_test.", ".test.", "spec.", "_spec.")
        is_test_file = any(ind in path.lower() for ind in test_indicators)
        if not is_test_file:
            warnings.append(
                "⚠️ Quality Gate: This is a substantial code file. Consider writing tests."
            )

    if warnings:
        return result + "\n\n" + "\n".join(warnings)
    return result


async def debug_statement_post_hook(
    tool_name: str, tool_input: dict, result: str, session_id: str
) -> str:
    """Detect leftover debug statements in written files.

    Derived from ECC stop:check-console-log:
    'Check for leftover console.log / debug prints before finishing.'
    """
    if tool_name != "write_file":
        return result

    content = tool_input.get("content", "")
    path = tool_input.get("path", "")

    # Skip non-code files
    code_extensions = (".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".rs")
    if not any(path.endswith(ext) for ext in code_extensions):
        return result

    debug_patterns = [
        (r"\bconsole\.log\b", "console.log"),
        (r"\bprint\s*\(", "print()"),
        (r"\bdebugger\b", "debugger"),
        (r"\bpdb\.set_trace\b", "pdb.set_trace"),
        (r"\bbreakpoint\s*\(", "breakpoint()"),
        (r"\blogger\.debug\b", "logger.debug"),
    ]

    found = []
    for pattern, name in debug_patterns:
        if re.search(pattern, content):
            found.append(name)

    if found:
        statements = ", ".join(found)
        return result + (
            f"\n\n⚠️ Debug Statement Check: Found [{statements}] in the file. "
            f"Consider removing debug statements before final deployment."
        )
    return result


# ===========================================================================
# Planning Loop & GateGuard (from Superpowers + ECC patterns)
# ===========================================================================

# Session-level tracking: what tools have been called per session
_session_tool_history: dict[str, list[str]] = {}


def _record_tool_call(session_id: str, tool_name: str):
    """Record that a tool was called in this session."""
    if session_id not in _session_tool_history:
        _session_tool_history[session_id] = []
    _session_tool_history[session_id].append(tool_name)


def _session_has_called(session_id: str, tool_names: set[str]) -> bool:
    """Check if session has called any of the specified tools."""
    history = _session_tool_history.get(session_id, [])
    return bool(set(history) & tool_names)


def clear_session_history(session_id: str):
    """Cleanup when session is destroyed."""
    _session_tool_history.pop(session_id, None)
    # Defined later in this module; guard in case of import ordering.
    globals().get("_heavy_dep_warned", {}).pop(session_id, None)


RESEARCH_TOOLS = {"web_search", "read_file", "shell_exec", "think", "load_skill", "load_agent"}
WRITE_TOOLS = {"create_tool", "create_skill", "create_hook", "write_file"}


async def gateguard_pre_hook(
    tool_name: str, tool_input: dict, session_id: str
) -> tuple[bool, str | None]:
    """GateGuard: Block write/create operations if agent hasn't done ANY research first.

    From ECC pattern: "Demand investigation before file edits."
    Forces agent to read/search/think before creating or writing.
    """
    if tool_name not in WRITE_TOOLS:
        return True, None

    # Allow if agent has done at least one research operation
    if _session_has_called(session_id, RESEARCH_TOOLS):
        return True, None

    # Allow think tool as it's research
    if tool_name == "think":
        return True, None

    return False, (
        "🛡️ GateGuard: You must research before creating/writing. "
        "Call `think` (to plan your approach), `web_search` (to gather info), "
        "`read_file` (to inspect existing files), or `shell_exec` (to explore) "
        "BEFORE calling `create_tool`, `create_skill`, `create_hook`, or `write_file`. "
        "This ensures you don't hallucinate — investigate first, then act."
    )


async def planning_loop_post_hook(
    tool_name: str, tool_input: dict, result: str, session_id: str
) -> str:
    """Planning Loop: After research tools, nudge agent to plan before acting.

    From Superpowers pattern: "Design gate — plan before implement."
    """
    # Record this tool call
    _record_tool_call(session_id, tool_name)

    # After first research action, if agent hasn't thought yet, nudge
    history = _session_tool_history.get(session_id, [])

    # If agent just did first web_search or shell_exec but hasn't called think yet
    if tool_name in ("web_search", "shell_exec", "read_file"):
        think_count = history.count("think")
        research_count = sum(1 for t in history if t in RESEARCH_TOOLS - {"think"})

        if research_count >= 2 and think_count == 0:
            return result + (
                "\n\n💡 **Planning Reminder**: You've gathered data but haven't called `think` yet. "
                "Before creating tools or executing complex operations, use `think` to: "
                "(1) assess what tools you need, (2) plan your approach, (3) identify gaps in your knowledge."
            )

    return result


# Heavy deps that pull large native runtimes (torch etc.) — risky on a small
# RAM budget. Maps a pip package name → approximate resident footprint hint.
_HEAVY_DEPS = {
    "torch": "PyTorch ~800MB-2GB resident",
    "tensorflow": "TensorFlow ~1GB+ resident",
    "sentence-transformers": "pulls in PyTorch ~800MB-2GB",
    "transformers": "pulls in PyTorch/TF, hundreds of MB+",
    "spacy": "language models ~hundreds of MB",
    "faiss-gpu": "GPU build, large",
    "vllm": "very large, multi-GB",
    "unstructured": "heavy parsing stack, hundreds of MB",
}
# Lighter alternatives to suggest, so the nudge is actionable (not just "no").
_LIGHT_ALTERNATIVES = (
    "For semantic search under tight RAM: use an EMBEDDING API (OpenAI/Bedrock/Gemini) "
    "so no model loads locally; or ONNX-based `fastembed` (far lighter than torch); or "
    "lexical retrieval (`rank-bm25` / TF-IDF via scikit-learn) — no model at all. "
    "Vector store: `faiss-cpu` or numpy cosine is fine; it's the EMBEDDING runtime that blows RAM."
)


def _session_mem_mb(session_id: str) -> int | None:
    """Best-effort: read the container RAM budget (MB) for this session.
    Returns None if unknown. Keeps the hook decoupled from the loop."""
    try:
        from app.deps import _session_manager
        if _session_manager is None:
            return None
        # NOTE: SessionManager.get() is async; we only need a sync dict lookup here
        # (a pre-hook is sync). Read the backing _sessions dict directly to avoid
        # returning an un-awaited coroutine (which silently broke the RAM guard).
        session = _session_manager._sessions.get(session_id)
        if not session or not getattr(session, "container_config", None):
            return None
        ml = str(session.container_config.mem_limit).strip().lower()
        if ml.endswith("g"):
            return int(float(ml[:-1]) * 1024)
        if ml.endswith("m"):
            return int(float(ml[:-1]))
        return None
    except Exception:
        return None


# Track which (session, package) heavy-dep warnings we've already shown, so the
# agent can override by simply re-issuing the command (fail-closed but recoverable).
_heavy_dep_warned: dict[str, set] = {}


async def heavy_dep_ram_guard_pre_hook(
    tool_name: str, tool_input: dict, session_id: str
) -> tuple[bool, str | None]:
    """Soft-block installing a heavy dependency when the RAM budget is small.

    This closes G1: the agent often CORRECTLY analyzes that e.g. sentence-transformers
    is too heavy for 512MB, then installs it anyway. This makes that contradiction
    mechanical: first attempt is blocked with the footprint + lighter alternatives;
    if the agent still means it, re-issuing the SAME install proceeds (preserves freedom).
    """
    if tool_name != "shell_exec":
        return True, None
    command = tool_input.get("command", "")
    if "pip install" not in command and "pip3 install" not in command and "uv pip install" not in command:
        return True, None

    mem_mb = _session_mem_mb(session_id)
    # Only guard when RAM is genuinely tight (<= 1GB). Unknown budget → don't block.
    if mem_mb is None or mem_mb > 1024:
        return True, None

    cmd_lower = command.lower()
    hit = next((dep for dep in _HEAVY_DEPS if dep in cmd_lower), None)
    if not hit:
        return True, None

    warned = _heavy_dep_warned.setdefault(session_id, set())
    if hit in warned:
        # Agent insists — let it through (it owns the decision).
        return True, None
    warned.add(hit)

    return False, (
        f"🧠 RAM-Budget Guard: You're installing '{hit}' ({_HEAVY_DEPS[hit]}) but this "
        f"container has only ~{mem_mb}MB RAM. This will likely OOM or hang during install/load — "
        f"and is probably the exact thing your own analysis flagged as too heavy.\n"
        f"→ {_LIGHT_ALTERNATIVES}\n"
        f"Revisit your DECISION-COMMITMENT table (research-first-design skill): pick something in the "
        f"RAM budget. If you have a concrete reason '{hit}' fits anyway, re-issue the same install "
        f"command to proceed — but make the reasoning explicit first."
    )


# ===========================================================================
# Register all built-in hooks
# ===========================================================================

hook_manager.register_pre_hook(dangerous_command_pre_hook)
hook_manager.register_pre_hook(heavy_dep_ram_guard_pre_hook)
hook_manager.register_pre_hook(config_protection_pre_hook)
hook_manager.register_pre_hook(secret_detection_pre_hook)
hook_manager.register_pre_hook(gateguard_pre_hook)
hook_manager.register_post_hook(audit_post_hook)
hook_manager.register_post_hook(quality_gate_post_hook)
hook_manager.register_post_hook(debug_statement_post_hook)
hook_manager.register_post_hook(planning_loop_post_hook)
