import json
import urllib.error
import urllib.request

TEST_INPUTS = [
    {
        "name": "Clearly AI-generated",
        "text": "Artificial intelligence represents a transformative paradigm shift in modern society. It is important to note that while the benefits of AI are numerous, it is equally essential to consider the ethical implications. Furthermore, stakeholders across various sectors must collaborate to ensure responsible deployment.",
    },
    {
        "name": "Clearly human-written",
        "text": "ok so i finally tried that new ramen place downtown and honestly? underwhelming. the broth was fine but they put WAY too much salt in it and i was thirsty for like three hours after. my friend got the spicy version and said it was better. probably won't go back unless someone drags me there",
    },
    {
        "name": "Borderline formal human writing",
        "text": "The relationship between monetary policy and asset price inflation has been extensively studied in the literature. Central banks face a fundamental tension between their mandate for price stability and the unintended consequences of prolonged low interest rates on equity and real estate valuations.",
    },
]


def post_json(path, payload):
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"http://localhost:5000{path}",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read().decode("utf-8"))


def main():
    saved_content_id = None

    for item in TEST_INPUTS:
        status, result = post_json(
            "/submit",
            {"text": item["text"], "creator_id": "m5-test-user"},
        )
        print("\n" + "=" * 60)
        print(item["name"])
        print("HTTP status:", status)
        print("content_id:", result.get("content_id"))
        print("attribution:", result.get("attribution"))
        print("confidence:", result.get("confidence"))
        print("llm_score:", result.get("signals", {}).get("llm_score"))
        print("style_score:", result.get("signals", {}).get("style_score"))
        print("label:", result.get("label"))

        if saved_content_id is None and result.get("content_id"):
            saved_content_id = result["content_id"]

    if saved_content_id:
        print("\n" + "=" * 60)
        print("Testing appeal workflow")
        status, appeal_result = post_json(
            "/appeal",
            {
                "content_id": saved_content_id,
                "creator_reasoning": "I wrote this myself from personal experience. I am a non-native English speaker and my writing style may appear more formal than typical.",
            },
        )
        print("HTTP status:", status)
        print(json.dumps(appeal_result, indent=2))


if __name__ == "__main__":
    main()
