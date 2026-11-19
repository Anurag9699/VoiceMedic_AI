# Backend - Voice-Controlled Payment System

This folder contains the FastAPI backend for the Voice-Controlled Payment System.

## Requirements

- Python 3.10+ (tested with Python 3.10+)

## Setup Instructions

1. **Navigate to the backend directory**:
   ```bash
   cd backend
   ```

2. **Create a virtual environment**:
   ```bash
   python3 -m venv .venv
   ```

3. **Activate the virtual environment**:
   - On macOS/Linux:
     ```bash
     source .venv/bin/activate
     ```
   - On Windows (Command Prompt):
     ```cmd
     .venv\Scripts\activate.bat
     ```
   - On Windows (PowerShell):
     ```powershell
     .venv\Scripts\Activate.ps1
     ```

4. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

5. **Start the development server**:
   ```bash
   uvicorn main:app --reload --port 8000
   ```

6. **Verify the server is running**:
   - Open [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health) in your browser.
   - Interactive Swagger API docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
