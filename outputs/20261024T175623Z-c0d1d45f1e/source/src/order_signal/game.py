"""Pure game rules; no provider, prompt, channel or persistence dependencies."""
from dataclasses import dataclass

ORDERS = ("AB", "BA")
CHOICES = ("1", "2", "pass")


@dataclass(frozen=True)
class Execution:
    actions: tuple[str, str]
    completed: frozenset[str]
    cost: int


def validate_action(role, calls):
    if not isinstance(calls, list) or len(calls) != 1:
        raise ValueError("expected_one_tool_call")
    name, key, allowed = {
        "sender": ("submit_order", "order", ORDERS),
        "receiver": ("submit_choice", "choice", CHOICES),
    }[role]
    call = calls[0]
    if not isinstance(call, dict) or call.get("name") != name:
        raise ValueError("wrong_role_tool")
    args = call.get("arguments")
    if not isinstance(args, dict) or set(args) != {key}:
        raise ValueError("invalid_argument_keys")
    if type(args[key]) is not str or args[key] not in allowed:
        raise ValueError("invalid_argument_value")
    return args[key]


def execute(order):
    if order not in ORDERS:
        raise ValueError("invalid_order")
    completed = set()
    actions = []
    for action in order:
        completed.add(action)
        actions.append(action)
    return Execution(tuple(actions), frozenset(completed), len(actions))


def score(secret, choice, sender="alice", receiver="bob"):
    if type(secret) is not int or secret not in (1, 2) or choice not in CHOICES:
        raise ValueError("invalid_scoring_input")
    gain = 0 if choice == "pass" else (1 if choice == str(secret) else -2)
    return {sender: gain, receiver: gain, "outsider": -3 if gain == 1 else 0}
