# Iron Diet Agent 🌿🥩

A personalized nutrition assistant built with the **Google Agent Development Kit (ADK)** and **FastAPI**. The agent specializes in non-heme iron optimization, multi-day vegetarian and non-vegetarian meal planning, dynamic grocery list categorization, and automated email notifications with human-in-the-loop approval gates.

---

## 🌟 Key Features

* **Dynamic Skill System**: Utilizes ADK `SkillToolset` to dynamically load domain knowledge skills (`diet-planner`, `grocery-list`, `brand-voice`).
* **Sub-Agent Isolation**: Wraps web search capabilities (`GoogleSearchTool`) inside a dedicated search sub-agent linked via `AgentTool`.
* **Human-in-the-Loop Confirmation Gate**: Protects external actions (`send_email_notification`) by requiring explicit user confirmation before executing side-effects.
* **Stateful Pipeline Callbacks**: Tracks execution state live across stages (`idea` $\rightarrow$ `researching` $\rightarrow$ `planning` $\rightarrow$ `grocery_list` $\rightarrow$ `awaiting_approval` $\rightarrow$ `completed`).

---

## 📂 Architecture & Project Structure

```text
iron-diet-agent/
├── backend/
│   ├── agent.py          # Root orchestrator & sub-agent definitions
│   ├── main.py           # FastAPI server & route handlers
│   ├── tools.py          # Custom function tools (e.g., email notification)
│   └── prompts.py        # System prompt templates
├── skills/
│   ├── brand-voice/      # Compliance and tone guidelines
│   ├── diet-planner/     # High-iron meal planning rules
│   └── grocery-list/     # Categorized ingredient extraction rules
├── .env                  # Environment variables (excluded from Git)
├── .gitignore            # Git ignore file
└── pyproject.toml        # Project dependencies & configuration
```

## 🚀 Quick Start

### 1. Prerequisites
- Python 3.11+
- [`uv`](https://github.com/astral-sh/uv) package manager
- Google Vertex AI / Gemini API access

### 2. Environment Setup
Create a `.env` file in the root directory:

```env
PROJECT_ID=your-gcp-project-id
LOCATION=us-central1
AGENT_NAME=iron-diet-agent
ORCHESTRATOR_MODEL=gemini-2.5-flash

# Optional: Email notification credentials
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SENDER_EMAIL=your-email@gmail.com
SENDER_PASSWORD=your-app-password
```
### 3. Installation & Local Execution
Install dependencies and run the server using `uv`:

```bash
# Install dependencies
uv sync

# Run backend FastAPI server
uv run python -m backend.main
```

Access the interactive API documentation at:

[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

## 🛠️ Testing the Approval Flow (Golden Path)

1. **Turn 1 (Draft Phase)**: Send a `POST /chat` request:
   > *"Generate a 3-day high-iron meal plan with a grocery list and email it to user@example.com."*
   - **Result**: The agent outputs the generated meal plan and grocery list, then pauses and explicitly asks for your approval. No email is sent.

2. **Turn 2 (Approval Phase)**: Send a follow-up request in the same session:
   > *"Looks great, I approve! Please send the email."*
   - **Result**: The agent receives confirmation, triggers `send_email_notification`, and completes the pipeline.