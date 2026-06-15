"""Feedback detection and classification."""

from dataclasses import dataclass, asdict
from typing import Optional
import logging
import re
import json

from anthropic import Anthropic

from ..config import config

logger = logging.getLogger(__name__)


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

    # STRONG negative feedback — clearly about the assistant's RESPONSE quality.
    NEGATIVE_PATTERNS = [
        # Russian
        r"слишком (длинн|коротк|сложн|прост|многословн)",
        r"не (понял|понятно|то|так|верно|правильно)",
        r"(плохо|ужасно|отвратительно|некачественно)",
        r"можно (короче|проще|понятнее|лучше|яснее)",
        r"это (бред|чушь|ерунда|неправда)",
        r"твой ответ",
        r"(запутал|непонятно объясн)",
        # English
        r"too (long|short|complex|simple|verbose)",
        r"(bad|terrible|awful|poor) (answer|response|explanation)",
        r"(confusing|unclear|hard to understand)",
        r"your (answer|response|reply)",
        r"not (what I (asked|wanted|meant))",
    ]

    # AMBIGUOUS imperatives — could be feedback about the response OR a work task
    # ("исправь баг в X"). Only treated as feedback when the message is NOT a task.
    WEAK_IMPERATIVE_PATTERNS = [
        r"\b(переделай|исправь|измени|перепиши)\b",
        r"\b(fix|redo|change|improve|rewrite) (this|it|that)\b",
    ]

    # Signals that an imperative is a TASK (about code/files), not self-feedback.
    TASK_SIGNAL_PATTERN = (
        r"```|\b[\w./-]+\.(py|js|ts|tsx|jsx|md|json|ya?ml|go|rs|java|cpp|cc|c|h|html|css|sql|sh)\b"
        r"|[/\\]|\b(баг|bug|функци|метод|класс|тест|файл|строк|переменн|импорт|endpoint|"
        r"api|команд|function|method|class|test|file|line|variable|import|module|модул|"
        r"таблиц|table|запрос|query|скрипт|script|конфиг|config)\b"
    )

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
        self._weak_imperative_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.WEAK_IMPERATIVE_PATTERNS
        ]
        self._task_signal = re.compile(self.TASK_SIGNAL_PATTERN, re.IGNORECASE)

    def _looks_like_task(self, message: str) -> bool:
        """True if the message references code/files → it's a work task, not
        feedback about the assistant's own response."""
        return bool(self._task_signal.search(message))

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

        # Strong negative — clearly about the response
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

        # Ambiguous imperative ("исправь/fix this"): a WORK TASK if it references
        # code/files → NOT self-feedback (prevents prompt drift from normal commands).
        if (not positive_match
                and self._match_patterns(message, self._weak_imperative_patterns)):
            if self._looks_like_task(message):
                return None  # task for the agent, not feedback about it
            # Genuinely ambiguous & short → let the LLM disambiguate if possible.
            if self.client and len(message.split()) < 15:
                return self._llm_detect(message)
            # No LLM: record as low-confidence negative (below trigger threshold).
            return Feedback(
                type="negative",
                category=self._detect_category(message_lower),
                raw_text=message,
                confidence=0.5,
                triggered_improvement=False,
            )

        # Neither - could be implicit feedback; use LLM for short messages.
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

        except Exception as e:
            # Fallback - if LLM fails, don't block but log the error
            logger.warning(f"LLM feedback detection failed: {e}")

        return None

    def is_feedback_message(self, message: str) -> bool:
        """Quick check if message likely contains feedback."""
        return self.detect(message) is not None
