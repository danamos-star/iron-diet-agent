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

## 🛠️ Testing the approval flow (Golden Path)

1. **Turn 1 (Draft Phase)**: Send a `POST /chat` request:
   > *"Generate a 3-day high-iron meal plan with a grocery list and email it to user@example.com."*
   - **Result**: The agent outputs the generated meal plan and grocery list, then pauses and explicitly asks for your approval. No email is sent.

2. **Turn 2 (Approval Phase)**: Send a follow-up request in the same session:
   > *"Looks great, I approve! Please send the email."*
   - **Result**: The agent receives confirmation, triggers `send_email_notification`, and completes the pipeline.

## Verification screenshots

1. Deployment verification
   <img width="1872" height="729" alt="image" src="https://github.com/user-attachments/assets/5a05f87d-d555-44f5-a27d-6ed976855c05" />

2. Memory Bank configuration
   <img width="1855" height="609" alt="image" src="https://github.com/user-attachments/assets/9d17cf30-5fa2-4104-85a5-b5377b730fbb" />

3. Streamed Response verification
   <img width="1154" height="396" alt="image" src="https://github.com/user-attachments/assets/ba63c3a7-d1b2-4a38-9063-e482091765c0" />

   <img width="1163" height="442" alt="image" src="https://github.com/user-attachments/assets/6b5de5ba-fc52-4c67-9020-3add68bd40b7" />

## Agent Governance 

1. Model Armor gataway screening
   <img width="1082" height="191" alt="image" src="https://github.com/user-attachments/assets/87996c18-89cb-4112-99eb-9d9ccbe0b9a5" />

2. Agent Gateway ingress attachment
   <img width="986" height="98" alt="image" src="https://github.com/user-attachments/assets/3e024022-78d9-4002-8d17-4d284ab5dada" />

3. Registered Governance policy
   <img width="988" height="167" alt="image" src="https://github.com/user-attachments/assets/e536f404-ff0f-491f-a4d3-d2e5481aad55" />

4. PII reduction in action
   <img width="987" height="279" alt="image" src="https://github.com/user-attachments/assets/43b26228-3395-4dac-950b-f2a816b68b62" />

5. Application layer guardrail
   <img width="902" height="406" alt="image" src="https://github.com/user-attachments/assets/3d65b90b-a2f7-40ea-bf07-cfac90aa6c0f" />








   



