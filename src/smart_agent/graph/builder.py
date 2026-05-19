from langgraph.graph import END, StateGraph

from smart_agent.graph.state import AgentState
from smart_agent.nodes.clarifier import clarifier_node
from smart_agent.nodes.cognitive import cognitive_node
from smart_agent.nodes.evaluator import evaluator_node
from smart_agent.nodes.executor import executor_node
from smart_agent.nodes.meta_thinker import meta_thinker_node
from smart_agent.nodes.perceiver import perceiver_node
from smart_agent.nodes.retry import retry_node
from smart_agent.nodes.trivial import trivial_node


def route_after_perceiver(state: AgentState) -> str:
    if state.get("is_trivial"):
        return "trivial_respond"
    if state.get("needs_clarification"):
        return "clarifier"
    return "meta_thinker"


def route_after_meta_thinker(state: AgentState) -> str:
    if state.get("needs_full_framework"):
        return "cognitive_framework"
    return "executor"


def route_after_evaluator(state: AgentState) -> str:
    if state.get("eval_passed") or state.get("attempt_number", 0) >= 3:
        return "format_output"
    return "retry_strategist"



def format_output_node(state: AgentState) -> dict:
    best = state.get("best_output", "")
    final = state.get("final_output", "")
    return {"final_output": best if best else final}


def build_graph() -> StateGraph:
    graph = StateGraph(AgentState)

    graph.add_node("perceiver", perceiver_node)
    graph.add_node("trivial_respond", trivial_node)
    graph.add_node("clarifier", clarifier_node)
    graph.add_node("meta_thinker", meta_thinker_node)
    graph.add_node("cognitive_framework", cognitive_node)
    graph.add_node("executor", executor_node)
    graph.add_node("evaluator", evaluator_node)
    graph.add_node("retry_strategist", retry_node)
    graph.add_node("format_output", format_output_node)

    graph.set_entry_point("perceiver")

    graph.add_conditional_edges(
        "perceiver",
        route_after_perceiver,
        {
            "trivial_respond": "trivial_respond",
            "clarifier": "clarifier",
            "meta_thinker": "meta_thinker",
        },
    )

    graph.add_conditional_edges(
        "meta_thinker",
        route_after_meta_thinker,
        {
            "cognitive_framework": "cognitive_framework",
            "executor": "executor",
        },
    )

    # Cognitive framework → executor (framework enriches executor context)
    graph.add_edge("cognitive_framework", "executor")
    graph.add_edge("executor", "evaluator")

    graph.add_conditional_edges(
        "evaluator",
        route_after_evaluator,
        {
            "format_output": "format_output",
            "retry_strategist": "retry_strategist",
        },
    )

    graph.add_edge("retry_strategist", "executor")

    graph.add_edge("trivial_respond", END)
    graph.add_edge("clarifier", END)
    graph.add_edge("format_output", END)

    return graph.compile()
