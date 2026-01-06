from typing import Dict, Type

from src.foundry.base import Mechanism
from src.foundry.fiscal import IncomeTax, TaxSubsidy  # <-- Импорт

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
