"""Message grouping for advanced compaction."""

from dataclasses import dataclass


@dataclass
class MessageGroup:
    """A logical group of messages (one API round: user → assistant)."""
    messages: list[dict]
    estimated_tokens: int

    @property
    def summary_hint(self) -> str:
        for m in self.messages:
            if m["role"] == "user":
                content = m.get("content", "")
                return content[:100] + "..." if len(content) > 100 else content
        return ""


def group_messages_by_round(messages: list[dict]) -> list[MessageGroup]:
    """Group messages into API rounds (user msg → assistant response)."""
    groups: list[MessageGroup] = []
    current: list[dict] = []

    for msg in messages:
        if msg["role"] == "user" and current:
            groups.append(_make_group(current))
            current = []
        current.append(msg)

    if current:
        groups.append(_make_group(current))

    return groups


def _make_group(msgs: list[dict]) -> MessageGroup:
    total_chars = sum(len(m.get("content", "")) for m in msgs)
    return MessageGroup(messages=msgs, estimated_tokens=total_chars // 4)
