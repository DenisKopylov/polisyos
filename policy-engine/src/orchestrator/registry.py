from typing import Dict, Type, Any

from src.foundry.base import Mechanism
from src.foundry.fiscal import IncomeTax, TaxSubsidy  # <-- Импорт
# Импортируем типы из IR
from src.policy_ir.contract import Intervention

# Словарь: "строка из JSON" -> Класс Python
MECHANISM_REGISTRY: Dict[str, Type[Mechanism]] = {
    "tax_subsidy": TaxSubsidy,
    "income_tax": IncomeTax,  # <-- Регистрация
}


def get_mechanism_class(mech_type: str) -> Type[Mechanism]:
    if mech_type not in MECHANISM_REGISTRY:
        raise ValueError(
            f"Unknown mechanism type: '{mech_type}'. Available: {list(MECHANISM_REGISTRY.keys())}"
        )
    return MECHANISM_REGISTRY[mech_type]


def create_mechanism(intervention: Intervention, n_agents: int) -> Mechanism:
    """Фабрика: превращает описание меры в живой объект Foundry."""
    mech_cls = MECHANISM_REGISTRY.get(intervention.mechanism_type)
    if not mech_cls:
        raise ValueError(f"Unknown mechanism: {intervention.mechanism_type}")

    # Превращаем параметры из dict в kwargs
    # Важно: здесь мы предполагаем, что параметры в IR совпадают с аргументами __init__
    return mech_cls(n_agents=n_agents, **intervention.parameters)
