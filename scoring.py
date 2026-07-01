def clamp_score(value):
    """Keep a numeric score between 0.0 and 1.0."""
    try:
        value = float(value)
    except (TypeError, ValueError):
        value = 0.5
    return round(max(0.0, min(1.0, value)), 3)


def combine_signal_scores(llm_score, style_score):
    """
    Combine both detection signals according to planning.md.

    final_score = (0.65 * llm_score) + (0.35 * style_score)
    """
    llm_score = clamp_score(llm_score)
    style_score = clamp_score(style_score)
    final_score = (0.65 * llm_score) + (0.35 * style_score)
    return clamp_score(final_score)


def map_score_to_attribution(confidence):
    """
    Map the combined confidence score to exactly three categories.

    0.00 - 0.39 = likely_human
    0.40 - 0.74 = uncertain
    0.75 - 1.00 = likely_ai
    """
    confidence = clamp_score(confidence)

    if confidence >= 0.75:
        return "likely_ai"

    if confidence <= 0.39:
        return "likely_human"

    return "uncertain"
