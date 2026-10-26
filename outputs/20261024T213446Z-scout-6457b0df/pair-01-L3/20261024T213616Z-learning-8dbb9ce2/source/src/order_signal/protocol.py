"""One sender decision, channel delivery, one receiver decision; fresh contexts."""

from dataclasses import dataclass
from .channels import deliver
from .game import execute, score, metrics
from .versions import VERSIONS

VERSION = VERSIONS["protocol_version"]


@dataclass(frozen=True)
class SenderObservation:
    secret: int
    objective: str


@dataclass(frozen=True)
class ReceiverObservation:
    order: str
    objective: str


@dataclass(frozen=True)
class Agent:
    identifier: str
    role: str
    display_name: str


def play(*, secret, condition, agents, rng, decide, record):
    sender, receiver = agents
    actual = decide(sender, SenderObservation(secret, condition["objective"]))
    record["actual_order"] = actual
    execution = execute(actual)
    record["execution"] = {
        "actions": list(execution.actions),
        "completed": sorted(execution.completed),
        "cost": execution.cost,
    }
    observed = deliver(
        actual,
        condition["delivery"],
        recipient=receiver.identifier,
        permitted_recipient=receiver.identifier,
        rng=rng,
    )
    record["delivered_observation"] = {
        "order": observed,
        "recipient": receiver.identifier,
    }
    choice = decide(receiver, ReceiverObservation(observed, condition["objective"]))
    record["choice"] = choice
    record["rewards"] = score(secret, choice, sender.identifier, receiver.identifier)
    record["metrics"] = metrics(record["rewards"])
    record["outcome"] = (
        "pass"
        if choice == "pass"
        else ("correct" if choice == str(secret) else "wrong")
    )
    record["status"] = "completed"
