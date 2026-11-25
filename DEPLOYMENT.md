# 🚀 VoiceMedic AI — Production Cloud Deployment Guide

This guide details the complete deployment process for **VoiceMedic AI** across modern cloud platforms.

- **Repository**: [https://github.com/Anurag9699/VoiceMedic_AI](https://github.com/Anurag9699/VoiceMedic_AI)
- **Architecture**: Decoupled FastAPI Backend (Docker / PyTorch / FFmpeg) + React 18 Frontend (Vite / Edge CDN)

---

## 🏗️ Architecture & Cloud Platform Selection

| Component | Technology Stack | Recommended Host | Free / Low-Cost Tier |
|---|---|---|---|
| **Backend** | Python 3.11, FastAPI, SpeechBrain, Whisper, FFmpeg | **Render** or **Railway** | Docker-based Web Service |
| **Frontend** | React 18, Vite, Web Audio API | **Vercel** or **Netlify** | Global Edge CDN with automated HTTPS |
| **Self-Hosted** | Docker Compose + Nginx reverse proxy | **AWS / DigitalOcean / Hetzner** | 1-command complete stack deploy |

---

## ⚡ Step 1: Deploy the Backend (Render or Railway)

Since the backend executes deep neural networks (**ECAPA-TDNN**, **Whisper**) and **FFmpeg** audio resampling, it must be deployed in a containerized Linux environment.

### Option A: Deploy on [Render.com](https://dashboard.render.com/) (Recommended)

1. Sign in to [Render Dashboard](https://dashboard.render.com/) using your GitHub account.
2. Click **New +** → **Web Service**.
3. Select your repository: **`VoiceMedic_AI`** (or `Anurag9699/VoiceMedic_AI`).
4. Configure the service settings:
   - **Name**: `voicemedic-backend`
   - **Region**: Select closest to your users (e.g. *Singapore*, *Frankfurt*, *Oregon*)
   - **Root Directory**: `backend`
   - **Runtime**: **Docker** *(Render detects `backend/Dockerfile` automatically)*
   - **Instance Type**: **Starter** ($7/mo) or Free instance *(Note: Starter with 1GB–2GB RAM is recommended for SpeechBrain & Whisper neural networks)*
5. Scroll down to **Environment Variables** and add:
   - `GEMINI_API_KEY`: *(Your Google AI Studio API Key)*
   - `SPEAKER_VERIFICATION_THRESHOLD`: `0.55`
   - `WHISPER_MODEL`: `small`
6. Click **Create Web Service**.
7. Once the build completes and health check passes, copy your public backend URL:
   `https://voicemedic-backend.onrender.com`

---

### Option B: Deploy on [Railway.app](https://railway.app/)

1. Log in to [Railway.app](https://railway.app/) with GitHub.
2. Click **New Project** → **Deploy from GitHub repo** → select `VoiceMedic_AI`.
3. Go to project **Settings** → **Build**:
   - Set **Dockerfile Path**: `backend/Dockerfile`
4. Go to **Variables** and add:
   - `GEMINI_API_KEY`: *(Your key)*
   - `SPEAKER_VERIFICATION_THRESHOLD`: `0.55`
   - `WHISPER_MODEL`: `small`
5. Go to **Networking** → Click **Generate Domain**.
6. Copy your public domain (e.g. `https://voicemedic-production.up.railway.app`).

---

## ⚡ Step 2: Deploy the Frontend (Vercel or Netlify)

The frontend is a lightweight Single Page Application (SPA) that communicates with your cloud backend via REST endpoints.

### Option A: Deploy on [Vercel.com](https://vercel.com/) (Recommended)

1. Sign in to [Vercel](https://vercel.com/) with GitHub.
2. Click **Add New...** → **Project**.
3. Select the `VoiceMedic_AI` repository and click **Import**.
4. Configure the build:
   - **Framework Preset**: `Vite` (automatically detected)
   - **Root Directory**: Click *Edit* and select **`frontend`**
5. Expand **Environment Variables** and add:
   - **Key**: `VITE_API_BASE_URL`
   - **Value**: *(Your backend URL from Step 1, e.g. `https://voicemedic-backend.onrender.com`)*
6. Click **Deploy**.
7. In ~30 seconds, your application will be live at `https://voicemedic-ai.vercel.app`! 🎉

---

### Option B: Deploy on [Netlify.com](https://netlify.com/)

1. Log in to [Netlify](https://app.netlify.com/) with GitHub.
2. Click **Add new site** → **Import an existing project** → GitHub.
3. Select `VoiceMedic_AI`.
4. Configure:
   - **Base directory**: `frontend`
   - **Build command**: `npm run build`
   - **Publish directory**: `frontend/dist`
5. Under **Environment variables**, add:
   - `VITE_API_BASE_URL`: *(Your backend URL)*
6. Click **Deploy site**.

---

## ⚡ Step 3: Self-Hosted Deployment via Docker Compose (Any VPS)

To deploy both frontend and backend on an AWS EC2, DigitalOcean Droplet, or Ubuntu VPS:

```bash
# 1. Clone the repository
git clone https://github.com/Anurag9699/VoiceMedic_AI.git
cd VoiceMedic_AI

# 2. Set your environment variable
export GEMINI_API_KEY="your_api_key_here"

# 3. Start the entire containerized stack
docker compose up -d --build

# The application is now live at:
# Frontend: http://<your-server-ip>:5173
# Backend:  http://<your-server-ip>:8000
```

---

## 🔒 Verification & Troubleshooting Checklist

1. **Verify Backend Health**:
   Visit `https://<YOUR-BACKEND-URL>/health` in your browser. It should return:
   ```json
   {"status": "ok", "system": "VoiceMedic AI"}
   ```

2. **Verify API Documentation**:
   Visit `https://<YOUR-BACKEND-URL>/docs` to view the interactive Swagger OpenAPI interface.

3. **HTTPS / Mixed Content Security**:
   Modern browsers block microphone access (`getUserMedia`) on unencrypted HTTP connections (except `localhost`). When deployed to production, both your frontend and backend **must** use `https://` URLs. Vercel, Netlify, Render, and Railway provide free automatic SSL certificates.

4. **Microphone Permissions**:
   Ensure the browser tab has microphone permission granted. If prompted, click **Allow**.
