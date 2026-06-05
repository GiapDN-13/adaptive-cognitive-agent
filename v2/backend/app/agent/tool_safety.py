"""
Tool Safety — AST-based validation for runtime-created tool and hook code.

Prevents dangerous operations in self-created extensions by analyzing
the code's AST before compilation. Runs in the backend process with
an import whitelist and forbidden call detection.
"""

import ast

FORBIDDEN_MODULES = frozenset({
    "os", "subprocess", "shutil", "sys", "ctypes", "signal",
    "socket", "multiprocessing", "threading", "importlib",
    "code", "codeop", "compileall", "py_compile",
})

ALLOWED_MODULES = frozenset({
    "json", "re", "math", "datetime", "urllib", "urllib.parse",
    "hashlib", "base64", "collections", "itertools", "functools",
    "typing", "dataclasses", "enum", "string", "textwrap",
    "csv", "io", "struct", "decimal", "fractions",
    "statistics", "random", "uuid", "copy", "operator",
})

FORBIDDEN_CALLS = frozenset({
    "eval", "exec", "compile", "__import__", "globals", "locals",
    "getattr", "setattr", "delattr", "breakpoint", "exit", "quit",
    "open",
})


class CodeSafetyError(Exception):
    pass


def validate_handler_code(code: str) -> None:
    """Validate tool handler code. Raises CodeSafetyError if unsafe."""
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        raise CodeSafetyError(f"Syntax error: {e}")

    funcs = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "handler"
    ]
    if len(funcs) == 0:
        raise CodeSafetyError(
            "Handler code must define 'async def handler(session, tool_input, ws_send, cancel_event) -> str'"
        )
    if len(funcs) > 1:
        raise CodeSafetyError("Handler code must define exactly ONE 'async def handler(...)' function")

    func = funcs[0]
    args = func.args
    param_count = len(args.args)
    if param_count != 4:
        raise CodeSafetyError(
            f"Handler must have exactly 4 parameters (session, tool_input, ws_send, cancel_event), got {param_count}"
        )

    _check_imports(tree)
    _check_calls(tree)


def validate_hook_code(code: str, hook_type: str) -> None:
    """Validate hook code. Raises CodeSafetyError if unsafe."""
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        raise CodeSafetyError(f"Syntax error: {e}")

    if hook_type == "pre":
        func_name = "pre_hook"
        expected_params = 3
    elif hook_type == "post":
        func_name = "post_hook"
        expected_params = 4
    else:
        raise CodeSafetyError(f"Invalid hook_type: '{hook_type}'. Must be 'pre' or 'post'.")

    funcs = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.AsyncFunctionDef) and node.name == func_name
    ]
    if len(funcs) == 0:
        raise CodeSafetyError(
            f"Hook code must define 'async def {func_name}(...)'"
        )

    func = funcs[0]
    param_count = len(func.args.args)
    if param_count != expected_params:
        raise CodeSafetyError(
            f"'{func_name}' must have {expected_params} parameters, got {param_count}"
        )

    _check_imports(tree)
    _check_calls(tree)


def _check_imports(tree: ast.AST) -> None:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                module_root = alias.name.split(".")[0]
                if module_root in FORBIDDEN_MODULES:
                    raise CodeSafetyError(
                        f"Import of '{alias.name}' is forbidden. "
                        f"Use docker_manager.exec_command_simple() for system operations."
                    )
                if module_root not in ALLOWED_MODULES:
                    raise CodeSafetyError(
                        f"Import of '{alias.name}' is not in the allowed list. "
                        f"Allowed: {', '.join(sorted(ALLOWED_MODULES))}"
                    )
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                module_root = node.module.split(".")[0]
                if module_root in FORBIDDEN_MODULES:
                    raise CodeSafetyError(
                        f"Import from '{node.module}' is forbidden."
                    )
                if module_root not in ALLOWED_MODULES:
                    raise CodeSafetyError(
                        f"Import from '{node.module}' is not in the allowed list. "
                        f"Allowed: {', '.join(sorted(ALLOWED_MODULES))}"
                    )


def _check_calls(tree: ast.AST) -> None:
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in FORBIDDEN_CALLS:
                raise CodeSafetyError(
                    f"Call to '{node.func.id}()' is forbidden in runtime extensions."
                )
