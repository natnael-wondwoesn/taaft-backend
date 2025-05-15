# Database Scripts

This directory contains utility scripts for database operations.

## Convert Unique IDs Script

The `convert_unique_ids.py` script converts tool unique IDs with slashes to hyphens in the database.
For example, "deepseek-ai/DeepSeek-V3" becomes "deepseek-ai-DeepSeek-V3".

### Why This Script?

FastAPI's path parameters don't handle slashes in path segments by default. While we've updated the routes to use the `:path` path converter, it's also good practice to avoid slashes in IDs to prevent potential issues with URL parsing and routing.

### What This Script Does

1. Finds all tools with slashes in their unique_id
2. Converts slashes to hyphens
3. Updates the tool document in the database
4. Updates references to these unique_ids in:
   - Favorites collection
   - Shares collection
   - Users' saved_tools arrays

### How to Run

From the project root directory:

```bash
# Make sure the script is executable
chmod +x app/scripts/convert_unique_ids.py

# Run the script
python app/scripts/convert_unique_ids.py
```

### Output

The script logs its progress to the console and application logs, showing:
- Which unique_ids are being converted
- How many tools, favorites, shares, and user references were updated
- Any errors that occurred during the process 