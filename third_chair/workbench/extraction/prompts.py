"""Prompts for LLM-based fact extraction."""

TRANSCRIPT_EXTRACTION_SYSTEM = """You are a legal analyst extracting structured facts from body-worn camera transcript segments.

For each segment, extract:
1. **Statements**: Direct quotes or paraphrased claims made by speakers
2. **Events**: Actions or occurrences described (e.g., "Officer arrived at scene")
3. **Entity Mentions**: People, places, objects, or times referenced
4. **Actions**: Physical actions described or performed

Focus on factual content that could be relevant in legal proceedings. Extract specific details like:
- Times and dates mentioned
- Locations or addresses
- Names of people
- Descriptions of events or actions
- Claims about what happened

Respond in JSON format only. Do not include any text outside the JSON."""

TRANSCRIPT_EXTRACTION_USER = """Extract facts from this transcript segment.

Speaker: {speaker}
Speaker Role: {speaker_role}
Timestamp: {start_time:.1f}s - {end_time:.1f}s

Text:
{text}

{translation_section}

Respond with a JSON object containing arrays for each extraction type:
{{
  "statements": [
    {{
      "content": "The exact statement or paraphrase",
      "speaker": "{speaker}",
      "confidence": 0.9
    }}
  ],
  "events": [
    {{
      "content": "Description of the event",
      "confidence": 0.8
    }}
  ],
  "entity_mentions": [
    {{
      "content": "Name or description of entity",
      "entity_type": "person|place|time|object",
      "confidence": 0.9
    }}
  ],
  "actions": [
    {{
      "content": "Description of the action",
      "actor": "{speaker}",
      "confidence": 0.8
    }}
  ]
}}

Only include extractions that are clearly supported by the text. Omit empty arrays."""

INCONSISTENCY_FOCUS_SYSTEM = """You are a legal analyst comparing statements from different sources to identify potential inconsistencies.

Your task is to determine if two statements or facts are:
1. **Inconsistent**: They contradict each other or cannot both be true
2. **Corroborating**: They support each other or describe the same fact
3. **Unrelated**: They discuss different topics or events

When identifying inconsistencies, consider:
- Direct contradictions (e.g., "I was at home" vs "He was at the store")
- Timeline conflicts (events that couldn't happen in the order described)
- Numeric discrepancies (different counts, times, amounts)
- Role/identity conflicts (who did what)

Be precise and explain your reasoning. Only flag genuine inconsistencies, not minor variations in wording.

Respond in JSON format only."""

INCONSISTENCY_ANALYSIS_USER = """Compare these two extractions from different evidence items:

**Extraction A** (from evidence {evidence_a_id}):
Speaker: {speaker_a}
Time: {time_a}
Content: {content_a}

**Extraction B** (from evidence {evidence_b_id}):
Speaker: {speaker_b}
Time: {time_b}
Content: {content_b}

Analyze whether these extractions are inconsistent, corroborating, or unrelated.

Respond with a JSON object:
{{
  "relationship": "inconsistent|corroborating|unrelated",
  "confidence": 0.0-1.0,
  "reasoning": "Detailed explanation of your analysis",
  "severity": "minor|moderate|major|critical",
  "key_discrepancy": "Brief description of the main difference (if inconsistent)"
}}

Only use "inconsistent" if there is a genuine factual conflict, not just different perspectives or additional details."""

TIMELINE_ANALYSIS_SYSTEM = """You are a legal analyst checking the chronological consistency of events described in evidence.

Your task is to identify temporal conflicts - situations where the timeline of events doesn't make sense, such as:
- Events described as happening before they could have occurred
- Overlapping events that couldn't happen simultaneously
- Impossible sequences (e.g., arriving before leaving)

Focus on explicit time references and logical event sequences.

Respond in JSON format only."""

TIMELINE_CONFLICT_USER = """Analyze these events for timeline consistency:

Events (in order of occurrence as claimed):
{events_list}

Check if the chronological order is plausible. Consider:
1. Are there any impossible sequences?
2. Do the time gaps make sense?
3. Are there conflicts between what different sources say about timing?

Respond with a JSON object:
{{
  "has_conflicts": true|false,
  "conflicts": [
    {{
      "event_a_id": "id",
      "event_b_id": "id",
      "description": "What makes this impossible or implausible",
      "severity": "minor|moderate|major|critical"
    }}
  ],
  "reasoning": "Overall assessment of timeline consistency"
}}"""
