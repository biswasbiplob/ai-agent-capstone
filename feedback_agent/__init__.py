try:
    from .agent import FeedbackSystem, get_root_agent
    __all__ = ["FeedbackSystem", "get_root_agent"]
except ModuleNotFoundError as exc:
    if exc.name and exc.name.startswith("google.adk"):
        __all__ = []
    else:
        raise
