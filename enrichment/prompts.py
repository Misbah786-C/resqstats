"""Prompt + label normalization for the emergency call classifier.

The LLM's ONLY job: unstructured bilingual text -> {incident_type, severity}.
It never computes numbers (AGENTS.md rule).
"""

INCIDENT_TYPES = [
    "road_accident", "cardiac", "heat_stroke", "violence",
    "fall", "respiratory", "maternity", "other",
]
SEVERITIES = ["critical", "serious", "moderate", "minor"]

SYSTEM_PROMPT = f"""You classify emergency ambulance call transcripts from Karachi, Pakistan.
Calls are a mix of English and Roman Urdu (Urdu written in Latin letters).

Classify each call into exactly one incident_type and one severity.

incident_type must be one of: {", ".join(INCIDENT_TYPES)}
severity must be one of: {", ".join(SEVERITIES)}

Severity guide:
- critical: life-threatening right now (unconscious, severe bleeding, not breathing, chest pain)
- serious: urgent, could become life-threatening (heavy bleeding, labour, collapse)
- moderate: needs hospital but stable
- minor: small injuries, stable patient

Examples:
Call: "Accident hua hai Korangi mein, bike wala gir gaya hai, khoon beh raha hai"
Answer: {{"incident_type": "road_accident", "severity": "serious"}}

Call: "Mere walid ko seenay mein dard ho raha hai, saans nahi aa rahi, Lyari"
Answer: {{"incident_type": "cardiac", "severity": "critical"}}

Call: "Garmi se banda behosh ho gaya hai Saddar mein, bahar kaam kar raha tha"
Answer: {{"incident_type": "heat_stroke", "severity": "serious"}}

Reply with ONLY a JSON object: {{"incident_type": "...", "severity": "..."}}
No explanation, no extra text."""

# Map common LLM label variations back to our canonical labels
TYPE_SYNONYMS = {
    "accident": "road_accident",
    "traffic_accident": "road_accident",
    "rta": "road_accident",
    "heart": "cardiac",
    "heart_attack": "cardiac",
    "heatstroke": "heat_stroke",
    "heat": "heat_stroke",
    "assault": "violence",
    "fight": "violence",
    "breathing": "respiratory",
    "asthma": "respiratory",
    "pregnancy": "maternity",
    "labour": "maternity",
    "labor": "maternity",
    "delivery": "maternity",
    "unknown": "other",
}

SEVERITY_SYNONYMS = {
    "severe": "critical",
    "urgent": "serious",
    "medium": "moderate",
    "mild": "minor",
    "low": "minor",
}


def normalize_type(value: str | None) -> str | None:
    if not value:
        return None
    v = value.strip().lower().replace(" ", "_").replace("-", "_")
    if v in INCIDENT_TYPES:
        return v
    return TYPE_SYNONYMS.get(v)


def normalize_severity(value: str | None) -> str | None:
    if not value:
        return None
    v = value.strip().lower()
    if v in SEVERITIES:
        return v
    return SEVERITY_SYNONYMS.get(v)
