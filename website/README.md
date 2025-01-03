# Playbooks Website

This repository contains both the API (FastAPI) and frontend (Next.js) components of the Playbooks website.

## Development Setup

### Prerequisites

1. Python 3.x
2. Node.js and npm
3. Ruby (for foreman)

### Installation

1. Install foreman (process manager):
```bash
sudo gem install foreman
```

2. Set up API:
```bash
cd api
pip install -r requirements.txt
```

3. Set up Frontend:
```bash
cd frontend
npm install
```

### Running for Development

We use foreman to run both the API and frontend services concurrently. From the `website` directory:

```bash
foreman start
```

This will start:
- API server at http://localhost:8000
- Frontend development server at http://localhost:3000

### Testing

#### Frontend Tests

1. Unit Tests:
```bash
cd frontend
npm test           # Run tests once
npm run test:watch # Run tests in watch mode
```

2. Browser Tests:
```bash
cd frontend
npm run test:e2e      # Run browser tests in headless mode
npm run test:e2e:ui   # Run browser tests with UI for debugging
```

Browser tests use Playwright and will:
- Automatically start the development server
- Run tests against Chrome browser
- Generate HTML test reports
- Shut down the server when complete

#### API Tests
```bash
cd api
pytest
```

### Service Details

#### API
- Framework: FastAPI
- Default port: 8000
- Auto-reload enabled for development
- API documentation available at http://localhost:8000/docs

#### Frontend
- Framework: Next.js
- Default port: 3000
- Hot-reload enabled for development
