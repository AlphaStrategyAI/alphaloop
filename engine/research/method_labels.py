from engine.research.display_names import method_label
from engine.research.models import MethodRef


def format_methods_display(methods: tuple[MethodRef, ...] | None) -> str:
    if not methods:
        return ""
    return " · ".join(method_label(method.method_id) for method in methods)
