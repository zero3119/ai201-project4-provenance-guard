# Provenance Guard Planning

## Project Overview

Provenance Guard is a backend system for a creative writing platform. It accepts submitted text, analyzes whether the writing appears likely AI-generated or likely human-written, returns a confidence score, shows a transparency label, and allows creators to appeal a classification they believe is wrong.

The goal is not to prove authorship perfectly. The goal is to communicate uncertainty clearly, avoid overconfident accusations, and keep an audit trail of attribution decisions.

---

## Detection Signals

### Signal 1: Groq LLM Classifier

**What it measures:**  
This signal asks a Groq LLM to evaluate whether the submitted text appears AI-generated or human-written based on overall style, structure, specificity, and phrasing.

**Why it helps:**  
An LLM can notice broad writing patterns such as generic phrasing, overly polished structure, repetitive explanations, and lack of personal specificity.

**Output:**  
`llm_score`, a float from `0.0` to `1.0`.

- `0.0` = very likely human-written
- `1.0` = very likely AI-generated

**Blind spot:**  
The LLM can be wrong. Formal human writing may be misclassified as AI, and edited AI writing may appear human.

---

### Signal 2: Stylometric Heuristics

**What it measures:**  
This signal uses Python calculations to measure structural patterns in the text, including sentence length variance, vocabulary diversity, punctuation density, and average sentence length.

**Why it helps:**  
AI-generated writing often has smoother and more uniform sentence patterns. Human writing often has more variation, interruptions, informal punctuation, and uneven sentence lengths.

**Output:**  
`style_score`, a float from `0.0` to `1.0`.

- `0.0` = very human-like structure
- `1.0` = very AI-like structure

**Blind spot:**  
Some human writing is naturally polished and consistent, especially academic or professional writing. Some AI writing can also be edited to look more irregular.

---

### Combined Confidence Score

The final score will combine both signals:

```txt
final_score = (0.65 * llm_score) + (0.35 * style_score)
```

The Groq LLM classifier has more weight because it can evaluate the overall meaning and style of the text. The stylometric heuristic score still matters because it is independent and based on measurable writing structure.

---

## Uncertainty Representation

The final confidence score represents how strongly the system believes the submitted text appears AI-generated.

A score of `0.60` means the system leans toward AI-generated, but it is not confident enough to make a strong claim. A score of `0.80` or higher means the system has stronger evidence and can show a high-confidence AI label.

| Final Score | Attribution | Label Type |
|---:|---|---|
| `0.00–0.39` | `likely_human` | High-confidence human label |
| `0.40–0.74` | `uncertain` | Uncertain label |
| `0.75–1.00` | `likely_ai` | High-confidence AI label |

The uncertain range is intentionally wide because false positives are harmful to creators. The system should avoid strongly labeling a human creator's work as AI-generated unless the score is high.

---

## Transparency Label Design

| Label Type | Exact Label Text |
|---|---|
| Likely AI | "This work shows strong signs of AI-generated writing. This label is based on automated analysis and may not be perfect. The creator may appeal this decision." |
| Likely human | "This work appears likely to be human-written based on the available signals. This label is based on automated analysis and should be understood as a confidence estimate, not proof." |
| Uncertain | "This work could not be confidently classified as AI-generated or human-written. The system found mixed signals, so readers should treat the attribution as uncertain." |

---

## Appeals Workflow

A creator can submit an appeal if they believe their content was misclassified.

### Appeal submission

The creator provides:

- `content_id`
- `creator_id`
- `creator_reasoning`

### System behavior when an appeal is received

When an appeal is submitted, the system will:

1. Look up the original decision using `content_id`.
2. Record the creator's appeal reasoning.
3. Change the content status from `classified` to `under_review`.
4. Add the appeal information to the JSON audit log.
5. Return a confirmation response.

### Human reviewer view

A human reviewer would see:

- content ID
- creator ID
- original attribution result
- original confidence score
- individual signal scores
- transparency label shown to readers
- creator appeal reasoning
- current status

---

## Anticipated Edge Cases

### Edge Case 1: Formal human writing

A human-written academic paragraph may look polished, balanced, and generic. The stylometric signal may score it as AI-like because it has consistent sentence lengths and formal vocabulary.

### Edge Case 2: Edited AI writing

A creator might heavily edit AI output by adding personal details, irregular punctuation, and informal phrases. This may lower both signal scores even though AI was involved.

### Edge Case 3: Poetry or experimental writing

