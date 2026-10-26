"""Only a committed order can enter this channel; routing is explicit."""
from .game import ORDERS


def deliver(order, mode, *, recipient, permitted_recipient, rng):
    if recipient != permitted_recipient:
        raise ValueError("recipient_not_permitted")
    if order not in ORDERS:
        raise ValueError("invalid_order")
    if mode == "actual":
        return order
    if mode == "random":
        return rng.choice(ORDERS)
    raise ValueError("unsupported_channel")
