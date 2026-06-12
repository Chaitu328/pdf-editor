# Bilingual PDF OCR & Photo Editor

An interactive tool to analyze bilingual (English & Telugu) documents/PDFs using high-accuracy PaddleOCR merging, replace text dynamically via direct vector insertion, upload replacement profile photos, and download updated PDF documents.

---

## 🏗️ Repository Directory Structure

```
pdf-editor/
├── app/                  # Python FastAPI Service (OCR, PDF Editing & Storage)
│   ├── .venv/            # Python Virtual Environment
│   ├── routes/           # FastAPI router endpoints
│   ├── services/         # Core logic (OCR parser, PDF fitz editor)
│   ├── storage/          # Local uploads/outputs directory
│   ├── utils/            # Shared helpers & font files
│   ├── main.py           # Entrypoint for FastAPI
│   └── requirements.txt  # Python requirements
├── backend/              # Node.js API Gateway (multers, proxies)
│   ├── index.js          # Gateway entrypoint
│   └── package.json      # Express backend configuration
├── frontend/             # Vite + React Frontend Interface
│   ├── src/              # React components & styling
│   └── package.json      # React dependencies
├── .gitignore            # Workspace ignore settings
├── example_pdf.pdf       # Sample PDF document
└── README.md             # Setup and developer guide (This file)
```

---

## 🛠️ Installation & Setup Guide

To run the application, you need to open **three separate terminals** in the project root directory.

### 1️⃣ Python FastAPI Service (`app/`)
The Python virtual environment and dependencies are located inside the `app/` folder.

**Run directly from the root directory (Recommended, avoids PowerShell script execution policy issues):**
```powershell
# Run the FastAPI microservice using the virtual environment python interpreter directly
app\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

**Alternative: Run from inside the `app/` folder:**
```powershell
# 1. Navigate to the app folder
cd app

# 2. Run the FastAPI microservice (imports will resolve correctly via our path correction)
..\app\.venv\Scripts\python.exe -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

**Alternative: Activate the environment first (PowerShell):**
```powershell
# 1. Activate the Python virtual environment (if allowed by your system policy)
app\.venv\Scripts\Activate.ps1

# 2. Run the FastAPI microservice from the root directory
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

**Alternative: Activate the environment first (Command Prompt / CMD):**
```cmd
app\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

- **Service URL**: `http://127.0.0.1:8000`

---

### 2️⃣ Node.js API Gateway (`backend/`)
The Node gateway proxies and handles request payload sizes between the frontend and the Python service.

**Commands (Any Terminal):**
```bash
# 1. Navigate to the backend folder
cd backend

# 2. Install gateway dependencies
npm install

# 3. Start the gateway server in development mode
npm run dev
```

- **Gateway URL**: `http://localhost:3000`

---

### 3️⃣ Vite React Frontend (`frontend/`)
The interactive user interface for editing text blocks and uploading photos.

**Commands (Any Terminal):**
```bash
# 1. Navigate to the frontend folder
cd frontend

# 2. Install React frontend dependencies
npm install

# 3. Start the Vite React development server
npm run dev
```

- **Frontend URL**: `http://localhost:5174/` (or `http://localhost:5173/`)

---

## ⚙️ Environment Variables

The config settings are defined as follows:

*   **Python Service env (`app/.env`):**
    ```env
    API_KEY=d4d3b6bea6ed7282a7adc0b02378dadf19f398e0c059cec19d2b30d215ca5d03
    UPLOAD_DIR=storage/uploads
    OUTPUT_DIR=storage/outputs
    STORAGE_DIR=storage
    OCR_LANG=te
    ```

*   **Node Gateway env (`backend/.env`):**
    ```env
    PORT=3000
    PDF_SERVICE_URL=http://127.0.0.1:8000
    PDF_SERVICE_API_KEY=d4d3b6bea6ed7282a7adc0b02378dadf19f398e0c059cec19d2b30d215ca5d03
    ```
