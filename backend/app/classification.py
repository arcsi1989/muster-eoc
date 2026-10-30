"""Data classification before anything reaches a model (PRD section 08, CR-03 C1). The data
contracts give every field a data class; `for_model` is the one filter, applied where a model is
shown data: a generation task's input and every copilot tool result. It drops restricted fields
by name at any depth, so maps and coordinates stay in the UI (docs/decisions.md)."""

from typing import cast

from pydantic import BaseModel

from app.ingest import contracts
from app.ingest.contracts import DataClass

# Views of the dependency graph that no contract names as a field: everything an asset feeds,
# is fed by, and how many assets feed a dependant. Restricted like the edge list itself; the one
# dependency behind a finding is internal and stays in that finding's own text.
GRAPH_VIEWS = frozenset({"feeds", "fed_by", "downstream_assets", "feeders"})


def data_classes(model: type[BaseModel]) -> dict[str, DataClass]:
    """The data class of each field of a contract that declares one."""
    classes = {}
    for name, info in model.model_fields.items():
        extra = info.json_schema_extra
        if isinstance(extra, dict) and "data_class" in extra:
            classes[name] = cast(DataClass, extra["data_class"])
    return classes


def contract_models() -> list[type[contracts.Contract]]:
    """Every data contract, without their shared base."""
    return [
        m
        for m in vars(contracts).values()
        if isinstance(m, type) and issubclass(m, contracts.Contract) and m is not contracts.Contract
    ]


def _restricted_keys() -> frozenset[str]:
    """Every field name a contract classes restricted. A name is restricted in every contract or
    in none, so the filter can go by name."""
    models = contract_models()
    restricted = {n for m in models for n, c in data_classes(m).items() if c == "restricted"}
    for model in models:
        for name, data_class in data_classes(model).items():
            if name in restricted and data_class != "restricted":
                raise ValueError(f"{model.__name__}.{name} is {data_class}, restricted elsewhere")
    return frozenset(restricted) | GRAPH_VIEWS


RESTRICTED_KEYS = _restricted_keys()


def for_model[T](data: T) -> T:
    """`data` without its restricted fields, at any depth: what a model may be shown."""
    if isinstance(data, dict):
        return cast(T, {k: for_model(v) for k, v in data.items() if k not in RESTRICTED_KEYS})
    if isinstance(data, list):
        return cast(T, [for_model(v) for v in data])
    return data