Poetry may use repetition, short lines, unusual punctuation, or simple vocabulary. The heuristic signal may misread this structure as AI-like.

### Edge Case 4: Non-native English writing

A non-native English speaker may write in a careful or formal style that looks unusual to the system. The system should avoid overconfident AI labels in these cases.

---

## API Surface

### `POST /submit`

Accepts:

```json
{
  "text": "The submitted writing goes here.",
  "creator_id": "creator-123"
}
```

Returns:

```json
{
  "content_id": "unique-id",
  "creator_id": "creator-123",
  "attribution": "likely_ai | likely_human | uncertain",
  "confidence": 0.82,
  "label": "Reader-facing transparency label text",
  "signals": {
    "llm_score": 0.87,
    "style_score": 0.73
  },
  "status": "classified"
}
```

### `POST /appeal`

Accepts:

```json
{
  "content_id": "unique-id",
  "creator_id": "creator-123",
  "creator_reasoning": "I wrote this myself and can explain my writing process."
}
```

Returns:

```json
{
  "content_id": "unique-id",
  "status": "under_review",
  "message": "Appeal received and marked for human review."
}
```

### `GET /log`

Returns recent audit log entries, including submission decisions and appeal records.

---

## Architecture

### Submission Flow

```txt
Client / Creative Platform
        |
        | POST /submit
        | raw text + creator_id
        v
Flask API
        |
        | sends text to Signal 1
        v
Groq LLM Classifier
        |
        | returns llm_score
        v
Flask API
        |
        | sends text to Signal 2
        v
Stylometric Heuristics
        |
        | returns style_score
        v
Confidence Scoring
        |
        | combines llm_score + style_score
        v
Transparency Label Generator
        |
        | creates label text
        v
JSON Audit Log
        |
        | stores decision
        v
JSON Response to Client
```

### Appeal Flow

```txt
Client / Creator
        |
        | POST /appeal
        | content_id + creator_id + creator_reasoning
        v
Flask API
        |
        | finds original decision
        v
JSON Audit Log
        |
        | updates status to under_review
        | stores appeal reasoning
        v
JSON Confirmation Response
```

### Architecture Narrative

A submitted piece of text enters the system through `POST /submit`. The Flask API sends the text through two independent detection signals, combines the scores into one final confidence score, maps that score to a transparency label, stores the result in the JSON audit log, and returns a structured response.

If a creator disagrees with the result, they can submit an appeal through `POST /appeal`. The system records their reasoning, updates the content status to `under_review`, logs the appeal, and returns a confirmation response.

---

## AI Tool Plan

### M3: Submission Endpoint + First Signal

**Spec sections to provide to the AI tool:**

- Project Overview
- Detection Signals: Signal 1
- API Surface: `POST /submit`
- Architecture

**Ask the AI tool to generate:**

- Flask app skeleton
- `POST /submit` route
- Groq LLM classifier function
- basic JSON audit log entry for submissions

**Verification plan:**

- Run the Flask app locally.
- Send a test request to `POST /submit`.
- Confirm the response includes `content_id`, `creator_id`, `attribution`, `confidence`, `label`, `signals`, and `status`.
- Confirm the audit log stores the submission.

---

### M4: Second Signal + Confidence Scoring

**Spec sections to provide to the AI tool:**

- Detection Signals
- Uncertainty Representation
- API Surface
- Architecture

**Ask the AI tool to generate:**

- stylometric heuristic function
- score combination function
- updated `/submit` response with both signal scores

**Verification plan:**

Test at least four inputs:

- clearly AI-generated text
- clearly human-written text
- formal human writing
- lightly edited AI-style text

Check that:

- scores vary meaningfully between test cases
- `llm_score`, `style_score`, and `final_score` appear in the response
- individual signal scores appear in the audit log
- different score ranges produce different labels

---

### M5: Production Layer

**Spec sections to provide to the AI tool:**

- Transparency Label Design
- Appeals Workflow
- API Surface
- Architecture

**Ask the AI tool to generate:**

- label generation logic
- `POST /appeal` endpoint
- `GET /log` endpoint
- rate limiting for `POST /submit`

**Verification plan:**

- Confirm all label variants are reachable.
- Submit an appeal and confirm the status becomes `under_review`.
- Confirm appeal reasoning is saved in the audit log.
- Test rate limiting and confirm the API returns a `429` response after too many requests.
- Confirm `GET /log` shows at least 3 structured entries.

---

## Stretch Feature Note

Before starting any stretch feature, this planning file will be updated with the design, expected behavior, and verification plan for that feature.
