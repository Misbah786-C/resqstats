"""Phase 4 tests - no API key needed: parsing + normalization logic only."""
from enrichment.llm_classify import parse_response
from enrichment.prompts import (
    INCIDENT_TYPES,
    SEVERITIES,
    SYSTEM_PROMPT,
    normalize_severity,
    normalize_type,
)


def test_parse_clean_json():
    t, s = parse_response('{"incident_type": "cardiac", "severity": "critical"}')
    assert (t, s) == ("cardiac", "critical")


def test_parse_with_markdown_fences():
    t, s = parse_response('```json\n{"incident_type": "road_accident", "severity": "minor"}\n```')
    assert (t, s) == ("road_accident", "minor")


def test_parse_garbage_returns_none():
    assert parse_response("sorry, I cannot classify this") == (None, None)
    assert parse_response("") == (None, None)


def test_normalize_type_synonyms():
    assert normalize_type("Heart Attack") == "cardiac"
    assert normalize_type("heatstroke") == "heat_stroke"
    assert normalize_type("Traffic-Accident") == "road_accident"
    assert normalize_type("alien invasion") is None


def test_normalize_severity_synonyms():
    assert normalize_severity("Severe") == "critical"
    assert normalize_severity("URGENT") == "serious"
    assert normalize_severity("chill") is None


def test_prompt_contains_all_labels():
    for label in INCIDENT_TYPES + SEVERITIES:
        assert label in SYSTEM_PROMPT, f"'{label}' missing from system prompt"
