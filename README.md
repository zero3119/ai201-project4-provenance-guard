# Provenance Guard

Provenance Guard is a Flask backend system for a creative writing platform. It accepts submitted text, analyzes whether the writing appears likely AI-generated or likely human-written, returns a confidence score, displays a transparency label, and gives creators a way to appeal if they believe the classification is wrong.

The goal of this project is not to prove authorship perfectly. The goal is to communicate uncertainty clearly, avoid overconfident accusations, and keep a structured audit trail of attribution decisions.

---

## Project Features

- `POST /submit` endpoint for text submissions
- Two-signal detection pipeline:
  - Groq LLM classifier
  - Stylometric heuristic analyzer
- Combined confidence score from `0.0` to `1.0`
- Three reader-facing transparency label variants
- JSON audit log for submissions and appeals
- `POST /appeal` endpoint for creator disputes
- `GET /log` endpoint for reviewing recent structured log entries
- Rate limiting on `/submit`

---

## Architecture

```txt
Submission Flow:

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
        | returns llm_score from 0.0 to 1.0
        v
Flask API
        |
        | sends text to Signal 2
        v
Stylometric Heuristics
        |
        | returns style_score from 0.0 to 1.0
        v
Confidence Scoring
        |
        | combines scores into final confidence
        v
Transparency Label Generator
        |
        | creates reader-facing label text
        v
Audit Log
        |
        | stores content_id, creator_id, scores, label, status
        v
JSON Response to Client


Appeal Flow:

Client / Creator
        |
        | POST /appeal
        | content_id + creator_reasoning
        v
Flask API
        |
        | finds original submission
        | updates content status
        v
Audit Log
        |
        | stores appeal reasoning and status = under_review
        v
JSON Confirmation Response
```

A submitted text enters through `POST /submit`. The API sends the text to two independent detection signals, combines their scores into one confidence score, maps that score to a transparency label, writes a structured audit-log entry, and returns a JSON response.

If a creator disagrees with the classification, they can submit an appeal through `POST /appeal`. The system finds the original `content_id`, records the creator's reasoning, updates the submission status to `under_review`, and adds an appeal event to the audit log.

---

## API Surface

### `POST /submit`

