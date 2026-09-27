# 🌍 Wayfarer | AI Travel Concierge

> An intelligent, multi-modal travel concierge built with Google's Agent Development Kit (ADK), Gemini 2.5 Flash, and Google Cloud Platform. Wayfarer transforms plain-text travel planning into interactive, UI-driven experiences complete with real-time database queries, budget estimations, and AI-generated postcard previews.

![Wayfarer AI Travel Concierge Demo](demo.gif)

---

## 💡 Motivation & Product Overview

Planning memorable trips often requires juggling multiple tools: checking maps, calculating exchange rates, looking up local dining reviews, and keeping track of personal travel preferences. 

**Wayfarer** unifies these fragmented tools into a single conversational concierge that goes beyond static text responses. Instead of returning plain text itineraries, Wayfarer emits **dynamic, structured user interfaces (A2UI)**—rendering interactive cards, structured tables, cost breakdowns, and high-resolution generative images directly inside the chat interface.

### Key Product Highlights
* **Cross-Session Personalization**: Retains travel styles, dietary preferences, and budget constraints across multiple visits via long-term memory.
* **Interactive UI Cards**: Delivers structured travel itineraries, dining recommendations, and budget breakdowns as clean, visual cards.
* **Visual Postcard Previews**: Generates bespoke, high-resolution AI travel postcards for destinations on demand.
* **Real-World Grounding**: Queries live dining and hotel collections while integrating real-time currency exchange rates.

---

## 🏗️ System Architecture

Wayfarer is architected as an **Agent-to-Agent (A2A) decoupled system** separating the core agent logic (running on Google Cloud Agent Runtime) from the client-facing proxy (running on Cloud Run).

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            CLIENT UI LAYER                                  │
│  Vanilla JS Chat UI + Built-in A2UI Renderer + Smooth Auto-Scroll Engine    │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ HTTP POST /chat
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      FASTAPI A2A PROXY (Cloud Run)                          │
│  Translates Browser Payload ◄──► A2A Protocol & Normalizes A2UI Data Parts  │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ Agent-to-Agent (A2A) Protocol
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                  REASONING ENGINE (Agent Runtime on GCP)                    │
│                        Gemini 2.5 Flash + ADK Core                          │
└────────┬───────────────────┬──────────────────┬────────────────────┬────────┘
         │                   │                  │                    │
         ▼                   ▼                  ▼                    ▼
┌─────────────────┐ ┌────────────────┐ ┌─────────────────┐ ┌──────────────────┐
│ Vertex AI       │ │ Cloud          │ │ Vertex AI       │ │ Google Maps      │
│ Memory Bank     │ │ Firestore      │ │ Imagen 3        │ │ Platform         │
│ (Cross-session) │ │ (Destinations) │ │ + Cloud Storage │ │ (Places/Geocode) │
└─────────────────┘ └────────────────┘ └─────────────────┘ └──────────────────┘
```

---

## 🎯 Technical Core & Implementation Details

The architecture incorporates key design patterns for robust, multi-modal agentic systems:

### 1. Agent-Driven UI (A2UI) Normalization & Rendering
* **The Challenge**: LLMs emitting raw JSON fragments (e.g., `surfaceUpdate` without `beginRendering`) can cause blank component renders or leak raw JSON syntax into user chat bubbles.
* **The Solution**: Implementation of a normalization layer (`a2ui_utils.py` and proxy middleware) that automatically inspects incoming payloads, infers unreferenced component root IDs, auto-injects missing `beginRendering` frames, and strips wrapper tags.
* **Client-Side Auto-Scroll Engine**: Integration of `ResizeObserver` and image `onload` event listeners on the DOM log container to maintain smooth auto-scrolling as heavy assets (e.g., Imagen 3 postcards) finish downloading.

### 2. Cross-Session Long-Term Memory (Vertex AI Memory Bank)
* **The Challenge**: Standard LLM sessions lose context when a user closes the browser or starts a new session.
* **The Solution**: Execution of `PreloadMemoryTool` alongside an `after_agent_callback` to asynchronously persist extracted user facts, dietary restrictions, and travel preferences to a managed Vertex AI Memory Bank instance.

### 3. Multi-Tool Function Orchestration
* **Firestore Querying (`search_travel_spots`, `add_travel_spot`)**: Queries curated dining and hotel records stored in Google Cloud Firestore and appends new spots dynamically.
* **Generative Postcard Creation (`generate_destination_preview`)**: Utilizes Vertex AI Imagen 3 (`imagen-3.0-generate-002`) to generate destination previews, uploads assets to Google Cloud Storage (`gs://wayfarer-travel-media-*`), and returns publicly accessible CDN URLs.
* **Google Maps Integration (`geocode_address`, `get_nearby_places`)**: Converts physical locations into latitude/longitude coordinates and fetches nearby points of interest via Google Maps APIs.
* **Budget & Exchange Rate Engine (`calculate_trip_budget`, `get_exchange_rate`)**: Computes itemized travel estimates (lodging, dining, transit, contingency) and converts totals using real-time currency conversion rates.

