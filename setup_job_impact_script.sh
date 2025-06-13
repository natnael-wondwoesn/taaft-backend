#!/bin/bash
# Setup script to create app/scripts directory in the container and copy the script

echo "Setting up job impact tool count script in the container..."

# Get container name
CONTAINER_NAME=$(docker ps | grep taaft-backend-app | awk '{print $NF}')

if [ -z "$CONTAINER_NAME" ]; then
    echo "Error: Could not find taaft-backend-app container"
    exit 1
fi

echo "Using container: $CONTAINER_NAME"

# Create app/scripts directory in container if it doesn't exist
echo "Creating app/scripts directory in container..."
docker exec $CONTAINER_NAME bash -c "mkdir -p /app/app/scripts"

if [ $? -ne 0 ]; then
    echo "Error: Failed to create directory in container"
    exit 1
fi

# Copy script to the container
echo "Copying script to container..."
docker cp app/scripts/calculate_job_impact_tool_counts.py $CONTAINER_NAME:/app/app/scripts/

if [ $? -ne 0 ]; then
    echo "Error: Failed to copy script to container"
    exit 1
fi

# Make the script executable
echo "Making script executable in container..."
docker exec $CONTAINER_NAME bash -c "chmod +x /app/app/scripts/calculate_job_impact_tool_counts.py"

if [ $? -ne 0 ]; then
    echo "Error: Failed to make script executable"
    exit 1
fi

echo "Setup completed successfully!"
echo "You can now run ./update_job_impact_counts.sh to run the script." 