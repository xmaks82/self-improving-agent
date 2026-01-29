"""Feedback detection and classification."""

from dataclasses import dataclass, asdict
from typing import Optional
import re
import json

from anthropic import Anthropic

from ..config import config


@dataclass
class Feedback:
    """Detected feedback from user message."""
    type: str              # "positive", "negative", "neutral"
    category: str          # "verbosity", "accuracy", "clarity", "format", "tone", "general"
    raw_text: str          # Original message text
    confidence: float      # Detection confidence (0.0 - 1.0)
    triggered_improvement: bool = False

    @property
    def should_trigger_improvement(self) -> bool:
        """Determine if this feedback should trigger an improvement cycle."""
        # Trigger on negative feedback with high confidence
        if self.type == "negative" and self.confidence >= config.thresholds.feedback_confidence:
            return True
        # Also trigger on explicit feedback
        if self.category == "explicit":
            return True
        return False

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(asdict(self), ensure_ascii=False)


class FeedbackDetector:
    """
    Detects and classifies feedback in user messages.

    Uses a combination of:
    1. Pattern matching (fast, cheap) - primary method
    2. LLM classification (accurate, expensive) - fallback for unclear cases
    """

    # Negative feedback patterns (Russian and English)
    NEGATIVE_PATTERNS = [
        # Russian
        r"слишком (длинн|коротк|сложн|прост|многословн)",
        r"не (понял|понятно|то|так|верно|правильно)",
        r"(плохо|ужасно|отвратительно|некачественно)",
        r"(неправильн|ошиб|некорректн|неверн)",
        r"можно (короче|проще|понятнее|лучше|яснее)",
        r"это (бред|чушь|ерунда|неправда)",
        r"не (работает|помогло|подходит)",
        r"(переделай|исправь|измени)",
        r"(запутал|непонятн|сложн)",
        # English
        r"too (long|short|complex|simple|verbose)",
        r"(wrong|incorrect|inaccurate|false)",
        r"(bad|terrible|awful|poor)",
        r"(confusing|unclear|hard to understand)",
        r"(fix|redo|change|improve) (this|it|that)",
        r"doesn'?t (work|help|make sense)",
        r"not (right|correct|what I (asked|wanted|meant))",
    ]

    # Positive feedback patterns
    POSITIVE_PATTERNS = [
        # Russian
        r"(спасибо|благодар)",
        r"(отлично|супер|круто|класс|здорово|прекрасно)",
        r"(помогло|работает|получилось|понял)",
        r"то что нужно",
        r"(идеально|perfect|великолепно)",
        r"(хорошо|норм|нормально|ок|okay)",
        # English
        r"(thanks|thank you)",
        r"(great|excellent|awesome|perfect|wonderful)",
        r"(helped|works|worked|got it)",
        r"(exactly|just) what I (needed|wanted)",
        r"(good|nice|well done)",
    ]

    # Category keywords for classification
    CATEGORY_KEYWORDS = {
        "verbosity": [
            "длинн", "коротк", "многословн", "кратк", "подробн",
            "long", "short", "verbose", "brief", "concise", "detailed"
        ],
        "accuracy": [
            "неправильн", "ошиб", "некорректн", "неверн", "правильн",
            "wrong", "incorrect", "error", "mistake", "accurate", "right"
        ],
        "clarity": [
            "понятн", "ясн", "сложн", "запутан", "прост",
            "clear", "unclear", "confusing", "simple", "understand"
        ],
        "format": [
            "формат", "оформлен", "структур", "код", "список",
            "format", "structure", "code", "list", "layout"
        ],
        "tone": [
            "тон", "грубо", "формальн", "неформальн", "вежлив",
            "tone", "rude", "formal", "informal", "polite"
        ],
        "relevance": [
            "не то", "не о том", "другое", "тему", "вопрос",
            "off-topic", "irrelevant", "different", "topic", "question"
        ],
    }

    def __init__(self, client: Optional[Anthropic] = None):
        """
        Initialize feedback detector.

        Args:
            client: Anthropic client for LLM fallback (optional)
        """
        self.client = client

        # Compile patterns for efficiency
        self._negative_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.NEGATIVE_PATTERNS
        ]
        self._positive_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.POSITIVE_PATTERNS
        ]

    def detect(self, message: str) -> Optional[Feedback]:
        """
        Detect feedback in a user message.

        Args:
            message: User's input message

        Returns:
            Feedback object if feedback detected, None otherwise
        """
        message_lower = message.lower()

        # Quick pattern matching
        negative_match = self._match_patterns(message, self._negative_patterns)
        positive_match = self._match_patterns(message, self._positive_patterns)

        # Negative feedback detected
        if negative_match and not positive_match:
            category = self._detect_category(message_lower)
            return Feedback(
                type="negative",
                category=category,
                raw_text=message,
                confidence=0.85,
                triggered_improvement=True,
            )

        # Positive feedback detected
        if positive_match and not negative_match:
            return Feedback(
                type="positive",
                category=self._detect_category(message_lower),
                raw_text=message,
                confidence=0.80,
                triggered_improvement=False,
            )

        # Both or neither - could be implicit feedback
        # Use LLM if message is short (likely feedback) and client available
        if len(message.split()) < 15 and self.client:
            return self._llm_detect(message)

        return None

    def _match_patterns(self, text: str, patterns: list) -> bool:
        """Check if text matches any pattern."""
        for pattern in patterns:
            if pattern.search(text):
                return True
        return False

    def _detect_category(self, text: str) -> str:
        """Detect feedback category based on keywords."""
        text_lower = text.lower()

        category_scores = {}
        for category, keywords in self.CATEGORY_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in text_lower)
            if score > 0:
                category_scores[category] = score

        if category_scores:
            return max(category_scores, key=category_scores.get)

        return "general"

    def _llm_detect(self, message: str) -> Optional[Feedback]:
        """
        Use LLM to detect implicit feedback.

        This is called for short messages that didn't match patterns.
        """
        if not self.client:
            return None

        try:
            response = self.client.messages.create(
                model=config.models.feedback,
                max_tokens=150,
                messages=[{
                    "role": "user",
                    "content": f"""Classify this message as feedback about an AI assistant's response or a regular query/statement.

Message: "{message}"

Reply ONLY with a JSON object (no other text):
{{"is_feedback": true/false, "type": "positive"/"negative"/"neutral", "category": "verbosity"/"accuracy"/"clarity"/"format"/"tone"/"general", "confidence": 0.0-1.0}}

If it's NOT feedback about the AI's previous response, set is_feedback to false."""
                }]
            )

            # Parse response
            response_text = response.content[0].text.strip()

            # Try to extract JSON
            json_match = re.search(r'\{[^}]+\}', response_text)
            if json_match:
                data = json.loads(json_match.group())

                if not data.get("is_feedback", False):
                    return None

                return Feedback(
                    type=data.get("type", "neutral"),
                    category=data.get("category", "general"),
                    raw_text=message,
                    confidence=float(data.get("confidence", 0.5)),
                    triggered_improvement=data.get("type") == "negative",
                )

        except Exception:
            # Fallback - if LLM fails, don't block
            pass

        return None

    def is_feedback_message(self, message: str) -> bool:
        """Quick check if message likely contains feedback."""
        return self.detect(message) is not None
