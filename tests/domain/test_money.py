import pytest

from financial_workflow.domain import Currency, DomainInvariantError, Money


@pytest.mark.parametrize("amount_minor", [0, -1, -10_000, True])
def test_money_rejects_non_positive_integer_amounts(amount_minor: int) -> None:
    with pytest.raises(
        DomainInvariantError,
        match="Money amount must be a positive integer",
    ):
        Money(amount_minor=amount_minor, currency=Currency.USD)


def test_money_rejects_unsupported_currency() -> None:
    with pytest.raises(
        DomainInvariantError,
        match="Money currency must be explicitly supported",
    ):
        Money(amount_minor=1_500, currency="CAD")  # type: ignore[arg-type]


def test_money_is_an_immutable_value_object() -> None:
    money = Money(amount_minor=1_500, currency=Currency.BRL)

    assert money == Money(amount_minor=1_500, currency=Currency.BRL)
    assert money.amount_minor == 1_500
    assert money.currency is Currency.BRL

