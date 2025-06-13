#!/bin/bash

# --- CONFIGURATION ---
ATLAS_URI="mongodb+srv://natnaelwondwoesn:123456nat1@cluster0.0gsof12.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
DB_NAME="taaft_db"
DUMP_DIR="atlas_backup"
MONGO_CONTAINER="taaft-backend-mongo-1"  # Adjust if your container name is different

# --- 1. Dump from Atlas ---
echo "Dumping data from Atlas..."
mongodump --uri="$ATLAS_URI" --db="$DB_NAME" --out="$DUMP_DIR"
if [ $? -ne 0 ]; then
  echo "mongodump failed! Check your Atlas URI and credentials."
  exit 1
fi

# --- 2. Copy dump into MongoDB container ---
echo "Copying dump into MongoDB container..."
docker cp "$DUMP_DIR/$DB_NAME" "$MONGO_CONTAINER":/tmp/
if [ $? -ne 0 ]; then
  echo "docker cp failed! Check your container name."
  exit 1
fi

# --- 3. Restore inside the container ---
echo "Restoring data inside MongoDB container..."
docker exec -it "$MONGO_CONTAINER" mongorestore --drop --db "$DB_NAME" /tmp/$DB_NAME
if [ $? -ne 0 ]; then
  echo "mongorestore failed inside the container!"
  exit 1
fi

echo "Migration complete! You can now check your MongoDB data." 