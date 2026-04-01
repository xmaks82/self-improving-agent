"""Secret scanner — detects credentials before sharing in team memory."""

import re
from dataclasses import dataclass

SECRET_RULES = [
    ("aws-access-key", r"\b((?:A3T[A-Z0-9]|AKIA|ASIA|ABIA|ACCA)[A-Z2-7]{16})\b"),
    ("github-pat", r"gh[ps]_[0-9a-zA-Z]{36,}"),
    ("anthropic-key", r"\bsk-ant-api\d+-[a-zA-Z0-9_\-]{20,}"),
    ("openai-key", r"\bsk-(?:proj|svcacct)-[A-Za-z0-9_\-]{20,}"),
    ("private-key", r"-----BEGIN[A-Z ]*PRIVATE KEY-----"),
    ("stripe-key", r"\b(?:sk|rk)_(?:test|live|prod)_[a-zA-Z0-9]{10,}"),
    ("slack-token", r"xox[bpe]-[0-9]{10,}"),
    ("groq-key", r"\bgsk_[a-zA-Z0-9]{20,}"),
    ("generic-secret", r"(?i)(?:password|secret|token|api.?key)\s*[:=]\s*['\"]?[a-zA-Z0-9_\-/.]{16,}"),
]

_compiled = [(rid, re.compile(pat)) for rid, pat in SECRET_RULES]


@dataclass
class SecretMatch:
    rule_id: str
    label: str


def scan_for_secrets(content: str) -> list[SecretMatch]:
    """Scan text for potential secrets. Returns list of matches."""
    matches = []
    seen: set[str] = set()
    for rule_id, pattern in _compiled:
        if rule_id not in seen and pattern.search(content):
            seen.add(rule_id)
            matches.append(SecretMatch(
                rule_id=rule_id,
                label=rule_id.replace("-", " ").title(),
            ))
    return matches
