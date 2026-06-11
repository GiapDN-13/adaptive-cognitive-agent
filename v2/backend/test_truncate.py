"""Test truncate_output (P4.1): was_truncated true for line OR char hiding."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from app.agent.tools import truncate_output  # noqa: E402


def main():
    failures = []

    # 1: small → unchanged, False
    t, w = truncate_output("hello\nworld")
    if t != "hello\nworld" or w is not False:
        failures.append(f"1 small: {(t,w)}")
    else:
        print("[1] small output → unchanged, was_truncated=False: PASS")

    # 2: many lines (under char cap) → truncated, True
    big_lines = "\n".join(f"line{i}" for i in range(300))
    t, w = truncate_output(big_lines)
    if w is not True or "lines hidden" not in t:
        failures.append(f"2 lines: was_truncated={w}")
    else:
        print("[2] 300 lines → truncated + was_truncated=True: PASS")

    # 3: single huge line (over char cap, under line cap) → truncated, True
    huge = "x" * 20000
    t, w = truncate_output(huge)
    if w is not True or "truncated at 12000 chars" not in t:
        failures.append(f"3 chars: was_truncated={w} text_tail={t[-40:]!r}")
    else:
        print("[3] 20000-char single line → truncated + was_truncated=True: PASS")

    # 4: exactly at limits → unchanged
    exact = "\n".join("a" for _ in range(150))
    t, w = truncate_output(exact)
    if w is not False:
        failures.append(f"4 exact: was_truncated={w}")
    else:
        print("[4] exactly 150 lines → unchanged: PASS")

    print()
    if failures:
        print("RESULT: FAIL")
        for f in failures:
            print("  -", f)
        sys.exit(1)
    print("RESULT: ALL PASS")


if __name__ == "__main__":
    main()
