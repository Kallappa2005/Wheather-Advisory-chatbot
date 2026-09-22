from pathlib import Path
from langgraph.graph import END, START, StateGraph

from app.graph.nodes import GraphDependencies, fetch_weather, generate_response, handle_location_failure, handle_no_policy, handle_weather_failure, match_sops, parse_request, resolve_location, select_applicable_policy
from app.graph.state import AdvisoryState


def build_graph(deps: GraphDependencies):
    graph = StateGraph(AdvisoryState)
    graph.add_node("parse_request", lambda state: parse_request(state, deps))
    graph.add_node("resolve_location", lambda state: resolve_location(state, deps))
    graph.add_node("fetch_weather", lambda state: fetch_weather(state, deps))
    graph.add_node("match_sops", lambda state: match_sops(state, deps))
    graph.add_node("select_policy", lambda state: select_applicable_policy(state, deps))
    graph.add_node("generate_response", lambda state: generate_response(state, deps))
    graph.add_node("handle_no_policy", lambda state: handle_no_policy(state, deps))
    graph.add_node("handle_weather_failure", lambda state: handle_weather_failure(state, deps))
    graph.add_node("handle_location_failure", lambda state: handle_location_failure(state, deps))

    graph.add_edge(START, "parse_request")
    graph.add_edge("parse_request", "resolve_location")
    graph.add_conditional_edges("resolve_location", lambda state: "location_failure" if state.get("location_error") else "location_success", {"location_failure": "handle_location_failure", "location_success": "fetch_weather"})
    graph.add_conditional_edges("fetch_weather", lambda state: "weather_failure" if state.get("weather_error") else "weather_success", {"weather_failure": "handle_weather_failure", "weather_success": "match_sops"})
    graph.add_edge("match_sops", "select_policy")
    graph.add_conditional_edges("select_policy", lambda state: "policy_found" if state.get("selected_policy") else "no_policy", {"policy_found": "generate_response", "no_policy": "handle_no_policy"})
    graph.add_edge("generate_response", END)
    graph.add_edge("handle_no_policy", END)
    graph.add_edge("handle_weather_failure", END)
    graph.add_edge("handle_location_failure", END)
    return graph.compile()