Accepts a JSON body:

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
    "llm_reason": "Short model explanation.",
    "style_score": 0.73,
    "style_metrics": {
      "sentence_count": 4,
      "word_count": 82,
      "average_sentence_length": 20.5,
      "sentence_length_variance": 6.25,
      "type_token_ratio": 0.78,
      "uniformity_score": 0.92,
      "length_score": 0.69,
      "low_diversity_score": 0.48,
      "formality_marker_score": 0.25,
      "regular_punctuation_score": 1.0,
      "informality_penalty": 0.0
    }
  },
  "status": "classified"
}
```

### `POST /appeal`

Accepts a JSON body:

```json
{
  "content_id": "unique-id",
  "creator_reasoning": "I wrote this myself and can explain my process."
}
```

Returns:

```json
{
  "content_id": "unique-id",
  "status": "under_review",
  "message": "Appeal received and marked for human review.",
  "appeal_reasoning": "I wrote this myself and can explain my process.",
  "updated_submission": {
    "event_type": "submission",
    "content_id": "unique-id",
    "status": "under_review",
    "appeal_filed": true
  }
}
```

### `GET /log`

Returns recent structured audit-log entries.

---

## Detection Signal 1: Groq LLM Classifier

The first signal uses Groq with `llama-3.3-70b-versatile` to estimate whether the submitted writing appears AI-generated or human-written.

This signal captures overall semantic and stylistic patterns. It can notice writing that sounds generic, overly balanced, polished, formulaic, or lacking personal specificity. Its output is an `llm_score` from `0.0` to `1.0`:

- `0.0` = very likely human-written
- `1.0` = very likely AI-generated

I chose this signal because an LLM can evaluate the overall feel and structure of a paragraph better than a simple formula. However, it has important blind spots. Formal human writing may be misclassified as AI, and edited AI writing may appear more human. Because of this, the Groq score is not treated as proof by itself.

---

## Detection Signal 2: Stylometric Heuristics

The second signal uses pure Python statistics to measure writing structure. It calculates metrics such as:

- sentence count
- word count
- average sentence length
- sentence length variance
- type-token ratio / vocabulary diversity
- formal phrase markers
- informal writing markers
- expressive punctuation

This signal returns a `style_score` from `0.0` to `1.0`:

- `0.0` = very human-like structure
- `1.0` = very AI-like structure

I chose this signal because it is independent from the LLM. Instead of asking another model for an opinion, it measures visible structural patterns. AI-generated text often has smoother, more uniform sentence structure and polished phrasing, while casual human writing often has more variation, interruptions, punctuation, and informal wording.

This signal also has blind spots. Academic writing, professional writing, or non-native English writing may be polished and uniform even when written by a human. Poetry may use repetition or unusual punctuation that simple statistics can misunderstand.

---

## Confidence Scoring

Both detection signals produce a score from `0.0` to `1.0`. The system combines them using this weighted formula:

```txt
final_score = (0.65 * llm_score) + (0.35 * style_score)
```

The Groq score receives more weight because it can evaluate meaning, tone, and overall style. The stylometric score still matters because it provides an independent structural check.

The final score is mapped to three categories:

| Final Score | Attribution | Label Variant |
|---:|---|---|
| `0.00–0.39` | `likely_human` | High-confidence human |
| `0.40–0.74` | `uncertain` | Uncertain |
| `0.75–1.00` | `likely_ai` | High-confidence AI |

I chose a wide uncertain range because false positives are harmful on a creative platform. A score around `0.60` may mean the writing has some AI-like signs, but the system should not strongly label it as AI-generated. A score of `0.75` or higher is where the system has enough evidence to use the high-confidence AI label.

### Example Confidence Results

These examples show that the scoring system can produce meaningfully different results for different types of writing.

#### High-confidence AI-style example

Input:

```txt
Artificial intelligence represents a transformative paradigm shift in the modern digital landscape, offering unprecedented opportunities to enhance efficiency, optimize decision-making, and drive innovation across diverse sectors while also requiring careful consideration of ethical implications and responsible implementation.
```

Actual result:

```json
{
  "attribution": "likely_ai",
  "confidence": 0.818,
  "content_id": "66dcd55d-dd39-42fb-8b5e-5b48d6ed86ad",
  "creator_id": "test-user-ai",
  "label": "This work shows strong signs of AI-generated writing. This label is based on automated analysis and may not be perfect. The creator may appeal this decision.",
  "signals": {
    "llm_reason": "The text features overly formal and generic language patterns commonly found in AI-generated content.",
    "llm_score": 0.8,
    "style_score": 0.85,
    "style_metrics": {
      "average_sentence_length": 38.0,
      "formality_marker_score": 1.0,
      "informality_penalty": 0.0,
      "length_score": 1.0,
      "low_diversity_score": 0.0,
      "regular_punctuation_score": 1.0,
      "sentence_count": 1,
      "sentence_length_variance": 0,
      "type_token_ratio": 0.974,
      "uniformity_score": 1.0,
      "word_count": 38
    }
  },
  "status": "classified"
}
```

This example scores higher because it uses polished, generic, broad wording such as “transformative paradigm shift,” “optimize decision-making,” and “ethical implications.”

#### Lower-confidence human-style example

Input:

```txt
ok so I went to the bar with Jenny because she owed me a drink. I thought that we were going to a random bar so I went looking kind of mid, turns out is one of those bouge places and I ended up looking like a hobo while she was in a dress and shit
```

Actual result:

```json
{
  "attribution": "likely_human",
  "confidence": 0.214,
  "content_id": "a3526cc7-1af2-4eba-acea-fc3227298e0a",
  "creator_id": "test-user-ai",
  "label": "This work appears likely to be human-written based on the available signals. This label is based on automated analysis and should be understood as a confidence estimate, not proof.",
  "signals": {
    "llm_reason": "The writing has an informal tone and colloquial language, which is more typical of human expression.",
    "llm_score": 0.2,
    "style_score": 0.24,
    "style_metrics": {
      "average_sentence_length": 28.0,
      "formality_marker_score": 0.0,
      "informality_penalty": 0.8,
      "length_score": 1.0,
      "low_diversity_score": 0.6,
      "regular_punctuation_score": 1.0,
      "sentence_count": 2,
      "sentence_length_variance": 169,
      "type_token_ratio": 0.75,
      "uniformity_score": 0.0,
      "word_count": 56
    }
  },
  "status": "classified"
}
```

This example scores lower because it contains personal detail, informal phrasing, expressive punctuation, uneven structure, and casual wording.

#### Uncertain example

Input:

```txt
The relationship between monetary policy and asset price inflation has been extensively studied in the literature. Central banks face a fundamental tension between their mandate for price stability and the unintended consequences of prolonged low interest rates on equity and real estate valuations.
```

Actual result:

```json
{
  "attribution": "uncertain",
  "confidence": 0.428,
  "content_id": "e4d0a403-1c77-456e-8f94-77cf51b2467b",
  "creator_id": "test-user-borderline",
  "label": "This work could not be confidently classified as AI-generated or human-written. The system found mixed signals, so readers should treat the attribution as uncertain.",
  "signals": {
    "llm_reason": "The text is well-structured but lacks personal touch and uses overly formal language.",
    "llm_score": 0.4,
    "style_score": 0.479,
    "style_metrics": {
      "average_sentence_length": 21.5,
      "formality_marker_score": 0.0,
      "informality_penalty": 0.0,
      "length_score": 0.75,
      "low_diversity_score": 0.158,
      "regular_punctuation_score": 1.0,
      "sentence_count": 2,
      "sentence_length_variance": 30.25,
      "type_token_ratio": 0.86,
      "uniformity_score": 0.622,
      "word_count": 43
    }
  },
  "status": "classified"
}
```

Scores may vary slightly between runs because the Groq model can return slightly different judgments. The important point is that the examples produce noticeably different confidence ranges.

---

## Transparency Label Variants

The system returns one of three exact transparency labels.

| Label Variant | Score Range | Exact Label Text |
|---|---:|---|
| High-confidence AI | `0.75–1.00` | "This work shows strong signs of AI-generated writing. This label is based on automated analysis and may not be perfect. The creator may appeal this decision." |
| High-confidence human | `0.00–0.39` | "This work appears likely to be human-written based on the available signals. This label is based on automated analysis and should be understood as a confidence estimate, not proof." |
| Uncertain | `0.40–0.74` | "This work could not be confidently classified as AI-generated or human-written. The system found mixed signals, so readers should treat the attribution as uncertain." |

These labels are intentionally cautious. Even the high-confidence labels say the result is based on automated analysis, not proof.

---

## Appeals Workflow

A creator can submit an appeal if they believe their content was misclassified. The appeal request must include:

- `content_id`
- `creator_reasoning`

When an appeal is received, the system:

1. Looks up the original submission using `content_id`.
2. Updates the original submission status from `classified` to `under_review`.
3. Stores the creator's appeal reasoning.
4. Adds a separate appeal event to the audit log.
5. Returns a confirmation response.

A human reviewer would see:

- content ID
- creator ID
- original attribution
- original confidence score
- Groq LLM score
- stylometric score
- creator appeal reasoning
- current status

Automated reclassification is not included. The purpose of the appeal workflow is to create a clear path for human review.

### Appeal example

Creator reasoning:

```txt
I wrote this myself from personal experience. I am a non-native English speaker and my writing style may appear more formal than typical.
```

Actual response:

```json
{
  "appeal_reasoning": "I wrote this myself from personal experience. I am a non-native English speaker and my writing style may appear more formal than typical.",
  "content_id": "66dcd55d-dd39-42fb-8b5e-5b48d6ed86ad",
  "message": "Appeal received and marked for human review.",
  "status": "under_review",
  "updated_submission": {
    "appeal_filed": true,
    "appeal_reasoning": "I wrote this myself from personal experience. I am a non-native English speaker and my writing style may appear more formal than typical.",
    "appeal_timestamp": "2026-07-01T06:07:43.176980+00:00",
    "attribution": "likely_ai",
    "confidence": 0.818,
    "content_id": "66dcd55d-dd39-42fb-8b5e-5b48d6ed86ad",
    "creator_id": "test-user-ai",
    "event_type": "submission",
    "label": "This work shows strong signs of AI-generated writing. This label is based on automated analysis and may not be perfect. The creator may appeal this decision.",
    "llm_reason": "The text features overly formal and generic language patterns commonly found in AI-generated content.",
    "llm_score": 0.8,
    "status": "under_review",
    "style_score": 0.85,
    "style_metrics": {
      "average_sentence_length": 38.0,
      "formality_marker_score": 1.0,
      "informality_penalty": 0.0,
      "length_score": 1.0,
      "low_diversity_score": 0.0,
      "regular_punctuation_score": 1.0,
      "sentence_count": 1,
      "sentence_length_variance": 0,
      "type_token_ratio": 0.974,
      "uniformity_score": 1.0,
      "word_count": 38
    },
    "timestamp": "2026-07-01T05:59:06.866529+00:00"
  }
}
```

---

## Rate Limiting

The `/submit` endpoint uses Flask-Limiter with this limit:

```txt
10 per minute; 100 per day
```

I chose this limit because a normal creator is unlikely to submit more than 10 pieces of writing in one minute. The per-minute limit helps prevent a script from flooding the endpoint. The daily limit of 100 still gives enough room for testing or for a creator who submits multiple pieces of work in a day.

For local development, the limiter uses in-memory storage:

```python
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[],
    storage_uri="memory://",
)
```

### Rate Limit Test Evidence

PowerShell test command:

```powershell
.\test_rate_limit.ps1
```

Actual status-code output from my test:

```txt
200
200
200
200
200
200
200
200
200
200
429
429
```

The `429` responses show that the API starts rejecting requests after the 10-per-minute limit is exceeded.

---

## Audit Log

The system stores audit-log entries in `audit_log.json`. Each submission entry includes:

- timestamp
- content ID
- creator ID
- attribution result
- final confidence score
- transparency label
- Groq LLM score
- Groq reason
- stylometric score
- stylometric metrics
- status
- whether an appeal has been filed

Each appeal entry includes:

- timestamp
- content ID
- creator ID
- creator reasoning
- original attribution
- original confidence
- original signal scores
- status set to `under_review`

### Audit Log Evidence

Actual `GET /log` output excerpt:

```json
{
  "entries": [
    {
      "appeal_filed": false,
      "attribution": "uncertain",
      "confidence": 0.428,
      "content_id": "069bc9e0-249a-45b8-b9a5-17240a0cb962",
      "creator_id": "m5-test-user",
      "event_type": "submission",
      "label": "This work could not be confidently classified as AI-generated or human-written. The system found mixed signals, so readers should treat the attribution as uncertain.",
      "llm_reason": "The text is well-structured but lacks personal touch and uses overly formal language.",
      "llm_score": 0.4,
      "status": "classified",
      "style_score": 0.479,
      "style_metrics": {
        "average_sentence_length": 21.5,
        "formality_marker_score": 0.0,
        "informality_penalty": 0.0,
        "length_score": 0.75,
        "low_diversity_score": 0.158,
        "regular_punctuation_score": 1.0,
        "sentence_count": 2,
        "sentence_length_variance": 30.25,
        "type_token_ratio": 0.86,
        "uniformity_score": 0.622,
        "word_count": 43
      },
      "timestamp": "2026-06-30T01:54:21.624513+00:00"
    },
    {
      "content_id": "43ddeb4f-457b-45bd-b768-0cac59406bc2",
      "creator_id": "m5-test-user",
      "creator_reasoning": "I wrote this myself from personal experience. I am a non-native English speaker and my writing style may appear more formal than typical.",
      "event_type": "appeal",
      "llm_score": 0.7,
      "original_attribution": "uncertain",
      "original_confidence": 0.661,
      "status": "under_review",
      "style_score": 0.588,
      "timestamp": "2026-06-30T01:54:24.312652+00:00"
    },
    {
      "appeal_filed": false,
      "attribution": "likely_human",
      "confidence": 0.152,
      "content_id": "12cdd6c6-3b9e-40e9-a64a-6b1b4e2a1d76",
      "creator_id": "ratelimit-test",
      "event_type": "submission",
      "label": "This work appears likely to be human-written based on the available signals. This label is based on automated analysis and should be understood as a confidence estimate, not proof.",
      "llm_reason": "it has a straightforward and simple structure typical of human communication",
      "llm_score": 0.0,
      "status": "classified",
      "style_score": 0.433,
      "style_metrics": {
        "average_sentence_length": 11.0,
        "formality_marker_score": 0.0,
        "informality_penalty": 0.0,
        "length_score": 0.167,
        "low_diversity_score": 0.0,
        "regular_punctuation_score": 1.0,
        "sentence_count": 1,
        "sentence_length_variance": 0,
        "type_token_ratio": 1.0,
        "uniformity_score": 1.0,
        "word_count": 11
      },
      "timestamp": "2026-06-30T01:57:34.809244+00:00"
    },
    {
      "appeal_filed": false,
      "attribution": "likely_human",
      "confidence": 0.152,
      "content_id": "7bf647f4-eff3-4a71-8ef0-7c9038647f9e",
      "creator_id": "ratelimit-test",
      "event_type": "submission",
      "label": "This work appears likely to be human-written based on the available signals. This label is based on automated analysis and should be understood as a confidence estimate, not proof.",
      "llm_reason": "it has a straightforward and simple structure typical of human communication",
      "llm_score": 0.0,
      "status": "classified",
      "style_score": 0.433,
      "style_metrics": {
        "average_sentence_length": 11.0,
        "formality_marker_score": 0.0,
        "informality_penalty": 0.0,
        "length_score": 0.167,
        "low_diversity_score": 0.0,
        "regular_punctuation_score": 1.0,
        "sentence_count": 1,
        "sentence_length_variance": 0,
        "type_token_ratio": 1.0,
        "uniformity_score": 1.0,
        "word_count": 11
      },
      "timestamp": "2026-06-30T01:57:35.475131+00:00"
    }
  ]
}
```

---

## Known Limitations

This system would likely struggle with formal human writing. For example, an academic paragraph written by a human may have long sentences, careful structure, formal vocabulary, and low emotional variation. The stylometric signal may score that as AI-like because it measures polish and uniformity, not authorship.

The system may also struggle with poetry or experimental writing. A poem may use repetition, short lines, unusual punctuation, or simple vocabulary on purpose. The heuristic signal may misread those patterns because it does not understand artistic intent.

Finally, the Groq LLM classifier is still only an estimate. It can identify patterns that look AI-like, but it cannot prove how a text was created. Because of this, the system uses cautious labels, a wide uncertain range, and an appeal workflow.

---

## Spec Reflection

The planning spec helped guide the implementation by defining the output shape before coding. For example, the spec said both signals should return scores from `0.0` to `1.0`, which made the confidence-scoring function easier to implement and test.

One way the implementation diverged from the original spec was the high-confidence AI threshold. I originally planned to use `0.80` as the cutoff, but I changed it to `0.75` after testing because some clearly AI-style examples were scoring strongly but landing slightly below `0.80`. I kept the uncertain range wide enough to remain cautious while making the high-confidence AI label reachable during realistic tests.

Another implementation detail that changed was the Groq JSON parsing. I originally tried using strict JSON response formatting, but Groq returned malformed JSON in one test case. I changed the implementation so the prompt still requests JSON, but the Python code parses the response defensively and falls back to an uncertain score if parsing fails.

---

## AI Usage

I used AI assistance to help plan and implement the project, but I reviewed and revised the output instead of pasting it blindly.

### Instance 1: Flask endpoint and Groq signal

I directed the AI tool to generate a Flask app skeleton with `POST /submit`, a Groq classifier function, and JSON audit logging. The tool produced the initial route and signal function. I reviewed the output to make sure the endpoint accepted `text` and `creator_id`, returned `content_id`, and saved structured log entries.

### Instance 2: Debugging Groq JSON output

During testing, the Groq API failed because the model returned malformed JSON. I used AI assistance to understand the traceback and identify that strict JSON mode was causing the request to fail. I revised the implementation by removing strict `response_format` handling and adding safer Python-side parsing.

---

## How to Run the Project

Create and activate a virtual environment:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
pip install -r requirements.txt
```

Create a `.env` file in the project root:

```txt
GROQ_API_KEY=your_key_here
```

Run the Flask app:

```powershell
python app.py
```

Test `/submit`:

```powershell
$body = @{
  text = "Artificial intelligence represents a transformative paradigm shift in the modern digital landscape, offering unprecedented opportunities to enhance efficiency, optimize decision-making, and drive innovation across diverse sectors while also requiring careful consideration of ethical implications and responsible implementation."
  creator_id = "test-user-1"
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:5000/submit" -Method POST -ContentType "application/json" -Body $body
```

Test `/log`:

```powershell
Invoke-RestMethod -Uri "http://localhost:5000/log" -Method GET
```

Test `/appeal` using a real `content_id` from a previous `/submit` response:

```powershell
$appeal = @{
  content_id = "PASTE-CONTENT-ID-HERE"
  creator_reasoning = "I wrote this myself from personal experience. I am a non-native English speaker and my writing style may appear more formal than typical."
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:5000/appeal" -Method POST -ContentType "application/json" -Body $appeal
```

---

## Portfolio Walkthrough Summary Video

https://youtu.be/hMa50pJ71Qw


