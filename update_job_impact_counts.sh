#!/bin/bash
# Script to run job impact tool count calculation within the Docker environment

echo "Starting job impact tool count calculation..."

# Default values
FORCE_UPDATE=${FORCE_UPDATE:-false}
MIN_TOOL_COUNT=${MIN_TOOL_COUNT:-5}
BATCH_SIZE=${BATCH_SIZE:-50}

# Get container name
CONTAINER_NAME=$(docker ps | grep taaft-backend-app | awk '{print $NF}')

if [ -z "$CONTAINER_NAME" ]; then
    echo "Error: Could not find taaft-backend-app container"
    exit 1
fi

echo "Using container: $CONTAINER_NAME"
echo "Force update: $FORCE_UPDATE"
echo "Minimum tool count: $MIN_TOOL_COUNT"
echo "Batch size: $BATCH_SIZE"

# Check if the script exists in the container
echo "Checking if script exists in container..."
SCRIPT_EXISTS=$(docker exec $CONTAINER_NAME bash -c "[ -f /app/app/scripts/calculate_job_impact_tool_counts.py ] && echo 'yes' || echo 'no'")

if [ "$SCRIPT_EXISTS" != "yes" ]; then
    echo "Error: Script not found in container. Run ./setup_job_impact_script.sh first."
    exit 1
fi

echo "Script found in container."

# Run inside the Docker container with environment variables
echo "Running script in container..."
docker exec $CONTAINER_NAME bash -c "cd /app && FORCE_UPDATE=$FORCE_UPDATE MIN_TOOL_COUNT=$MIN_TOOL_COUNT BATCH_SIZE=$BATCH_SIZE python app/scripts/calculate_job_impact_tool_counts.py"

# Check if the command was successful
if [ $? -eq 0 ]; then
    echo "Job impact tool count calculation completed successfully."
    exit 0
else
    echo "Job impact tool count calculation failed."
    exit 1
fi 