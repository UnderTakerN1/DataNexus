# DataNexus: AI Game Strategy Consultant

> An intelligent Discord bot for game developers — combining LLMs with structured data analysis to act as your virtual creative director and market analyst.

---

## Overview

DataNexus helps game developers **brainstorm**, **analyze market trends**, and **assess project feasibility** — all from within Discord. Rather than relying purely on AI-generated guesswork, it grounds its responses in real-world game data, delivering precise budgets, development roadmaps, and risk analyses.

---

## Core Features

### Hybrid State Machine
Seamlessly transitions between two modes:
- **Consultant Mode** — Handles general queries and freeform conversation
- **Architect Mode** — Runs a structured, guided game design interview

### Data-Driven Insights
Loads a structured dataset (`Games_csv.csv`) directly into memory to provide factual, data-backed recommendations — not just AI guesses.

### Smart Token Optimization
Dynamically injects CSV context into the LLM prompt **only when strictly necessary**, preventing API rate limits and token bloat.

### Typo-Tolerant Search
A custom data search command powered by `difflib` enables case-insensitive, fuzzy-matched dataset queries.

---

## Technology Stack

| Layer | Technology |
|---|---|
| **Language** | Python 3 |
| **Data Processing** | pandas |
| **AI / NLP** | Groq API — *Llama 3.3 70B Versatile* |
| **Discord Interface** | discord.py |

---

## Setup & Installation

### 1. Clone the Repository

```bash
git clone https://github.com/YourUsername/DataNexus.git
cd DataNexus
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables

Create a `.env` file in the root directory and add your credentials:

```env
DISCORD_TOKEN=your_discord_bot_token
GROQ_API_KEY=your_groq_api_key
```

### 4. Run the Bot

```bash
python main.py
```

---

## Command Reference

### Game Design Flow

| Command | Description |
|---|---|
| `?Gameidea` | Launches a structured **10-question** interactive game design interview |
| `?roadmap` | Generates a full development roadmap *(run after `?Gameidea`)* |
| `?budget` | Produces a detailed budget estimate *(run after `?Gameidea`)* |
| `?risks` | Delivers a deep-dive risk analysis *(run after `?Gameidea`)* |
| `?end` | Safely exits the interactive design mode at any point |

### Market Analysis

| Command | Description |
|---|---|
| `?Predict <Game>` | Evaluates a game's future viability based on historical dataset trends |
| `?SearchData <Game>` | Fetches exact records for a title directly from the CSV dataset |

---

## Workflow

```
User runs ?Gameidea
        │
        ▼
  10-Question Interview (Architect Mode)
        │
        ▼
  ┌─────┴──────────────┐
  │                    │
?roadmap           ?budget / ?risks
  │                    │
  ▼                    ▼
Development       Budget & Risk
  Roadmap           Analysis
```

---

## Project Structure

```
DataNexus/
├── main.py               # Entry point
├── Games_csv.csv         # Structured game dataset
├── requirements.txt      # Python dependencies
├── .env                  # API credentials (not committed)
└── README.md
```

---

## License

This project is open for development use. Please review your Groq API and Discord Bot Terms of Service before deploying publicly.
