from engine.research.models import MethodRef

METHOD_LABELS: dict[str, str] = {
    "overfit.walk": "走样检验",
    "stability.oos": "样本外稳定",
    "crowding.load": "拥挤度",
    "cost.turnover": "换手成本",
}


def format_methods_display(methods: tuple[MethodRef, ...] | None) -> str:
    if not methods:
        return ""
    return " · ".join(METHOD_LABELS.get(method.method_id, method.method_id) for method in methods)
