import json
import urllib.request

TEST_INPUTS = [
    {
        "name": "Clearly AI-generated",
        "text": "Artificial intelligence represents a transformative paradigm shift in modern society. It is important to note that while the benefits of AI are numerous, it is equally essential to consider the ethical implications. Furthermore, stakeholders across various sectors must collaborate to ensure responsible deployment."
    },
    {
        "name": "Clearly human-written",
        "text": "ok so i finally tried that new ramen place downtown and honestly? underwhelming. the broth was fine but they put WAY too much sodium in it and i was thirsty for like three hours after. my friend got the spicy version and said it was better. probably won't go back unless someone drags me there"
    },
    {
        "name": "Borderline formal human writing",
        "text": "The relationship between monetary policy and asset price inflation has been extensively studied in the literature. Central banks face a fundamental tension between their mandate for price stability and the unintended consequences of prolonged low interest rates on equity and real estate valuations."
    },
    {
        "name": "Borderline lightly edited AI output",
        "text": "I've been thinking a lot about remote work lately. There are genuine tradeoffs — flexibility and no commute on one side, isolation and blurred work-life boundaries on the other. Studies show productivity varies widely by individual and role type."
    },
]


def submit_text(name, text):
    body = json.dumps({"text": text, "creator_id": "m4-test-user"}).encode("utf-8")
    request = urllib.request.Request(
        "http://localhost:5000/submit",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urllib.request.urlopen(request) as response:
        result = json.loads(response.read().decode("utf-8"))

    print("\n=" * 40)
    print(name)
    print("content_id:", result["content_id"])
    print("attribution:", result["attribution"])
    print("confidence:", result["confidence"])
    print("llm_score:", result["signals"]["llm_score"])
    print("style_score:", result["signals"]["style_score"])
    print("label:", result["label"])


def main():
    for item in TEST_INPUTS:
        submit_text(item["name"], item["text"])


if __name__ == "__main__":
    main()
