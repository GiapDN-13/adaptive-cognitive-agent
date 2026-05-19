import math


def calculator(expression: str) -> str:
    safe_globals = {
        "__builtins__": {},
        "math": math,
        "abs": abs,
        "round": round,
        "min": min,
        "max": max,
        "sum": sum,
        "pow": pow,
        "int": int,
        "float": float,
        "len": len,
        "range": range,
        "list": list,
        "True": True,
        "False": False,
    }
    try:
        result = eval(expression, safe_globals)
        return str(result)
    except Exception as e:
        return f"Error: {e}"
