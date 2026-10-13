# Project Contract

Legacy reference for the early seconds-based storyboard.json builder only. New themes use [single-shot-contract.md](single-shot-contract.md) and production.json. Do not apply this file's old hard-duration or one-use-per-visual-family rules to the current independent-shot workflow; do not silently convert an existing project.

## Directory layout

```text
project/
├── brief.md
├── source-ledger.json
├── story-architecture.json
├── hook-ledger.json
├── script-tagged.md
├── script.md
├── narration.txt
├── storyboard.json
├── visual-map.json
├── asset-ledger.json
├── keyframe-prompts.md
├── video-prompts.md
├── assets/
│   ├── images/
│   ├── audio/
│   └── clips/
├── subtitles/
├── outputs/
└── qc-report.md
```

## Source ledger

`source-ledger.json`:

```json
{
  "topic": "",
  "checked_at": "YYYY-MM-DD",
  "sources": [
    {
      "id": "S01",
      "type": "primary|scholarship|museum|reference",
      "title": "",
      "author_or_institution": "",
      "date": "",
      "url_or_locator": "",
      "license_or_access": "",
      "notes": ""
    }
  ],
  "claims": [
    {
      "id": "C001",
      "text": "",
      "class": "F|Q|I|D",
      "source_ids": ["S01"],
      "confidence": "high|medium|low",
      "dispute": "",
      "script_section": ""
    }
  ]
}
```

Direct quotations require an exact locator. A URL alone is insufficient when page, chapter, or section information is available.

## Story architecture

`story-architecture.json` needs:

- `primary_route`, `secondary_route`;
- `central_paradox`, `central_question`, `answer_or_uncertainty`;
- `characters` with goal, resources, constraints, decisions, cost;
- `causal_chain` with source-backed edges;
- `chapters` with time and character budgets;
- `decisive_evidence_or_choice`;
- `derived_thesis` and supporting chain.

## Hook ledger

Every hook in `hook-ledger.json` needs:

```json
{
  "id": "H01",
  "level": "macro|chapter|micro",
  "opened_at_seconds": 0,
  "viewer_question": "",
  "promised_evidence": "",
  "escalation_at_seconds": [],
  "resolved_at_seconds": 0,
  "resolution": "",
  "unresolved_reason": ""
}
```

## Storyboard

`storyboard.json` is the build manifest:

```json
{
  "title": "",
  "target_duration_seconds": 1500,
  "resolution": {"width": 1080, "height": 1920, "fps": 30},
  "narration": "assets/audio/narration.aiff",
  "subtitles": "subtitles/narration.srt",
  "music": "",
  "scenes": [
    {
      "id": "SC001",
      "chapter": "",
      "image": "assets/images/scene-01.png",
      "start_seconds": 0,
      "end_seconds": 12,
      "duration_seconds": 12,
      "motion": "zoom_in|zoom_out|pan_left|pan_right|static",
      "purpose": "",
      "narration_summary": "Actual spoken words covered by this scene",
      "visual_goal": "What the viewer must understand during this exact spoken span",
      "visual_mode": "document|person|place|route|number|quote|compare|network|process|evidence|decision|timeline|cause_chain|reconstruction",
      "visual_anchor": "document|person|place|object|map|number|diagram",
      "visual_family": "one stable family name for duplicate-subject detection",
      "match_level": "ORIGINAL_EXACT|A_EXACT_PLACE|A_ASSOCIATED|B_CONTEXT|B_LATER_IMAGE|NATIVE_EXACT",
      "match_reason": "Why this exact visual supports this exact spoken clause",
      "trigger_terms": ["phrase that must appear in narration_summary"],
      "source_note": "Required disclosure for contextual artifacts or later portraits",
      "subtitle_cues": [1, 2, 3],
      "rights_id": "A001"
    }
  ]
}
```

For a diagnostic draft only, the builder may cycle scenes when the caller explicitly passes the diagnostic cycling option. A reviewed pilot or publication build must never cycle scenes: it uses exact scene timing, assigns each subtitle cue exactly once, and preserves full narration coverage without gaps. `narration_summary` must contain the actual spoken span, not only a chapter label.

Each non-empty image/video path and each external `visual_family` may occur only once in a reviewed build. An image scene must contain a `match_reason`, and at least one `trigger_terms` value must appear in its `narration_summary`. `B_CONTEXT` and `B_LATER_IMAGE` require a disclosure in `source_note`. A code-native scene may leave `image` and `rights_id` empty but still needs `visual_goal`, `visual_mode`, `match_level=NATIVE_EXACT`, and `match_reason`.

`visual-map.json` is the human-auditable view of the same mapping. Each row records scene ID, narration paragraph or claim, subtitle cue IDs, visual anchor, asset path, and why that asset matches the spoken content.

## Asset ledger

Every image, music track, sound effect, and external clip needs an entry with:

- `id`, `path`, `kind`;
- generated/original/source URL;
- creator/institution;
- license and evidence;
- modifications;
- allowed use status.
- `visual_family`, exact spoken-clause binding, and whether pixel-level visual review passed.

Do not assume “found online” means reusable.

## Completion gates

1. Research gate: central claims sourced and disputes visible.
2. Architecture gate: causal and hook ledgers close.
3. Script gate: duration and spoken-language checks pass.
4. Rights gate: every external asset has usable status.
5. Semantic gate: zero repeated files, zero repeated external visual families, zero phrase-trigger failures, zero missing match reasons/disclosures/source pages.
6. Build gate: video and narration exist, and captions are visible in decoded video frames; a soft subtitle stream alone does not pass.
7. QC gate: duration, 9:16 resolution, streams, sample frames, audio, burned captions, cue coverage, semantic visual mapping, and factual risks recorded.
