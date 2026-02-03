__all__ = ["FeedbackSystem", "get_root_agent"]


def __getattr__(name: str):
    if name == "utils":
        import importlib
        return importlib.import_module("feedback_agent.utils")
    if name in ("FeedbackSystem", "get_root_agent"):
        from .agent import FeedbackSystem, get_root_agent
        return {"FeedbackSystem": FeedbackSystem, "get_root_agent": get_root_agent}[name]
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
