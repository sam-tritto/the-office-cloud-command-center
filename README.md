# ScrantonOS — Dunder Mifflin Cloud Command Center 🏢

ScrantonOS is a persistent, multi-agent orchestration engine and web interface built to handle corporate cloud operations, system diagnostics, and Human-in-the-Loop (HITL) workflows. Powered by the Google Antigravity SDK and FastAPI, it routes natural language requests through a specialized team of AI agents modeled after the staff of Dunder Mifflin, Scranton.

## Features

- **Multi-Agent Orchestration Loops**: Requests are received by the orchestrator (Michael) and routed to subject matter experts (Dwight for SRE, Oscar for FinOps, Stanley for IAM, etc.). Michael evaluates their responses and can chain tasks to other agents (e.g., Dwight finds an error -> Pam generates a report).
- **Interactive Data Dashboard 📊**: A slide-out visualization drawer built with `Chart.js` to view system telemetry and analytics. It displays beautiful, dynamic charts generated from metadata returned by:
  - **Oscar (FinOps)**: A structured bar chart detailing billing breakdowns and anomalies.
  - **Dwight (SRE)**: A pie chart mapping system log error distribution and resource bottlenecks.
  - **Angela (Firebase)**: A bar chart visualizing Firebase crash rates and device breakdowns.
  - **Kevin (Metrics)**: A custom metric grid calculating "Keleven-adjusted" calculations.
- **Jim Halpert's Multimodal UI/UX Reviews 📎**: Upload frontend screenshots via the paperclip icon in the chat. The app converts the files to Base64, transmits them over WebSockets, and routes them as native image parameters to the Google Antigravity SDK using Gemini 1.5, allowing Jim to review layouts, alignments, and joke about the design quality.
- **Gabe Lewis's Vanilla RAG Documentation Search 📚**: A lightweight, offline-capable Retrieval-Augmented Generation (RAG) system built without external vector databases. It uses the Google GenAI SDK for local embeddings and gracefully falls back to a custom deterministic keyword-overlap algorithm when offline or missing API keys.
- **Async Webhook Alerts & Live Badges ⚡**: A specialized HTTP endpoint (`POST /api/webhooks/alerts`) allows third-party tools (GitHub Actions, Firebase, Prometheus) to push live status alerts. Active WebSocket clients receive real-time, toast-style notifications marked with high-visibility "⚡ LIVE" badges.
- **Persistent State & Audit Logging**: 
  - `DEV` Mode: Uses local CSV files for conversation memory, session tracking, and audit logging.
  - `PROD` Mode: Seamlessly switches to Google Cloud Firestore for serverless, horizontally scalable persistence.
- **Human-in-the-Loop (HITL)**: High-risk operations (like IAM grants or data purges) are gated by a compliance agent (Toby) and require explicit human approval via the UI or REST endpoint.
- **Synthetic Data Generation**: Includes a Faker-based generator to flood the system with realistic logs, billing data, and tech debt tickets to test agent behavior at scale.
- **Command Palette**: A built-in UI sidebar (triggered by the `?` icon) to quickly access slash commands.
- **Graceful Fallbacks**: Operates in mock/demo mode if no LLM API key is provided, returning hardcoded personality responses.

---

## 🛠️ Local Testing & Development

You can run ScrantonOS locally using either Python directly or Docker Compose.

### Prerequisites

1. Clone the repository.
2. Create a `.env` file from the example:
   ```bash
   cp .env.example .env
   ```
3. Set your `GEMINI_API_KEY` in the `.env` file to enable actual AI responses.
4. Generate the synthetic test data:
   ```bash
   python scripts/generate_synthetics.py
   ```

### Option A: Using Docker (Recommended for quick start)

The project includes a blazing-fast `Dockerfile` (using `uv` for dependency resolution) and a `docker-compose.yml`.

1. Build and start the container:
   ```bash
   docker-compose up --build
   ```
2. Open your browser and navigate to: **http://localhost:8000**
3. To stop the server, press `Ctrl+C` or run `docker-compose down`.

### Option B: Using Local Python (Recommended for development)

1. Ensure you have Python 3.11+ installed.
2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
3. Install dependencies using `uv` (or standard `pip`):
   ```bash
   pip install uv
   uv pip install -r requirements.txt
   ```
4. Start the FastAPI server:
   ```bash
   python server.py
   ```
5. Open your browser and navigate to: **http://localhost:8000**

---

## 🚀 Connecting to Production (Deployment)

ScrantonOS is designed as a cloud-native containerized web application, making it perfectly suited for modern platforms like **Google Cloud Run** or **Kubernetes**.

### 1. Environment Variables

In `PROD` mode, the application relies on Google Cloud services for state and secrets. You must configure the following:

- `ENV`: Set to `PROD`.
- `GCP_PROJECT_ID`: Your Google Cloud Project ID.
- `GEMINI_API_KEY`: **(Optional in ENV)** In PROD mode, if this is missing from the environment, `config.py` will automatically fetch it securely from **GCP Secret Manager**.
- `IAM_APPROVAL_SECRET`: **(Optional in ENV)** Fetched securely from Secret Manager to sign HITL tokens.

### 2. Architecture Changes in PROD

When `ENV=PROD` is set:
1. **Database Abstraction**: `database.py` abandons the local CSV files and initializes a connection to **Google Cloud Firestore**. Sessions, messages, and audit logs are written to Firestore collections.
2. **Secret Management**: `config.py` connects to GCP Secret Manager to inject API keys and signing secrets dynamically.

### 3. Deploying via Docker (General)

To deploy to any standard Docker environment (e.g., AWS ECS, Kubernetes, or a standalone VPS):

1. **Build and Tag the Image:**
   ```bash
   docker build -t scranton-os:latest .
   ```
2. **Push to your Registry (if applicable):**
   ```bash
   docker tag scranton-os:latest your-registry/scranton-os:latest
   docker push your-registry/scranton-os:latest
   ```
3. **Deploy the Container:**
   Run the image in your environment, ensuring you pass the `ENV=PROD` and `GCP_PROJECT_ID` environment variables.

### 4. Deploying to Google Cloud Run (Example)

Google Cloud Run natively supports WebSockets and container scaling.

```bash
# 1. Build and push the container to Google Artifact Registry
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/scranton-os

# 2. Deploy the container to Cloud Run
gcloud run deploy scranton-os \
  --image gcr.io/YOUR_PROJECT_ID/scranton-os \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars ENV=PROD,GCP_PROJECT_ID=YOUR_PROJECT_ID
```

*(Ensure the Cloud Run service account has permissions for Secret Manager Secret Accessor and Datastore User).*

### 5. Production & Security Considerations

- **Secret Security**: ScrantonOS is designed so that **no secrets are leaked in the Docker image or logs**. The `.dockerignore` file explicitly prevents `.env` from being baked into the image. In `PROD` mode, `config.py` fetches secrets dynamically at runtime, and `print()` statements only log the fetch *status* (e.g., "Fetching GEMINI_API_KEY..."), never the raw keys.

- **Authentication**: The base app serves the UI without a login wall. In production, you should place ScrantonOS behind an identity proxy (like Google Cloud Identity-Aware Proxy) to prevent unauthorized access to your cloud commands.
- **State Management**: While the database is offloaded to Firestore, pending HITL approvals (`workflow.pending_hitl`) are held in server memory for speed. If running multiple instances, configure **session affinity (sticky sessions)** on your load balancer, or move the `pending_hitl` dict to a fast Redis cache.
