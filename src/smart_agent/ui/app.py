"""SmartAgent — Streamlit Demo UI"""

import json
import time

import streamlit as st

from smart_agent.graph.state import AgentState
from smart_agent.nodes.clarifier import clarifier_node
from smart_agent.nodes.cognitive import cognitive_node
from smart_agent.nodes.evaluator import evaluator_node
from smart_agent.nodes.executor import executor_node
from smart_agent.nodes.meta_thinker import meta_thinker_node
from smart_agent.nodes.perceiver import perceiver_node
from smart_agent.nodes.retry import retry_node
from smart_agent.nodes.trivial import trivial_node

st.set_page_config(page_title="SmartAgent by MekongAI", page_icon="🧠", layout="wide")

st.title("🧠 SmartAgent")
st.caption("Adaptive Cognitive Engine by MekongAI — Not your average chatbot.")

if "messages" not in st.session_state:
    st.session_state.messages = []
if "pending_clarification" not in st.session_state:
    st.session_state.pending_clarification = None

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

user_input = st.chat_input("Nhập câu hỏi...")

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        total_start = time.time()

        # Detect post-clarification: user is answering previous clarification questions
        is_post_clarification = st.session_state.pending_clarification is not None

        if is_post_clarification:
            orig = st.session_state.pending_clarification
            enriched_input = (
                f"Original request: {orig['original_input']}\n\n"
                f"Clarification Q&A:\n"
                f"Questions asked: {orig['questions']}\n"
                f"User's answers: {user_input}\n\n"
                f"Now proceed with the task using ALL the context above."
            )
            state: AgentState = {
                "user_input": enriched_input,
                "conversation_history": st.session_state.messages[:-1],
            }
            st.session_state.pending_clarification = None

            # Skip perceiver — we already know this needs full pipeline
            state.update({
                "language": orig.get("language", "vi"),
                "domains": orig.get("domains", ["general"]),
                "complexity_score": orig.get("complexity_score", 5),
                "is_trivial": False,
                "needs_clarification": False,
                "needs_search": False,
            })
            st.caption("📎 Tiếp tục từ context trước — bỏ qua Perceiver")
        else:
            state: AgentState = {
                "user_input": user_input,
                "conversation_history": st.session_state.messages[:-1],
            }

            # Step 1: Perceiver
            with st.status("🔍 Perceiver — Phân tích input...", expanded=False) as s:
                start = time.time()
                perceiver_result = perceiver_node(state)
                state.update(perceiver_result)
                elapsed = time.time() - start
                s.update(label=f"🔍 Perceiver ({elapsed:.1f}s)", state="complete")
                st.markdown(
                    f"**Language:** `{state.get('language')}` | "
                    f"**Domains:** `{state.get('domains')}` | "
                    f"**Complexity:** `{state.get('complexity_score')}/10` | "
                    f"**Trivial:** `{state.get('is_trivial')}` | "
                    f"**Clarify:** `{state.get('needs_clarification')}`"
                )

        # Trivial path
        if state.get("is_trivial"):
            with st.status("💬 Trả lời nhanh...", expanded=False) as s:
                trivial_result = trivial_node(state)
                state.update(trivial_result)
                s.update(label="💬 Trivial response", state="complete")
            st.markdown(state.get("final_output", ""))
            st.session_state.messages.append({"role": "assistant", "content": state.get("final_output", "")})

        # Clarification path
        elif state.get("needs_clarification"):
            with st.status("❓ Cần hỏi thêm...", expanded=False) as s:
                clar_result = clarifier_node(state)
                state.update(clar_result)
                s.update(label="❓ Clarification", state="complete")
            st.markdown(state.get("final_output", ""))
            st.session_state.messages.append({"role": "assistant", "content": state.get("final_output", "")})
            # Save clarification context for next turn
            st.session_state.pending_clarification = {
                "original_input": user_input,
                "questions": state.get("clarification_questions", []),
                "language": state.get("language", "vi"),
                "domains": state.get("domains", ["general"]),
                "complexity_score": state.get("complexity_score", 5),
            }

        # Full pipeline
        else:
          try:
            # Step 2: Meta-Thinker
            with st.status("🧠 Meta-Thinker — Chọn chiến lược suy nghĩ...", expanded=False) as s:
                start = time.time()
                meta_result = meta_thinker_node(state)
                state.update(meta_result)
                elapsed = time.time() - start
                s.update(label=f"🧠 Meta-Thinker ({elapsed:.1f}s)", state="complete")
                st.markdown(
                    f"**Persona:** `{state.get('persona')}` | "
                    f"**Depth:** `{state.get('thinking_depth')}/5` | "
                    f"**Full Framework:** `{state.get('needs_full_framework')}`"
                )
                with st.expander("Domain Rules & Gates"):
                    st.markdown("**Rules:**")
                    for r in state.get("domain_rules", []):
                        st.markdown(f"- {r}")
                    st.markdown("**Anti-patterns:**")
                    for ap in state.get("anti_patterns", []):
                        st.markdown(f"- ⚠️ {ap}")
                    st.markdown("**Quality Gates:**")
                    for qg in state.get("quality_gates", []):
                        st.markdown(f"- ✅ {qg}")

            # Step 3: Cognitive Framework (if depth >= 4)
            if state.get("needs_full_framework"):
                with st.status("📐 Cognitive Framework — 5 bước tư duy chiến lược...", expanded=False) as s:
                    start = time.time()
                    cog_result = cognitive_node(state)
                    state.update(cog_result)
                    elapsed = time.time() - start
                    s.update(label=f"📐 Cognitive Framework ({elapsed:.1f}s)", state="complete")
                    cog = state.get("cognitive_output", {})
                    step_names = {"skills": "Skills", "knowledge": "Knowledge", "requirements": "Requirements", "goals": "Goals", "evaluation": "Evaluation"}
                    for key, name in step_names.items():
                        if key in cog:
                            with st.expander(f"Step: {name} ({len(cog[key])} chars)"):
                                st.markdown(cog[key][:2000])

            # Step 4: Executor (ReACT loop) + Evaluator + Retry
            attempt = 0
            max_attempts = 3
            while attempt < max_attempts:
                attempt += 1

                with st.status(f"⚡ Executor — ReACT loop (attempt {attempt})...", expanded=False) as s:
                    start = time.time()
                    exec_result = executor_node(state)
                    state.update(exec_result)
                    elapsed = time.time() - start
                    s.update(label=f"⚡ Executor ({elapsed:.1f}s, {state.get('react_iterations', 0)} iters, {len(state.get('tool_calls', []))} tools)", state="complete")

                # Show tool calls prominently (outside status, always visible)
                if state.get("tool_calls"):
                    st.markdown("##### 🔧 Tool Calls")
                    for tc in state.get("tool_calls", []):
                        tool_name = tc["tool"]
                        tool_input = tc.get("input", {})
                        tool_output = str(tc.get("output", ""))
                        col1, col2 = st.columns([1, 2])
                        with col1:
                            st.code(f"{tool_name}({json.dumps(tool_input, ensure_ascii=False)[:100]})", language="python")
                        with col2:
                            st.code(tool_output[:300], language="text")

                with st.status("📊 Evaluator — Chấm điểm output...", expanded=False) as s:
                    start = time.time()
                    eval_result = evaluator_node(state)
                    state.update(eval_result)
                    elapsed = time.time() - start
                    scores = state.get("eval_scores", {})
                    avg = sum(scores.values()) / 4 if scores else 0
                    s.update(label=f"📊 Evaluator ({elapsed:.1f}s) — Score: {avg:.1f}/10 {'✅' if state.get('eval_passed') else '❌'}", state="complete")
                    st.markdown(
                        f"R={scores.get('relevance')} | C={scores.get('completeness')} | "
                        f"A={scores.get('accuracy')} | Act={scores.get('actionability')} | "
                        f"**Avg: {avg:.1f}/10**"
                    )

                if state.get("eval_passed") or attempt >= max_attempts:
                    break

                with st.status("🔄 Retry — Đổi chiến lược...", expanded=False) as s:
                    retry_result = retry_node(state)
                    state.update(retry_result)
                    s.update(label=f"🔄 Retry — Strategy: {state.get('retry_strategy')}", state="complete")

            # Final output
            total_elapsed = time.time() - total_start
            st.divider()
            st.caption(f"⏱️ Total: {total_elapsed:.1f}s | Attempts: {attempt} | Persona: {state.get('persona')} | Depth: {state.get('thinking_depth')}")
            final = state.get("best_output") or state.get("final_output", "")
            st.markdown(final)
            st.session_state.messages.append({"role": "assistant", "content": final})

          except Exception as e:
            import traceback
            st.error(f"❌ Pipeline Error: {type(e).__name__}: {e}")
            st.code(traceback.format_exc(), language="python")
            fallback = state.get("final_output", "")
            if fallback:
                st.markdown("**Partial output recovered:**")
                st.markdown(fallback)
                st.session_state.messages.append({"role": "assistant", "content": fallback})
            else:
                st.session_state.messages.append({"role": "assistant", "content": f"[Error: {e}]"})
