"""Errors raised when a domain invariant would be violated."""

from uuid import UUID


class DomainInvariantError(ValueError):
    """A command attempted to create an invalid domain state."""


class InvalidPaymentTransitionError(DomainInvariantError):
    """A payment cannot move between the requested states."""

    def __init__(self, payment_id: UUID, current: str, target: str) -> None:
        self.payment_id = payment_id
        self.current = current
        self.target = target
        super().__init__(
            f"Payment {payment_id} cannot transition from {current} to {target}"
        )

