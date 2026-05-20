import io
import contextlib


def code_executor(code: str) -> str:
    stdout = io.StringIO()
    local_vars = {}
    try:
        with contextlib.redirect_stdout(stdout):
            exec(code, {"__builtins__": __builtins__}, local_vars)
        output = stdout.getvalue()
        if not output and local_vars:
            last_var = list(local_vars.values())[-1]
            if last_var is not None:
                output = str(last_var)
        return output[:15000] if output else "(no output)"
    except Exception as e:
        return f"Error: {type(e).__name__}: {e}"
