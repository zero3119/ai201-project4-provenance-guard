from scoring import clamp_score

HIGH_CONFIDENCE_AI_LABEL = (
    "This work shows strong signs of AI-generated writing. "
    "This label is based on automated analysis and may not be perfect. "
    "The creator may appeal this decision."
)

HIGH_CONFIDENCE_HUMAN_LABEL = (
    "This work appears likely to be human-written based on the available signals. "
    "This label is based on automated analysis and should be understood as a confidence estimate, not proof."
)

UNCERTAIN_LABEL = (
    "This work could not be confidently classified as AI-generated or human-written. "
    "The system found mixed signals, so readers should treat the attribution as uncertain."
)


def generate_transparency_label(confidence):
    """
    Map the final confidence score to exactly one of the three reader-facing
    label variants defined in planning.md.

    0.00 - 0.39 = high-confidence human
    0.40 - 0.74 = uncertain
    0.75 - 1.00 = high-confidence AI
    """
    confidence = clamp_score(confidence)

    if confidence >= 0.75:
        return HIGH_CONFIDENCE_AI_LABEL

    if confidence <= 0.39:
        return HIGH_CONFIDENCE_HUMAN_LABEL

    return UNCERTAIN_LABEL
