"""Incompatible revisions must never be pooled or silently reinterpreted."""

VERSIONS = {
    "design_version": "order-signal-design-v3",
    "protocol_version": "sender-channel-receiver-v2",
    "prompt_version": "order-signal-prompts-v3",
    "payoff_version": "penalty-transfer-v2",
    "analysis_version": "joint-hoeffding-diagnostics-v3",
}


def require_versions(value):
    if any(value.get(key) != expected for key, expected in VERSIONS.items()):
        raise ValueError("unsupported_or_mixed_versions")
