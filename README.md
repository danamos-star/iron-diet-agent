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