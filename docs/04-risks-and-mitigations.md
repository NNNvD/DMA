# Risks, Pitfalls, and Bottlenecks

This document outlines key risks and proposed mitigations.

---

## 1. Rules Hallucination / Misinterpretation

**Risk:**  
The DMA confidently gives incorrect rules, undermining trust.

**Causes:**
- LLM answering from prior training rather than ingested materials.
- Ambiguous or missing rule references.
- Overly aggressive generation without retrieval.

**Mitigations:**
- Always use retrieval for rules queries (RAG).
- Implement a "strict rules mode":
  - If confidence is low or no strong matches, answer:
    - "I’m not sure; here are the likely sections to check."
- Show citations (book, chapter, page) or passage excerpts.
- Include regression tests with known rules questions.

---

## 2. Context Overload & Loss

**Risk:**  
Large rulebooks + campaign + logs exceed context limits; relevant info is dropped, causing inconsistencies.

**Mitigations:**
- Use semantic search instead of feeding entire books each time.
- Maintain:
  - A compact “active session state” context.
  - A long-term knowledge base stored outside the prompt.
- Summarize old sessions and world state updates.
- Design chunking strategy (by section, topic) to support precise retrieval.

---

## 3. Latency Spikes During Live Play

**Risk:**  
The DMA responds too slowly during critical moments.

**Mitigations:**
- Optimize prompts for brevity during Stage 3.
- Preload context for:
  - PC sheets
  - Current scene
  - Relevant rules sections
- Use streaming responses.
- Consider:
  - Using a smaller/faster model for routine live queries.
  - Degrading gracefully (shorter answers, fewer suggestions) when latency is high.

---

## 4. Cost Blow-Ups

**Risk:**  
Unbounded token usage leads to high API costs.

**Mitigations:**
- Implement budget controls:
  - Per-session token caps.
  - Per-request token limits.
- Aggressively summarize logs and world state.
- Cache:
  - Frequently requested rules answers.
  - Session recaps and static summaries.
- Allow the DM to select a “frugal mode” that:
  - Reduces verbosity.
  - Uses smaller models whenever possible.

---

## 5. UX Overload

**Risk:**  
Too many features or options overwhelm the DM; the tool becomes distracting.

**Mitigations:**
- Start with a minimal interface for each stage:
  - 3–5 core actions.
- Hide advanced features behind optional panels or settings.
- Conduct usability tests (or simulated user journeys) and iterate.
- Provide presets for typical DM styles (e.g., “combat-focused”, “narrative-heavy”).

---

## 6. Continuity and Canon Drift

**Risk:**  
The DMA contradicts previous events or established lore.

**Mitigations:**
- Maintain a normalized world state with:
  - Entity IDs
  - Consistent references
- Record significant events as structured updates (not only text logs).
- Provide:
  - “World state diff” after each session for DM review.
- Add tests that:
  - Feed previous events and ask the DMA for recall; verify consistency.

---

## 7. Over-Reliance on DMA

**Risk:**  
DM outsources too much creative responsibility, leading to loss of agency and personality.

**Mitigations:**
- Design responses as options, not directives.
- Encourage DM annotations and overrides.
- Provide tools to:
  - Mark generated content as “canon” only after explicit DM confirmation.

---

## 8. Legal / Licensing Issues

**Risk:**  
Rulebook ingestion and use may violate terms of use.

**Mitigations:**
- Ingest rulebooks on the user’s machine or in their private storage.
- Avoid redistributing proprietary content.
- Explicitly support open systems (e.g., SRDs, open-licensed rulesets).
- Advise users to review and comply with publishers’ licenses.
