You are an expert Systems Architect and Lead AI Engineer specializing in multi-agent frameworks, LangGraph, and Python DevOps. 

I need to design, architect, and plan the development of a specific module: "The Virtual Meeting Room Chat Framework" using LangGraph. This system simulates a corporate/group meeting between multiple AI Persona Agents with different role/persona. Each persona agent can be consider as a Digital Twins of persona.

### 1. SYSTEM OVERVIEW & CORE LOGIC
- **Architecture**: LangGraph StateGraph utilizing a Centralized State and an Orchestrator Node (Pure Python control logic) rather than letting LLM agents route themselves.
- **State Management**: The global state must track:
  - `messages`: List of all dialogue turns.
  - `relationship_matrix`: A dynamic matrix dictating conflicts, factions, and optionally by configurationzodiac/horoscope/astrology (tử vi, bát tự) modifiers.
  - `current_speaker`: The ID of the persona selected to speak next.
  - `loop_count`: Integer tracking meeting rounds.
  - `stagnation_score`: Counter for redundant arguments.
- **Stopping Criteria (Critical)**:
  a) Max Rounds: `loop_count` hits a predefined threshold.
  b) Consensus: A lightweight Sub-Agent (Meeting Secretary) evaluates the recent chat state and detects agreement (>80% consensus or key stakeholder approval).
  c) Stagnation (Cãi cùn): Using Vector Embeddings to compute Cosine Similarity between recent turns. If similarity > 0.85 for consecutive turns (Information Gain ~ 0), increment `stagnation_score`. Trigger termination if it hits the limit.

### 2. POST-SIMULATION CHAT
After the graph terminates, the state is persisted. 
The system conducts an insight report of the chat.
The user can switch to a 1-1 private chat UI with any specific Persona. The context for this 1-1 chat is: Persona Prompt + Horoscope Data(optionally by configuration) + Dynamic Relationship Matrix + The Entire Simulated Meeting Transcript.

### 3. YOUR TASK
Analyze, design, and break down this module into a production-ready execution plan. Provide the following outputs in structured Markdown:

#### Step 1: Data Models & State Definition (Pydantic / Python)
- Define the exact schema for `MeetingState` using TypeDict or Pydantic.
- Define the schema for the `relationship_matrix` and Persona profiles (including traits, conflicts, and astrology factors).

#### Step 2: LangGraph Architecture Design
- Map out all Nodes (`orchestrator_node`, `persona_node`, `secretary_node`).
- Detail the logic for `orchestrator_node` (How it reads the matrix and the last speaker to select the next speaker).
- Write out the Python pseudo-code/structure for the `conditional_edge` handling the 3 stopping criteria (Max loops, Consensus, Cosine Similarity Stagnation).

#### Step 3: 1-1 Interrogation Chat Architecture
- Explain how the state transfers from the completed graph into an isolated, independent chat session with a single persona agent.

#### Step 4: Phased Development Plan (Modular Break Down)
- Break down the implementation into 4 sequential, iterative phases (e.g., Phase 1: Core Graph & State; Phase 2: Orchestration & Matrix Logic; Phase 3: Stopping Criteria & Vector Checks; Phase 4: Persistence & 1-1 Chat Interface).
- For each phase, specify: Objectives, Files to create/modify, and concrete Definition of Done (DoD).

Think step-by-step. Ensure the design is highly modular, scalable, and tailored to LangGraph's unique state-sharing design patterns. Avoid abstract summaries; give me concrete architectural blueprints.