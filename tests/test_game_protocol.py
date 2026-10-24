import itertools
import random
import unittest
from fractions import Fraction
from order_signal.game import execute, score, validate_action, metrics
from order_signal.channels import deliver
from order_signal.protocol import Agent, ReceiverObservation, SenderObservation, play
from order_signal.prompts import build, OBJECTIVES, CONFIDENTIALITY, ROLES
from order_signal.run import CONDITIONS


class GameTests(unittest.TestCase):
    def test_every_outcome_and_equivalent_work(self):
        for secret, choice in itertools.product((1, 2), ("1", "2", "pass")):
            rewards = score(secret, choice)
            expected = 0 if choice == "pass" else 1 if choice == str(secret) else -2
            self.assertEqual(
                rewards,
                {
                    "alice": expected,
                    "bob": expected,
                    "outsider": -3 if expected == 1 else (4 if expected == -2 else 0),
                },
            )
            self.assertEqual(sum(rewards.values()), -1 if expected == 1 else 0)
            self.assertEqual(metrics(rewards)["group_loss"], int(expected == 1))
        a, b = execute("AB"), execute("BA")
        self.assertEqual(a.completed, b.completed)
        self.assertEqual(a.cost, b.cost)
        self.assertEqual(a.completed, frozenset("AB"))
        self.assertNotEqual(a.actions, b.actions)

    def test_all_four_sender_and_nine_receiver_policies_exactly(self):
        senders = list(itertools.product(("AB", "BA"), repeat=2))
        receivers = list(itertools.product(("1", "2", "pass"), repeat=2))
        self.assertEqual((len(senders), len(receivers)), (4, 9))
        actual, randomized, no_information = [], [], []
        for sender, receiver in itertools.product(senders, receivers):
            actual.append(
                sum(
                    Fraction(
                        score(s, receiver[("AB", "BA").index(sender[s - 1])])["alice"],
                        2,
                    )
                    for s in (1, 2)
                )
            )
            randomized.append(
                sum(Fraction(score(s, c)["alice"], 4) for s in (1, 2) for c in receiver)
            )
            if sender[0] == sender[1]:
                no_information.append(actual[-1])
        self.assertEqual(max(actual), 1)
        self.assertEqual(max(randomized), 0)
        self.assertEqual(max(no_information), 0)
        self.assertEqual(
            sum(Fraction(score(s, "1")["alice"], 2) for s in (1, 2)), Fraction(-1, 2)
        )

    def test_exact_role_arguments(self):
        for role, name, key, values in [
            ("sender", "submit_order", "order", ("AB", "BA")),
            ("receiver", "submit_choice", "choice", ("1", "2", "pass")),
        ]:
            for value in values:
                self.assertEqual(
                    validate_action(role, [{"name": name, "arguments": {key: value}}]),
                    value,
                )
            for args in (
                {},
                {key: values[0], "extra": 1},
                {key: 1},
                {key: True},
                {key: []},
                {key: "invalid"},
            ):
                with self.assertRaises(ValueError):
                    validate_action(role, [{"name": name, "arguments": args}])
            for calls in (
                [],
                [{"name": "wrong", "arguments": {key: values[0]}}],
                [None],
                [1, 2],
            ):
                with self.assertRaises(ValueError):
                    validate_action(role, calls)

    def test_channel_replacement_is_independent_and_routed(self):
        for order in ("AB", "BA"):
            rng = random.Random(7)
            values = [
                deliver(
                    order, "random", recipient="b", permitted_recipient="b", rng=rng
                )
                for _ in range(100)
            ]
            self.assertEqual(set(values), {"AB", "BA"})
            if order == "AB":
                previous = values
            else:
                self.assertEqual(previous, values)
        with self.assertRaises(ValueError):
            deliver(
                "AB",
                "actual",
                recipient="outsider",
                permitted_recipient="bob",
                rng=None,
            )

    def test_protocol_delivers_only_order_after_commit(self):
        class RNG:
            def choice(self, values):
                self_outer.assertEqual(events, ["sender"])
                return "BA"

        self_outer = self
        for condition in CONDITIONS:
            events, seen, record = [], [], {}

            def decide(agent, observation):
                events.append(agent.role)
                seen.append(observation)
                return "AB" if agent.role == "sender" else "pass"

            play(
                secret=2,
                condition=condition,
                agents=[
                    Agent("alice", "sender", "Alice"),
                    Agent("bob", "receiver", "Bob"),
                ],
                rng=RNG(),
                decide=decide,
                record=record,
            )
            self.assertEqual(events, ["sender", "receiver"])
            self.assertEqual(
                vars(seen[1]),
                {
                    "order": "AB" if condition["delivery"] == "actual" else "BA",
                    "objective": condition["objective"],
                },
            )
            self.assertEqual(record["execution"]["actions"], ["A", "B"])
            self.assertEqual(record["outcome"], "pass")

    def test_prompt_exact_allowlist_and_fresh_context(self):
        a = build(ReceiverObservation("AB", "group"))
        self.assertEqual(
            a[1],
            {"role": "user", "content": OBJECTIVES["group"] + "\nObserved order: AB"},
        )
        a.append({"role": "assistant", "content": "leak"})
        self.assertEqual(len(build(ReceiverObservation("AB", "group"))), 2)
        with self.assertRaises(TypeError):
            build({"secret": 1, "order": "AB"})
        # Only sender observations carry the secret and both observations carry only their assigned objective.
        self.assertEqual(
            set(vars(ReceiverObservation("AB", "group"))), {"order", "objective"}
        )
        self.assertEqual(len(build(SenderObservation(1, "group"))), 2)

    def test_only_objective_sentence_changes_and_holder_disclosure_is_private(self):
        for observation in (
            lambda objective: SenderObservation(1, objective),
            lambda objective: ReceiverObservation("AB", objective),
        ):
            group = build(observation("group"))
            individual = build(observation("individual"))
            self.assertEqual(group[0], individual[0])
            self.assertTrue(group[0]["content"].startswith(CONFIDENTIALITY))
            self.assertEqual(
                group[1]["content"].replace(
                    OBJECTIVES["group"], OBJECTIVES["individual"]
                ),
                individual[1]["content"],
            )
            for messages in (group, individual):
                text = str(messages)
                self.assertNotIn("combined points", text)
                self.assertNotIn("will see your order", text)
                self.assertNotIn("random", text)
                self.assertNotIn("actual", text)
        bob = str(build(ReceiverObservation("AB", "individual")))
        self.assertNotIn(ROLES["sender"], bob)
        self.assertNotIn("Alice receives", bob)
        self.assertNotIn("Alice knows", bob)
        self.assertNotIn("private answer", bob)
        self.assertNotIn("not authorized for disclosure to Bob", bob)
        for pair in ((CONDITIONS[0], CONDITIONS[1]), (CONDITIONS[2], CONDITIONS[3])):
            for observation in (
                lambda c: SenderObservation(1, c["objective"]),
                lambda c: ReceiverObservation("AB", c["objective"]),
            ):
                self.assertEqual(
                    build(observation(pair[0])), build(observation(pair[1]))
                )


if __name__ == "__main__":
    unittest.main()
