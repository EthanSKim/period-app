# Period App Monorepo

Welcome to the **Period App** monorepo! This repository contains a fully containerized stack using React for the frontend, FastAPI for the backend, and PostgreSQL for the database.

## Architecture & Directory Structure

```text
period-app/
├── .github/
│   └── workflows/
│       └── ci.yml             # GitHub Actions CI workflow (ESLint, Ruff, builds)
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── database.py        # SQLAlchemy session & DB dependency setup
│   │   └── main.py            # FastAPI entry point & endpoints (/health, /)
│   ├── Dockerfile             # Multi-stage Dockerfile (dev & prod targets)
│   ├── pyproject.toml         # Ruff linting & formatting configurations
│   └── requirements.txt       # Python dependencies
├── frontend/
│   ├── public/                # Static assets
│   ├── src/                   # React TypeScript source code
│   ├── .prettierrc            # Prettier configurations
│   ├── Dockerfile             # Multi-stage Dockerfile with Nginx for prod
│   ├── eslint.config.js       # ESLint flat config with Prettier integration
│   ├── nginx.conf             # Nginx configuration for Vite SPA routes (prod)
│   ├── package.json           # Frontend packages & scripts
│   └── vite.config.ts         # Vite configuration (runs on port 3000)
├── .env                       # Local environment variables
├── .env.example               # Template environment variables
├── .gitignore                 # Monorepo git exclusion rules
└── docker-compose.yml         # Container orchestration (dev-mode volume bind mounts)
```

### Services & Port Bindings

| Service | Technology | Port (Host) | Port (Container) | Purpose |
| :--- | :--- | :--- | :--- | :--- |
| **frontend** | React + Vite + TS | `3000` | `3000` | UI Client |
| **backend** | FastAPI (Python) | `8000` | `8000` | Application API |
| **db** | PostgreSQL 16 | `5432` | `5432` | Relational Database |

---

## Getting Started

### Prerequisites

Ensure you have the following installed on your machine:
- [Docker & Docker Compose](https://www.docker.com/products/docker-desktop/)
- [Node.js v20+](https://nodejs.org/) (for local frontend dev)
- [Python 3.11+](https://www.python.org/) (for local backend dev)

### Setup Environment Variables

The project uses `.env` files for configuration. A template file `.env.example` is provided:

```bash
cp .env.example .env
```

You can customize the credentials and URLs inside `.env` to match your local requirements.

### Run with Docker Compose

To build and start the entire stack in development mode:

```bash
docker-compose up --build
```

- **Frontend** will be accessible at: [http://localhost:3000](http://localhost:3000)
- **Backend API** will be accessible at: [http://localhost:8000](http://localhost:8000)
- **Backend Health Check**: [http://localhost:8000/health](http://localhost:8000/health)
- **PostgreSQL Database** is running on port `5432` with connection parameters matching your `.env` values.

To stop the containers and keep data intact:

```bash
docker-compose down
```

To stop containers and delete database volumes:

```bash
docker-compose down -v
```

---

## Local Development (Without Docker)

If you prefer to run services individually outside of containers:

### 1. Backend

Create a Python virtual environment and install packages:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Run the development server:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 2. Frontend

Install npm packages:

```bash
cd frontend
npm install
```

Run the Vite development server:

```bash
npm run dev
```

---

## Linting and Code Quality

### Frontend

The frontend uses **ESLint** and **Prettier** to maintain code standards.

- Run linter check:
  ```bash
  cd frontend
  npm run lint
  ```
- Format code using Prettier:
  ```bash
  cd frontend
  npm run format
  ```

### Backend

The backend uses **Ruff** for high-performance python linting and formatting.

- Run linter check:
  ```bash
  cd backend
  ruff check .
  ```
- Run formatting check:
  ```bash
  cd backend
  ruff format --check .
  ```
- Auto-fix linting issues and re-format:
  ```bash
  cd backend
  ruff check --fix .
  ruff format .
  ```

---

## Continuous Integration (CI)

A GitHub Actions workflow is located at `.github/workflows/ci.yml`. It runs on every `pull_request` targeting the main branch. The workflow ensures:
1. Frontend code is formatted (Prettier), linted (ESLint), and successfully built (`npm run build`).
2. Backend code complies with Ruff's linting and formatting standards.
