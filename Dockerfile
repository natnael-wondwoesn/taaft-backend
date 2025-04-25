FROM python:3.12.3

WORKDIR /app

# Install dependencies
COPY requirements.txt .
# Uninstall standalone bson package if it exists and then install requirements
RUN pip install --no-cache-dir -r requirements.txt && \
    pip uninstall -y bson && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir aiohttp

# Copy application code
COPY app/ ./app/

# Copy static directory with its contents
COPY static/ ./static/

# Create logs directory
RUN mkdir -p logs

# Expose the port the app runs on
EXPOSE 8000

# Command to run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"] 