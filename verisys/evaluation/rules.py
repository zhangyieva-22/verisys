"""Existing deterministic catalog signal validation and candidate policy."""
def _rationale(selection, subjects):
    code = selection.relevance_reason
    facts = [subject.facts for subject in subjects]
    if code == "supported_openai_calls":
        valid = all(fact.get("client_library") == "openai" and fact.get("call_sites") for fact in facts)
        return valid, "APPLICABLE", "SUPPORTED", "Supported concrete OpenAI calls were detected; explicit per-call timeout coverage is worth investigating. No timeout result has been determined."
    if code == "openai_wrapper_presence":
        valid = all(fact.get("client_library") in ("openai", "langchain_openai") and not fact.get("call_sites") for fact in facts)
        return valid, "UNKNOWN", "PARTIAL", "OpenAI client or wrapper presence was detected, without supported concrete call sites; timeout scope is uncertain."
    if code == "http_api_routes":
        valid = all(fact.get("method") and fact.get("path") and fact.get("source_location") for fact in facts)
        routes = ", ".join(f"{fact.get('method')} {fact.get('path')}" for fact in facts)
        return valid, "APPLICABLE", "NOT_AVAILABLE", f"{routes} are detected HTTP routes; latency under a defined workload is worth investigating. No latency has been measured."
    if code == "source_declared_retry_loop":
        valid = all(any(edge["source"] == edge["target"] and edge["type"] == "CONDITIONAL" and edge.get("condition")
                        for edge in fact.get("transitions", [])) for fact in facts)
        return valid, "UNKNOWN", "NOT_AVAILABLE", "Source-declared conditional workflow loops permit repeated actions; retry safety is worth investigating. Actual retries and side effects are not established."
    if code == "tool_candidates_in_workflow":
        flows = [subject for subject in subjects if subject.kind == "EXECUTION_FLOW"]
        groups = [{identifier for step in flow.facts.get("steps", []) if step["type"] == "TOOL_EXECUTION"
                   for identifier in step["candidate_tool_ids"]} for flow in flows]
        candidates = set().union(*groups) if groups else set()
        tools = [subject.id for subject in subjects if subject.kind == "TOOL"]
        valid = bool(groups) and all(groups) and all(identifier in candidates for identifier in tools)
        return valid, "UNKNOWN", "NOT_AVAILABLE", "Source-declared workflow tool candidates were detected; potential side-effect safety is worth investigating. Side effects, tool order, and per-request selection are not established."
    return False, "UNKNOWN", "NOT_AVAILABLE", ""
