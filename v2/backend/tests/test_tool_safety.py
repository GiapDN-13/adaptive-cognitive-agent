"""Unit tests for tool_safety — AST validation of runtime code."""
import pytest
from app.agent.tool_safety import (
    validate_handler_code,
    validate_hook_code,
    CodeSafetyError,
)


VALID_HANDLER = '''
async def handler(session, tool_input, ws_send, cancel_event):
    import json
    return json.dumps({"ok": True})
'''


def test_valid_handler_passes():
    validate_handler_code(VALID_HANDLER)  # should not raise


def test_handler_missing_function_rejected():
    with pytest.raises(CodeSafetyError):
        validate_handler_code("async def other(): pass")


def test_handler_wrong_param_count_rejected():
    with pytest.raises(CodeSafetyError):
        validate_handler_code("async def handler(a, b): return 'x'")


def test_forbidden_import_os():
    code = '''
async def handler(session, tool_input, ws_send, cancel_event):
    import os
    return os.getcwd()
'''
    with pytest.raises(CodeSafetyError):
        validate_handler_code(code)


def test_forbidden_import_subprocess():
    code = '''
async def handler(session, tool_input, ws_send, cancel_event):
    import subprocess
    return "x"
'''
    with pytest.raises(CodeSafetyError):
        validate_handler_code(code)


def test_forbidden_call_eval():
    code = '''
async def handler(session, tool_input, ws_send, cancel_event):
    return eval(tool_input.get("e"))
'''
    with pytest.raises(CodeSafetyError):
        validate_handler_code(code)


def test_forbidden_call_exec():
    code = '''
async def handler(session, tool_input, ws_send, cancel_event):
    exec(tool_input.get("c"))
    return "x"
'''
    with pytest.raises(CodeSafetyError):
        validate_handler_code(code)


def test_non_whitelisted_import_rejected():
    code = '''
async def handler(session, tool_input, ws_send, cancel_event):
    import requests
    return requests.get("http://x").text
'''
    with pytest.raises(CodeSafetyError):
        validate_handler_code(code)


def test_allowed_imports_pass():
    code = '''
async def handler(session, tool_input, ws_send, cancel_event):
    import re, hashlib, csv, io
    from datetime import datetime
    from collections import defaultdict
    return "ok"
'''
    validate_handler_code(code)  # should not raise


def test_syntax_error_rejected():
    with pytest.raises(CodeSafetyError):
        validate_handler_code("async def handler(:::")


# --- Hook validation ---

def test_valid_pre_hook():
    code = '''
async def pre_hook(tool_name, tool_input, session_id):
    return True, None
'''
    validate_hook_code(code, "pre")


def test_valid_post_hook():
    code = '''
async def post_hook(tool_name, tool_input, result, session_id):
    return result
'''
    validate_hook_code(code, "post")


def test_hook_wrong_function_name_rejected():
    code = '''
async def my_hook(tool_name, tool_input, session_id):
    return True, None
'''
    with pytest.raises(CodeSafetyError):
        validate_hook_code(code, "pre")


def test_hook_invalid_type_rejected():
    code = '''
async def pre_hook(tool_name, tool_input, session_id):
    return True, None
'''
    with pytest.raises(CodeSafetyError):
        validate_hook_code(code, "invalid_type")
