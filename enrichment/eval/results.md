# LLM Classifier Evaluation

- Model: `llama-3.1-8b-instant` (Groq free tier), temperature 0
- Sample: 100 incidents (seed 42), ground truth = simulator labels
- **incident_type accuracy: 100.0%**
- **severity accuracy: 32.0%**
- unparseable responses: 0

## Per-type accuracy

- cardiac: 100% (16 calls)
- fall: 100% (11 calls)
- heat_stroke: 100% (9 calls)
- maternity: 100% (7 calls)
- other: 100% (21 calls)
- respiratory: 100% (6 calls)
- road_accident: 100% (25 calls)
- violence: 100% (5 calls)

## Top confusions (truth -> predicted)

- none

_Severity is genuinely ambiguous from text alone (a 'serious' accident and a
'moderate' one can sound identical), so type accuracy is the headline metric._