# 🌱 SproutAdvisor - Zone 6a Garden Specialist Agent

An intelligent, multi-tool agent built with Google's **Agent Development Kit (ADK)** and the **A2A Protocol**, specifically designed to assist beginner gardeners in US Hardiness Zone 6a with frontyard flower arrangement designs, backyard vegetable gardens, soil calculations, live weather tracking, and AI image/video generation.

![SproutAdvisor Demo](./sprout_advisor_demo.gif)

---

## 🚀 Key Capabilities & Implemented Tools

SproutAdvisor integrates Google Cloud services, database persistence, external weather APIs, and generative media models:

### 🛠️ Function Tools
* **`search_plants`**: Search the curated Zone 6a plant catalog filtered by placement (`frontyard`, `backyard`), category (`flower`, `vegetable`, `herb`), and sun exposure (`full_sun`, `partial_shade`, `shade`).
* **`add_plant_to_catalog`**: Add custom plant entries into the Firestore database catalog with specific care instructions.
* **`log_garden_action` & `get_garden_logs`**: Record and query persistent garden activity logs (e.g., planting, watering, fertilizing, pruning) stored in Firestore.
* **`calculate_garden_bed_supplies`**: Calculate required cubic feet and standard 0.75 cu. ft. soil/mulch bag quantities for custom rectangular garden beds.
* **`get_live_garden_weather`**: Retrieve real-time temperature, precipitation, wind speed, and weather conditions for Zone 6a via Open-Meteo.
* **`geocode_address` & `find_nearby_places`**: Locate local plant nurseries, garden centers, and agricultural supply stores using Google Maps APIs.
* **`generate_garden_item_image`**: Generate high-resolution plant and garden layout images using `gemini-3.1-flash-lite-image` in the `global` region and upload them to Google Cloud Storage.
* **`generate_garden_item_video`**: Generate short video clips of blooming plants and garden scenes using Google's `gemini-omni-flash-preview` model in the `global` region.

---

## ☁️ Google Cloud Services & Architecture

* **Vertex AI Memory Bank (`VertexAiMemoryBankService`)**: Provides durable, cross-session user memory via `PreloadMemoryTool` and an automated memory generation callback (`generate_memories_callback`). Automatically extracts and remembers user preferences (such as preferred flower colors) and health/plant allergies across sessions.
* **Google Cloud Firestore**: Serves as the primary persistent database for storing plant catalog collections (`sprout_plants`) and user garden activity logs (`sprout_garden_logs`).
* **Google Cloud Storage (GCS)**: Public media hosting bucket (`sprout-advisor-media-qwiklabs-gcp-02-0b1b594835a1`) storing generated plant images and garden videos.
* **Vertex AI Models**:
  * `gemini-2.5-flash`: Core reasoning agent LLM model.
  * `gemini-3.1-flash-lite-image`: Image generation model (`location="global"`).
  * `gemini-omni-flash-preview`: Video generation model (`location="global"`).
* **Agent Engine Sandbox Code Executor (`AgentEngineSandboxCodeExecutor`)**: Executes Python code securely in a remote sandboxed container environment.
* **A2UI Schema Manager (`a2ui.schema.manager`)**: Emits structured UI metadata cards (version 0.8) for display in ADK interfaces.

---

## 📁 Repository Structure

```
sprout-advisor/
├── app/
│   ├── __init__.py          # Package initialization
│   ├── agent.py             # Root agent definition, tool registrations & callbacks
│   ├── a2ui_utils.py        # A2UI callback and JSON response extractor
│   └── fast_api_app.py      # Local FastAPI server configuration
├── frontend/
│   ├── main.py              # A2A proxy server connecting frontend to Agent Engine
│   ├── requirements.txt     # Proxy frontend dependencies
│   ├── Dockerfile           # Container build definition for Cloud Run
│   └── static/
│       └── index.html       # Botanical chat UI with dialogue bubbles & prompt chips
├── agents-cli-manifest.yaml # Agent manifest configuration (ACLI 1.1.0)
├── deployment_metadata.json # Agent Engine deployment resource metadata
├── sprout_advisor_demo.gif  # Recorded demonstration GIF
└── README.md                # Project documentation
```

---

## 💻 Local Setup & Execution Instructions

Follow these steps to run SproutAdvisor locally on your machine:

### 1. Prerequisites & Environment Setup

Ensure Python 3.10+ and Google Cloud SDK (`gcloud`) are installed. Authenticate your account:

```bash
gcloud auth login
gcloud auth application-default login
gcloud config set project qwiklabs-gcp-02-0b1b594835a1
```

### 2. Install Dependencies

Install the backend and frontend requirements:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r frontend/requirements.txt
```

### 3. Run the Agent locally (ADK Playground)

Start the local ADK developer playground to inspect agent tool calls and A2UI cards:

```bash
adk web app
```

### 4. Run the Web Frontend Proxy

To run the custom chat frontend locally:

```bash
export AGENT_ENGINE_RESOURCE_NAME="projects/273799513932/locations/us-east1/reasoningEngines/4262707624841052160"
export AGENT_DIRECTORY="sprout_advisor_app"

cd frontend
python main.py
```

Open your browser to the local port displayed in the console output to interact with the chat interface.
