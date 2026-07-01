import json
import os
import re
from statistics import pvariance

from dotenv import load_dotenv
from groq import Groq

load_dotenv()


def _clamp_score(value):
    """Keep a numeric score between 0.0 and 1.0."""
    try:
        value = float(value)
    except (TypeError, ValueError):
        value = 0.5
    return round(max(0.0, min(1.0, value)), 3)


def _parse_groq_response(raw_content):
    """
    Parse the Groq response safely.

    The model is asked for JSON, but LLMs can still sometimes include markdown
    fences or extra text. This helper keeps the Flask route from crashing.
    """
    raw_content = raw_content.strip()

    # Remove common markdown fences if the model adds them.
    raw_content = raw_content.replace("```json", "").replace("```", "").strip()

    try:
        return json.loads(raw_content)
    except json.JSONDecodeError:
        pass

    # Try to extract the first JSON-looking object from the response.
    match = re.search(r"\{.*\}", raw_content, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    # Last fallback: look for a numeric score in the text.
    score_match = re.search(r"llm_score\s*[:=]\s*([01](?:\.\d+)?)", raw_content)
    if score_match:
        return {
            "llm_score": float(score_match.group(1)),
            "reason": "The score was extracted from a non-JSON model response."
        }

    return {
        "llm_score": 0.5,
        "reason": "The model response could not be parsed, so the score was set to uncertain."
    }


def classify_with_groq(text):
    """
    Signal 1: Groq LLM classifier.

    Returns:
        {
            "llm_score": float from 0.0 to 1.0,
            "llm_reason": short explanation from the model
        }

    0.0 = very likely human-written
    1.0 = very likely AI-generated
    """
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY is missing. Create a .env file with GROQ_API_KEY=your_key_here."
        )

    client = Groq(api_key=api_key)

    system_prompt = """
You are a careful writing attribution assistant. Your job is not to prove whether text is AI-generated.
Your job is to estimate whether a piece of writing shows signs of AI generation while being cautious about false positives.

Return exactly one JSON object and nothing else.
Do not use markdown.
Do not include code fences.
Do not add extra braces.

The JSON object must use this shape:
{"llm_score": 0.0, "reason": "short reason"}

llm_score must be a number from 0.0 to 1.0.
0.0 means very likely human-written.
1.0 means very likely AI-generated.
The reason must be one short sentence.
""".strip()

    user_prompt = f"""
Analyze this submitted writing and return only the JSON object:

{text}
""".strip()

    # Do NOT use response_format here. Groq JSON mode can fail the whole request
    # if the model output has even a tiny JSON formatting mistake. Instead, we
    # request JSON in the prompt and parse it safely ourselves.
    completion = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0,
        max_tokens=150,
    )

    raw_content = completion.choices[0].message.content.strip()
    parsed = _parse_groq_response(raw_content)

    return {
        "llm_score": _clamp_score(parsed.get("llm_score", 0.5)),
        "llm_reason": parsed.get("reason", "No reason provided.")
    }


def analyze_stylometry(text):
    """
    Signal 2: Stylometric heuristics.

    This uses simple measurable writing patterns instead of an LLM.
    It returns a score from 0.0 to 1.0.

    0.0 = very human-like structure
    1.0 = very AI-like structure
    """
    sentences = [s.strip() for s in re.split(r"[.!?]+", text) if s.strip()]
    words = re.findall(r"[A-Za-z']+", text.lower())

    if not words:
        return {
            "style_score": 0.5,
            "metrics": {
                "sentence_count": 0,
                "word_count": 0,
                "average_sentence_length": 0,
                "sentence_length_variance": 0,
                "type_token_ratio": 0,
                "informality_penalty": 0,
                "formality_marker_score": 0
            }
        }

    sentence_lengths = []
    for sentence in sentences:
        sentence_words = re.findall(r"[A-Za-z']+", sentence.lower())
        if sentence_words:
            sentence_lengths.append(len(sentence_words))

    if not sentence_lengths:
        sentence_lengths = [len(words)]

    word_count = len(words)
    sentence_count = len(sentence_lengths)
    average_sentence_length = sum(sentence_lengths) / sentence_count
    sentence_length_variance = pvariance(sentence_lengths) if sentence_count > 1 else 0
    type_token_ratio = len(set(words)) / word_count

    lower_text = text.lower()

    # More uniform sentence lengths can look more AI-like.
    uniformity_score = _clamp_score(1 - (sentence_length_variance / 80))

    # Longer, polished sentences can push the score upward, but this is only one factor.
    length_score = _clamp_score((average_sentence_length - 8) / 18)

    # Lower vocabulary diversity can suggest more formulaic writing.
    low_diversity_score = _clamp_score((0.90 - type_token_ratio) / 0.25)

    # Formal/generic phrases often appear in AI-written explanations.
    formality_markers = [
        "it is important",
        "it is essential",
        "essential to",
        "furthermore",
        "moreover",
        "in conclusion",
        "stakeholders",
        "various",
        "responsible deployment",
        "paradigm shift",
        "ethical implications",
        "transformative",
        "numerous",
    ]
    formality_count = sum(lower_text.count(marker) for marker in formality_markers)
    formality_marker_score = _clamp_score((formality_count / word_count) * 30)

    # Casual writing markers reduce the AI-like style score.
    informal_markers = [
        "ok",
        "honestly",
        "way too",
        "won't",
        "don't",
        "can't",
        "i've",
        "i'm",
        "like",
        "drag",
    ]
    informality_count = sum(lower_text.count(marker) for marker in informal_markers)
    informality_penalty = _clamp_score(informality_count / 5)

    expressive_punctuation = len(re.findall(r"[?!]", text)) + len(re.findall(r"\b[A-Z]{2,}\b", text))
    regular_punctuation_score = _clamp_score(1 - (expressive_punctuation / 3))

    style_score = (
        0.25 * uniformity_score
        + 0.20 * length_score
        + 0.15 * low_diversity_score
        + 0.25 * formality_marker_score
        + 0.15 * regular_punctuation_score
        - 0.25 * informality_penalty
    )

    style_score = _clamp_score(style_score)

    return {
        "style_score": style_score,
        "metrics": {
            "sentence_count": sentence_count,
            "word_count": word_count,
            "average_sentence_length": round(average_sentence_length, 3),
            "sentence_length_variance": round(sentence_length_variance, 3),
            "type_token_ratio": round(type_token_ratio, 3),
            "uniformity_score": uniformity_score,
            "length_score": length_score,
            "low_diversity_score": low_diversity_score,
            "formality_marker_score": formality_marker_score,
            "regular_punctuation_score": regular_punctuation_score,
            "informality_penalty": informality_penalty,
        }
    }
