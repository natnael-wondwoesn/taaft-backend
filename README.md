# TAAFT Backend

FastAPI-based backend for the TAAFT project with WebSocket support and MongoDB integration.

## Features

- FastAPI application with WebSocket support
- MongoDB integration for data storage
- Sites prioritized queue management system
- Dashboard API for sites queue

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

## API Endpoints

### Sites Queue API

- `POST /api/sites/`: Create a new site in the queue
- `GET /api/sites/n8n`: Provide site data for n8n automation
- `GET /api/sites/`: Get all sites with optional filtering (status, priority, category)
- `GET /api/sites/{site_id}`: Get a specific site by ID
- `PUT /api/sites/{site_id}`: Update a site in the queue
- `DELETE /api/sites/{site_id}`: Delete a site from the queue

#### n8n Data Feed Integration

The n8n endpoint (`/api/sites/n8n`) provides site data in a simple format for n8n automation:
```json
[
  {
    "_id": { "$oid": "680685e2856a3a9ff097944c" },
    "link": "https://theresanaiforthat.com/*",
    "category_id": "6806415d856a3a9ff0979444"
  }
]
```

Where each item in the array contains:
- `_id`: The MongoDB ObjectId in the format expected by n8n
- `link`: The URL of the site
- `category_id`: The category identifier for the site

The endpoint returns only active sites from the queue formatted for n8n integration.

### Sites Dashboard API

- `GET /api/sites/dashboard/stats`: Get overall statistics about the queue
- `GET /api/sites/dashboard/by-priority`: Get sites grouped by priority
- `GET /api/sites/dashboard/by-category`: Get sites summarized by category
- `GET /api/sites/dashboard/recent`: Get recently added sites

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