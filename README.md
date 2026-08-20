# SciCalc – Advanced Scientific Calculator

A full-stack scientific calculator web application built with:

- **Frontend** – HTML5, CSS3, Vanilla JavaScript
- **Backend** – Python + FastAPI
- **Database** – MongoDB
- **Communication** – REST API via `fetch()`

---

## Project Structure

```
scientific-calculator/
│
├── frontend/
│   ├── index.html          # Calculator UI
│   ├── style.css           # Responsive styles, dark/light theme
│   └── script.js           # Calculator logic, API calls, history
│
├── backend/
│   ├── main.py             # FastAPI app, CORS, lifespan
│   ├── database.py         # MongoDB connection helpers
│   ├── models.py           # Pydantic request/response models
│   ├── routes/
│   │   └── calculator.py   # API route handlers
│   ├── services/
│   │   └── calculator_service.py  # Safe expression evaluator
│   ├── requirements.txt    # Python dependencies
│   └── .env                # Environment variables (never commit secrets)
│
└── README.md
```

---

## 1. Prerequisites

| Tool | Minimum version | Notes |
|------|----------------|-------|
| Python | 3.11+ | [python.org](https://www.python.org/) |
| MongoDB | 6.0+ | [mongodb.com](https://www.mongodb.com/try/download/community) |
| A static file server | any | VS Code Live Server, Python http.server, etc. |

---

## 2. Configure MongoDB

1. Install and start MongoDB Community Server.
2. By default it listens on `mongodb://localhost:27017` — no extra configuration needed for local development.
3. The application will automatically create the `scientific_calculator` database and `calculations` collection on first use.

---

## 3. Configure the `.env` file

Open `backend/.env` and confirm (or change) the values:

```env
MONGODB_URL=mongodb://localhost:27017
DATABASE_NAME=scientific_calculator
```

If your MongoDB requires authentication:

```env
MONGODB_URL=mongodb://username:password@localhost:27017
```

> **Security**: Never commit `.env` to version control. Add it to `.gitignore`.

---

## 4. Install Python Dependencies

```bash
cd scientific-calculator/backend

# Create a virtual environment (recommended)
python -m venv venv

# Activate it
# Windows PowerShell:
venv\Scripts\activate
# macOS / Linux:
source venv/bin/activate

# Install packages
pip install -r requirements.txt
```

---

## 5. Start the Backend

From inside the `backend/` directory (with the venv active):

```bash
uvicorn main:app --reload
```

The API will be available at:

| URL | Description |
|-----|-------------|
| `http://127.0.0.1:8000` | Health check (JSON) |
| `http://127.0.0.1:8000/docs` | Swagger UI – interactive API docs |
| `http://127.0.0.1:8000/redoc` | ReDoc – alternative API docs |

You should see log output like:

```
INFO  Starting SciCalc API…
INFO  MongoDB connection: OK
INFO  Uvicorn running on http://127.0.0.1:8000
```

---

## 6. Start the Frontend

The frontend is plain HTML/CSS/JS — no build step required.

### Option A – VS Code Live Server (recommended)

1. Install the **Live Server** extension in VS Code.
2. Right-click `frontend/index.html` → **Open with Live Server**.
3. The browser opens at `http://127.0.0.1:5500`.

### Option B – Python built-in HTTP server

```bash
cd scientific-calculator/frontend
python -m http.server 5500
```

Then open `http://localhost:5500` in your browser.

### Option C – Open directly

Double-click `frontend/index.html` to open it in a browser.
The browser will send the origin `null` for `file://` URLs — this is
already allowed in the backend CORS configuration.

---

## 7. How the Frontend Communicates with the Backend

```
User clicks "=" or presses Enter
        │
        ▼
script.js  →  POST http://127.0.0.1:8000/api/calculate
              Body: { "expression": "sin(30)", "mode": "DEG" }
        │
        ▼
FastAPI routes/calculator.py
        │
        ▼
services/calculator_service.py  (safe eval in locked namespace)
        │
        ▼
MongoDB  →  stores { expression, result, mode, created_at }
        │
        ▼
Response: { "expression": "sin(30)", "result": 0.5, "mode": "DEG" }
        │
        ▼
script.js updates the result display
```

All communication is JSON over HTTP. The frontend never connects
directly to MongoDB.

---

## 8. API Endpoints

### POST `/api/calculate`

Evaluate a mathematical expression.

**Request body**
```json
{
  "expression": "sqrt(144)",
  "mode": "DEG"
}
```

**Response**
```json
{
  "expression": "sqrt(144)",
  "result": 12.0,
  "mode": "DEG"
}
```

---

### GET `/api/history?limit=50&skip=0`

Return recent calculations, newest first.

**Response**
```json
{
  "calculations": [
    {
      "_id": "64f1a2b3c4d5e6f7a8b9c0d1",
      "expression": "sqrt(144)",
      "result": 12.0,
      "mode": "DEG",
      "created_at": "2026-08-20T12:00:00Z"
    }
  ],
  "total": 1
}
```

---

### DELETE `/api/history/{id}`

Delete a single calculation record.

---

### DELETE `/api/history`

Clear all history.

---

## 9. Test the API with Swagger

1. Open `http://127.0.0.1:8000/docs` in your browser.
2. Click **POST /api/calculate** → **Try it out**.
3. Paste this body and click **Execute**:

```json
{
  "expression": "sin(30)",
  "mode": "DEG"
}
```

Expected result: `0.5`

4. Click **GET /api/history** → **Execute** to see stored calculations.

---

## 10. Test MongoDB History

With MongoDB running and at least one calculation performed:

```bash
# Open the MongoDB shell
mongosh

# Switch to the application database
use scientific_calculator

# List all stored calculations
db.calculations.find().pretty()

# Count records
db.calculations.countDocuments()

# Delete all records manually
db.calculations.deleteMany({})
```

---

## 11. Supported Operations

### Basic
`+`  `−`  `×`  `÷`  `%`  `=`

### Scientific Functions
| Function | Description |
|----------|-------------|
| `sin`, `cos`, `tan` | Trigonometric (respects DEG/RAD mode) |
| `asin`, `acos`, `atan` | Inverse trig (result in DEG/RAD) |
| `sinh`, `cosh`, `tanh` | Hyperbolic |
| `log` / `log10` | Base-10 logarithm |
| `ln` | Natural logarithm |
| `sqrt` | Square root |
| `cbrt` | Cube root |
| `exp` | eˣ |
| `abs` | Absolute value |
| `floor`, `ceil`, `round` | Rounding |
| `factorial` | n! (integer ≤ 170) |
| `x²`, `x³`, `xʸ` | Powers |

### Constants
`π` (pi) · `e` (Euler's number)

---

## 12. Features

- Scientific and basic arithmetic
- DEG / RAD angle mode toggle
- Keyboard support (`0–9`, `+`, `-`, `*`, `/`, `Enter`, `Escape`, `Backspace`)
- Calculation history (stored in MongoDB)
- Click any history item to reload it
- Delete individual history items or clear all
- Dark / Light theme toggle (persisted in `localStorage`)
- Copy result to clipboard
- Responsive layout (desktop, tablet, mobile)
- Graceful error handling (division by zero, invalid expressions, etc.)
- FastAPI auto-generated docs at `/docs` and `/redoc`

---

## 13. Deployment Notes

### Backend

1. Deploy to any cloud VM, container service, or PaaS (Railway, Render, Fly.io).
2. Set environment variables `MONGODB_URL` and `DATABASE_NAME` in your hosting platform — do not rely on `.env` in production.
3. Use MongoDB Atlas for a managed cloud database.
4. Remove `"null"` from `ALLOWED_ORIGINS` in `main.py` and add your real frontend domain.
5. Run without `--reload` in production:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 2
```

### Frontend

The frontend is a static site — deploy to:
- **Netlify / Vercel** – drag and drop the `frontend/` folder
- **GitHub Pages** – push `frontend/` to a `gh-pages` branch
- **S3 + CloudFront** – upload the three files

After deploying, update `API_BASE` in `script.js` to your backend's
public URL:

```js
const API_BASE = "https://your-backend.example.com/api";
```

---

## 14. Troubleshooting

| Symptom | Fix |
|---------|-----|
| `MongoDB is not reachable` in backend logs | Start MongoDB: `mongod` or via Services |
| `CORS error` in browser console | Confirm the frontend origin is in `ALLOWED_ORIGINS` in `main.py` |
| `422 Unprocessable Entity` from `/api/calculate` | Check `detail` field in the response for the specific error |
| Result shows `Error` in the display | Hover over the status message for details |
| History panel shows "Could not load history" | Backend is not running or MongoDB is down |
#   S c i e n t i f i c - C a l c u l a t o r - w i t h - A I - V o i c e - A s s i s t a n t  
 