"""Money value objects."""

from dataclasses import dataclass
from enum import StrEnum

from financial_workflow.domain.errors import DomainInvariantError


class Currency(StrEnum):
    """ISO 4217 currencies intentionally supported by the MVP."""

    BRL = "BRL"
    EUR = "EUR"
    GBP = "GBP"
    USD = "USD"


@dataclass(frozen=True, slots=True)
class Money:
    """A positive amount represented in the currency's minor units."""

    amount_minor: int
    currency: Currency

    def __post_init__(self) -> None:
        if isinstance(self.amount_minor, bool) or self.amount_minor <= 0:
            raise DomainInvariantError("Money amount must be a positive integer")
        if not isinstance(self.currency, Currency):
            raise DomainInvariantError("Money currency must be explicitly supported")