---

## 🛠️ Implemented Tool & Service Reference

| Service / Tool | Module | Description |
| :--- | :--- | :--- |
| **Gemini 2.5 Flash** | `app/agent.py` | Core reasoning model driving multi-tool selection and natural language orchestration. |
| **Vertex AI Memory Bank** | `app/agent.py` | Persists user preferences and travel facts across conversations. |
| **Cloud Firestore** | `app/tools.py` | Queries and writes structured destination records in the `destinations` collection. |
| **Vertex AI Imagen 3** | `app/tools.py` | Generates high-resolution destination postcard previews (`imagen-3.0-generate-002`). |
| **Google Cloud Storage** | `app/tools.py` | Hosts generated postcard image assets in a public GCS bucket. |
| **Google Maps Platform** | `app/tools.py` | Geocodes addresses and discovers nearby places via Places API. |
| **Trip Budget Engine** | `app/tools.py` | Itemizes lodging, food, transit, and contingency costs in USD and converts to target currency. |
| **A2UI Protocol** | `app/a2ui_utils.py` | Emits dynamic layout cards (Tables, Images, Cards, Columns, Rows) via `application/json+a2ui`. |

---

## ⚡ Challenges Faced

1. **Decoupled Proxy Architecture**: Separating the client proxy from the core agent engine isolates authentication, translates Agent-to-Agent (A2A) protocol messaging, and handles sanitization without cluttering agent prompts.
2. **A2UI Schema Resilience & Normalization**: Mitigated LLM schema drift where model responses omitted `beginRendering` frames or generated dangling component references, establishing an idempotent normalization layer that guarantees valid UI component trees.
3. **Asynchronous UX & Asset Loading**: Resolved layout truncation by attaching DOM `ResizeObserver` and image `onload` listeners so that the chat interface auto-scrolls smoothly as high-resolution Imagen 3 assets render.
4. **State Management & Memory Persistence**: Combined short-term thread state with long-term Vertex AI Memory Bank persistence, balancing context window constraints with multi-session user personalization.

---

## 📁 Repository Structure

```
wayfarer-travel-concierge/
├── app/
│   ├── agent.py         # ADK Root Agent definition, prompts, & callbacks
│   ├── tools.py         # Custom tools (Firestore, Maps, Imagen 3, Budget)
│   ├── a2ui_utils.py    # A2UI callback parser & schema normalizer
│   └── fast_api_app.py  # Local agent execution server
├── frontend/
│   ├── main.py          # FastAPI A2A proxy server
│   ├── a2ui_utils.py    # Proxy-side A2UI extraction & normalization
│   └── static/
│       └── index.html   # Custom chat UI & built-in A2UI card renderer
├── agents-cli-manifest.yaml  # Deployment configuration & CLI metadata
├── demo.gif             # 3-prompt looping demo recording
└── README.md            # Project documentation & case study
```

---

## 🚀 Local Setup & Execution Guide

### Prerequisites
* **Python 3.11+**
* **Google Cloud SDK (`gcloud`)**
* Active GCP Project with Vertex AI, Firestore, Cloud Storage, and Google Maps APIs enabled

### 1. Installation

Clone the repository and install dependencies:

```bash
git clone <REPO_URL>
cd wayfarer-travel-concierge
pip install -r requirements.txt
```

### 2. Environment Configuration

Configure Google Cloud project credentials and API keys:

```bash
export GOOGLE_CLOUD_PROJECT="gcp-project-id"
export GOOGLE_CLOUD_LOCATION="us-east1"
export GOOGLE_MAPS_API_KEY="YOUR_KEY"
```

### 3. Start Agent Backend

Execute the local agent server using `agents-cli`:

```bash
agents-cli run
```

### 4. Start Frontend Proxy

In a separate terminal window, launch the FastAPI proxy server:

```bash
cd frontend
python main.py
```

---

## 🚢 Production Deployment Guide

### Deploy Agent to Agent Runtime (Reasoning Engine)

```bash
agents-cli deploy --project gcp-project-id --region us-east1
```

### Deploy Frontend Proxy to Cloud Run

```bash
cd frontend
gcloud run deploy wayfarer-frontend \
  --source . \
  --region us-east1 \
  --allow-unauthenticated \
  --set-env-vars AGENT_ENGINE_RESOURCE_NAME="<DEPLOYED_AGENT_RESOURCE_NAME>",AGENT_DIRECTORY="app"
```

---

## 📄 License

Distributed under the Apache 2.0 License.
