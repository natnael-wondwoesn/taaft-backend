# TAAFT Backend

FastAPI-based backend for the TAAFT project with WebSocket support and MongoDB integration.

## Features

- FastAPI application with WebSocket support
- MongoDB integration for data storage
- Source queue management system
- Dashboard API

## Running with Docker

### Prerequisites

- Docker and Docker Compose installed

### Setup

1. Clone the repository
2. Create a `.env` file based on `.env.example`
3. Build and start the containers:

```bash
docker-compose up -d
```

This will:
- Build the FastAPI application
- Start a MongoDB instance
- Connect the application to MongoDB
- Expose the API on port 8000

### Accessing the API

- API Documentation: http://localhost:8000/docs
- API Base URL: http://localhost:8000
- WebSocket endpoint: ws://localhost:8000/ws

## Development

To run the application locally without Docker:

1. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run the application:
```bash
uvicorn app.main:app --reload
``` 