"""Reply classification service for processing incoming outreach responses."""

import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from backend.config import settings
from backend.services.audit import AuditService


class ReplyClassification(str, Enum):
    """Possible classifications for incoming replies."""
    INTERESTED = "interested"
    NOT_INTERESTED = "not_interested"
    LATER = "later"
    REFERRAL = "referral"
    QUESTION = "question"
    OBJECTION = "objection"
    MEETING_BOOKED = "meeting_booked"
    MEETING_CANCELLED = "meeting_cancelled"
    OUT_OF_OFFICE = "out_of_office"
    UNKNOWN = "unknown"


@dataclass
class ClassificationResult:
    """Result of reply classification."""
    classification: ReplyClassification
    confidence: float  # 0.0 to 1.0
    reasoning: str
    suggested_response: Optional[str] = None
    escalate_to_owner: bool = False


class ReplyClassifier:
    """LLM-based reply classification with predefined responses and escalation logic."""

    def __init__(self):
        self.objection_responses = self._load_objection_responses()
        self.classification_patterns = self._load_classification_patterns()

    def _load_objection_responses(self) -> Dict[str, str]:
        """Load predefined responses for common objections."""
        # In a full implementation, these would come from config/database
        return {
            "price": "I understand budget is a concern. Let me share how our clients typically see ROI within 3 months, often covering the investment many times over.",
            "timing": "Timing is always tricky. Many clients find that starting now actually saves them time/money in the long run by avoiding [specific pain point].",
            "authority": "Absolutely, you should consult with [stakeholder]. I can prepare a brief summary to help make that conversation easier.",
            "need": "I hear you don't see the need right now. Most of our clients felt the same way until they discovered [specific benefit] they weren't aware of.",
            "trust": "Trust is earned, not given. I'd be happy to share case studies, references, or start with a small pilot to build confidence.",
            "competitor": "It's smart to evaluate options. What's most important to you in making this decision? I can help compare apples-to-apples.",
            "feature_missing": "That feature isn't in our current package, but we often add requested features based on client feedback. Let me check our roadmap.",
            "contract_length": "I understand the hesitation around long-term commitments. We offer flexible terms and can start with a shorter initial period.",
            "implementation": "Implementation concerns are valid. We provide dedicated support and typically have clients up and running within [timeframe].",
            "resource_intensive": "Actually, our solution is designed to be lightweight and save resources. Most clients spend less than [time] per week managing it."
        }

    def _load_classification_patterns(self) -> Dict[ReplyClassification, List[str]]:
        """Load regex patterns for each classification type."""
        return {
            ReplyClassification.INTERESTED: [
                r"(?i).*\b(interested|yes|definitely|absolutely|sounds good|count me in|let's do it|sign me up)\b.*",
                r"(?i).*\b(when can we start|how do we proceed|next steps|send contract|ready to move forward)\b.*",
                r"(?i).*\b(looks promising|this could work|i like this|this makes sense)\b.*"
            ],
            ReplyClassification.NOT_INTERESTED: [
                r"(?i).*\b(not interested|no thanks|don't want|not for us|pass|decline)\b.*",
                r"(?i).*\b(not a priority|not needed|don't need|waste of time|not worth it)\b.*",
                r"(?i).*\b(unsubscribe|remove me|stop contacting|do not contact)\b.*"
            ],
            ReplyClassification.LATER: [
                r"(?i).*\b(maybe later|not now|too busy|reach out again|follow up in|circle back|touch base later)\b.*",
                r"(?i).*\b(next quarter|next year|when things calm down|after [event])\b.*",
                r"(?i).*\b(currently overwhelmed|at capacity|plate is full)\b.*"
            ],
            ReplyClassification.REFERRAL: [
                r"(?i).*\b(someone else|talk to [name]|[name] handles this|you should speak with|try contacting)\b.*",
                r"(?i).*\b(I know someone|my colleague|my boss|our [department] person)\b.*",
                r"(?i).*\b(forwarding to|cc'ing|looping in)\b.*"
            ],
            ReplyClassification.QUESTION: [
                r"(?i).*\b(how|what|why|when|where|who|can you|could you|would you)\b.*\?.*",
                r"(?i).*\b(explain|clarify|tell me more|details|information|info)\b.*",
                r"(?i).*\b(does it|is there|are there|do you have)\b.*"
            ],
            ReplyClassification.MEETING_BOOKED: [
                r"(?i).*\b(meeting scheduled|booked the meeting|calendar invite|see you then|looking forward to meeting)\b.*",
                r"(?i).*\b(thanks for setting up|accepted the invite|confirmed for)\b.*",
                r"(?i).*\b(see you on|meeting confirmed|appointment set)\b.*"
            ],
            ReplyClassification.MEETING_CANCELLED: [
                r"(?i).*\b(cancel meeting|reschedule|can't make it|something came up|apologies but)\b.*\b(meeting|appointment|call)\b.*",
                r"(?i).*\b(let's postpone|need to change|have a conflict)\b.*"
            ],
            ReplyClassification.OUT_OF_OFFICE: [
                r"(?i).*\b(out of office|on vacation|away until|will respond|back on)\b.*",
                r"(?i).*\b(auto-reply|automatic|on leave|out today|not in office)\b.*"
            ]
        }

    def classify(self, reply_content: str) -> ClassificationResult:
        """
        Classify a reply using pattern matching and simple heuristics.

        In a full implementation, this would use an LLM API call.
        For MVP, we use rule-based classification with confidence scoring.
        """
        if not reply_content or not reply_content.strip():
            return ClassificationResult(
                classification=ReplyClassification.UNKNOWN,
                confidence=0.0,
                reasoning="Empty reply content",
                escalate_to_owner=False
            )

        reply_lower = reply_content.lower().strip()

        # Check each classification type
        best_match = ReplyClassification.UNKNOWN
        best_confidence = 0.0
        matched_patterns = []

        for classification, patterns in self.classification_patterns.items():
            match_count = 0
            for pattern in patterns:
                if re.search(pattern, reply_content):
                    match_count += 1

            if match_count > 0:
                # Confidence based on number of matching patterns
                confidence = min(0.5 + (match_count * 0.1), 0.95)  # Cap at 0.95 for rule-based
                if confidence > best_confidence:
                    best_confidence = confidence
                    best_match = classification
                    matched_patterns = [p for p in patterns if re.search(p, reply_content)]

        # Determine if we should escalate to owner (low confidence or complex cases)
        escalate_to_owner = best_confidence < 0.8

        # Generate reasoning
        if best_match == ReplyClassification.UNKNOWN:
            reasoning = "No clear patterns matched in reply content"
        else:
            reasoning = f"Matched {len(matched_patterns)} patterns for {best_match.value}"

        # Get suggested response if applicable
        suggested_response = None
        if best_match == ReplyClassification.OBJECTION:
            # Try to identify which type of objection
            objection_type = self._identify_objection_type(reply_content)
            if objection_type and objection_type in self.objection_responses:
                suggested_response = self.objection_responses[objection_type]

        return ClassificationResult(
            classification=best_match,
            confidence=best_confidence,
            reasoning=reasoning,
            suggested_response=suggested_response,
            escalate_to_owner=escalate_to_owner
        )

    def _identify_objection_type(self, reply_content: str) -> Optional[str]:
        """Try to identify the specific type of objection from the reply."""
        reply_lower = reply_content.lower()

        objection_keywords = {
            "price": ["price", "cost", "expensive", "budget", "afford", "too much", "overpriced"],
            "timing": ["time", "timing", "busy", "schedule", "not now", "later", "delay"],
            "authority": ["boss", "manager", "director", "vp", "ceo", "partner", "committee", "team", "stakeholder"],
            "need": ["need", "necessary", "required", "problem", "issue", "challenge", "pain point"],
            "trust": ["trust", "reliable", "proven", "track record", "reference", "case study", "guarantee"],
            "competitor": ["competitor", "alternative", "option", "other", "compare", "vs", "versus"],
            "feature_missing": ["feature", "functionality", "capability", "does it do", "can it", "missing"],
            "contract_length": ["contract", "term", "length", "duration", "commitment", "long term", "years"],
            "implementation": ["implement", "setup", "install", "deploy", "configuration", "complex", "difficult"],
            "resource_intensive": ["resource", "staff", "personnel", "time consuming", "effort", "maintenance", "work"]
        }

        for objection_type, keywords in objection_keywords.items():
            if any(keyword in reply_lower for keyword in keywords):
                return objection_type

        return None

    def get_objection_response(self, objection_type: str) -> Optional[str]:
        """Get a predefined response for a specific objection type."""
        return self.objection_responses.get(objection_type)


# Global instance
reply_classifier = ReplyClassifier()