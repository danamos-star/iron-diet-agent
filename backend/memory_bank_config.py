import os
import sys
import vertexai

PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "801421770925")
LOCATION = "us-central1"
ENGINE_ID = os.getenv("AGENT_ENGINE_ID", "7025378199064281088")
ENGINE_NAME = f"projects/{PROJECT}/locations/{LOCATION}/reasoningEngines/{ENGINE_ID}"

MEMORY_BANK_CONFIG = {
    "customization_configs": [{
        "memory_topics": [
            {"managed_memory_topic": {"managed_topic_enum": "USER_PREFERENCES"}},
            {"managed_memory_topic": {"managed_topic_enum": "EXPLICIT_INSTRUCTIONS"}},
            {"custom_memory_topic": {
                "label": "posting_style",
                "description": "User's formatting, tone, sign-offs, emoji usage, and posting style rules.",
            }},
        ]
    }],
    "ttl_config": {"default_ttl": "7776000s"},  # 90 days
}


def apply_config():
    client = vertexai.Client(project=PROJECT, location=LOCATION)
    print(f"Updating {ENGINE_NAME} ...")
    client.agent_engines.update(
        name=ENGINE_NAME,
        config={"context_spec": {"memory_bank_config": MEMORY_BANK_CONFIG}},
    )
    # Read back instead of trusting the call
    engine = client.agent_engines.get(name=ENGINE_NAME)
    print("Applied context_spec:")
    print(engine.api_resource.context_spec)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "apply":
        apply_config()
    else:
        print("Usage: python backend/memory_bank_config.py apply")