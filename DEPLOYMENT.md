# 🚀 VoiceMedic AI — Production Deployment Guide

This guide explains how to deploy **VoiceMedic AI** (FastAPI Backend + React Frontend) to the cloud.

---

## 🏗️ Architecture Overview

| Component | Stack | Recommended Cloud Host |
|---|---|---|
| **Frontend** | React 18 + Vite | **Vercel** / **Netlify** |
| **Backend** | FastAPI + SpeechBrain + Whisper + FFmpeg | **Render** / **Railway** / **VPS (Docker)** |

---

## ⚡ Option 1: Render (Backend) + Vercel (Frontend) — Recommended

### Step 1: Push Project to GitHub

1. Create a new repository on [GitHub](https://github.com/new) named `VoiceMedic_AI`.
2. Push your local project to GitHub:
   ```bash
   cd /Users/anuragkhubakar/Desktop/ASR/VoiceMedic_AI
   git remote add origin https://github.com/<YOUR_GITHUB_USERNAME>/VoiceMedic_AI.git
   git branch -M main
   git push -u origin main
   ```

---

### Step 2: Deploy Backend to Render

1. Go to [Render Dashboard](https://dashboard.render.com/) and click **New +** → **Web Service**.
2. Connect your GitHub repository `VoiceMedic_AI`.
3. Set the following settings:
   - **Name**: `voicemedic-backend`
   - **Region**: Singapore / Oregon / Frankfurt (closest to you)
   - **Root Directory**: `backend`
   - **Runtime**: **Docker** (Render will automatically detect `backend/Dockerfile`)
   - **Instance Type**: Starter / Standard (recommended: 1GB–2GB RAM for PyTorch & Whisper)
4. Under **Environment Variables**, add:
   - `GEMINI_API_KEY` = *your Google AI Studio API key*
   - `SPEAKER_VERIFICATION_THRESHOLD` = `0.55`
   - `WHISPER_MODEL` = `small`
5. Click **Deploy Web Service**.
6. When deployment finishes, copy your live backend URL (e.g., `https://voicemedic-backend.onrender.com`).

---

### Step 3: Deploy Frontend to Vercel

1. Go to [Vercel](https://vercel.com/) and click **Add New...** → **Project**.
2. Select your `VoiceMedic_AI` repository.
3. Configure the project:
   - **Framework Preset**: Vite
   - **Root Directory**: Click edit and select `frontend`
4. Under **Environment Variables**, add:
   - `VITE_API_BASE_URL` = *your Render backend URL* (e.g., `https://voicemedic-backend.onrender.com`)
5. Click **Deploy**.
6. In ~40 seconds, your site is live at `https://voicemedic-ai.vercel.app`! 🎉

---

## ⚡ Option 2: 1-Click Railway Deployment

1. Go to [Railway.app](https://railway.app/).
2. Click **New Project** → **Deploy from GitHub repo**.
3. Select `VoiceMedic_AI`.
4. Railway will automatically pick up `backend/Dockerfile` and `backend/railway.toml`.
5. Add `GEMINI_API_KEY` in Railway Settings.
6. Generate a public domain under **Networking**.

---

## ⚡ Option 3: Self-Hosted Docker Compose (Any VPS / Cloud Server)

To deploy on your own server (AWS EC2, DigitalOcean Droplet, etc.):

```bash
# 1. Clone repository on your server
git clone https://github.com/<YOUR_GITHUB_USERNAME>/VoiceMedic_AI.git
cd VoiceMedic_AI

# 2. Create .env with your Gemini API key
echo "GEMINI_API_KEY=your_key_here" > .env

# 3. Launch full stack (Frontend + Backend + Nginx)
docker compose up -d --build

# Your app is live at http://your-server-ip:5173
```
