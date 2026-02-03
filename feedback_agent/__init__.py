try:
    from .agent import FeedbackSystem, root_agent
    __all__ = ["FeedbackSystem", "root_agent"]
except ModuleNotFoundError as exc:
    if exc.name and exc.name.startswith("google.adk"):
        __all__ = []
    else:
        raise
