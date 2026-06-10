"""Test _apply_context_window — verify long sessions get trimmed to a valid,
under-budget message list (the real fix for the recurring timeout)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.agent.loop import _apply_context_window  # noqa: E402

MAX = 80000


def build_long_session(n_iterations: int) -> list[dict]:
    """Simulate a long agent session: 1 user task, then n iterations of
    (assistant toolUse) → (user toolResult), like building a big RAG app."""
    msgs = [{"role": "user", "content": [{"text": "Tạo RAG chatbot cho 1000 user, đa dạng tài liệu."}]}]
    big_file = "x" * 6000  # a large file write, like app.py
    big_output = "y" * 5000  # a large shell/tool result
    for i in range(n_iterations):
        msgs.append({
            "role": "assistant",
            "content": [
                {"text": f"Bước {i}: ghi file."},
                {"toolUse": {"toolUseId": f"t{i}", "name": "write_file",
                             "input": {"path": f"/workspace/f{i}.py", "content": big_file}}},
            ],
        })
        msgs.append({
            "role": "user",
            "content": [
                {"toolResult": {"toolUseId": f"t{i}", "content": [{"text": big_output}]}},
            ],
        })
    return msgs


def assert_valid_bedrock(msgs: list[dict]):
    """Bedrock rules we must not violate."""
    assert msgs, "empty message list"
    assert msgs[0]["role"] == "user", f"first message must be user, got {msgs[0]['role']}"
    # no two consecutive same-role turns
    for a, b in zip(msgs, msgs[1:]):
        assert a["role"] != b["role"], f"consecutive {a['role']} messages"
    # collect every toolUseId and every toolResult id; results must reference a prior use
    seen_uses = set()
    for m in msgs:
        content = m.get("content", [])
        if not isinstance(content, list):
            continue
        for b in content:
            if "toolUse" in b:
                seen_uses.add(b["toolUse"]["toolUseId"])
            if "toolResult" in b:
                rid = b["toolResult"]["toolUseId"]
                assert rid in seen_uses, f"orphan toolResult {rid} (no matching toolUse before it)"


def main():
    failures = []

    # Case 1: short session — untouched
    short = build_long_session(2)
    out = _apply_context_window(short, MAX)
    if out is not short:
        failures.append("short session should be returned unchanged")
    print(f"[1] short session: {len(short)} msgs, unchanged={out is short}")

    # Case 2: long session — must drop below budget
    long_sess = build_long_session(34)
    before = sum(len(str(m.get("content", ""))) for m in long_sess)
    out = _apply_context_window(long_sess, MAX)
    after = sum(len(str(m.get("content", ""))) for m in out)
    print(f"[2] long session: {len(long_sess)} msgs / {before} chars -> {len(out)} msgs / {after} chars")
    if after > MAX:
        failures.append(f"after windowing {after} still > {MAX}")
    if after >= before:
        failures.append("windowing did not reduce size")

    # Case 3: result is valid for Bedrock
    try:
        assert_valid_bedrock(out)
        print("[3] bedrock validity: PASS (first=user, no consecutive same-role, no orphan toolResult)")
    except AssertionError as e:
        failures.append(f"bedrock validity: {e}")
        print(f"[3] bedrock validity: FAIL — {e}")

    # Case 4: head (original task) preserved
    if out[0] != long_sess[0]:
        failures.append("original task message not preserved as head")
    else:
        print("[4] original task preserved as head: PASS")

    # Case 5: most recent message preserved
    if out[-1] != long_sess[-1]:
        failures.append("most recent message not preserved")
    else:
        print("[5] most recent message preserved: PASS")

    print()
    if failures:
        print("RESULT: FAIL")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    print("RESULT: ALL PASS")


if __name__ == "__main__":
    main()
