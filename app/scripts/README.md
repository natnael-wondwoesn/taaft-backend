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
# On Unix/Linux/Mac (make executable first)
chmod +x app/scripts/convert_unique_ids.py
python app/scripts/convert_unique_ids.py

# On Windows
python app/scripts/convert_unique_ids.py
```

### Output

The script logs its progress to the console and application logs, showing:
- Which unique_ids are being converted
- How many tools, favorites, shares, and user references were updated
- Any errors that occurred during the process

## Update Category Counts Script

The `update_category_counts.py` script updates the count field in the categories collection to reflect the actual number of tools in each category.

### Why This Script?

Category counts can become outdated as tools are added, removed, or modified. This script ensures that the counts displayed in the UI are accurate.

### What This Script Does

1. Retrieves all categories from the database
2. For each category, counts the number of tools that belong to it
3. Updates the count field in the categories collection

### How to Run

From the project root directory:

```bash
# On Unix/Linux/Mac (make executable first)
chmod +x app/scripts/update_category_counts.py
python app/scripts/update_category_counts.py

# On Windows
python app/scripts/update_category_counts.py
```

### Setting Up as a Cron Job

To run this script automatically on a schedule:

#### On Unix/Linux/Mac

Add this to your crontab (run `crontab -e`):

```
# Run daily at 2 AM
0 2 * * * /path/to/python /path/to/app/scripts/update_category_counts.py
```

#### On Windows

Create a scheduled task:

1. Open Task Scheduler
2. Create a Basic Task
3. Set the trigger (e.g., daily at 2 AM)
4. Action: Start a program
5. Program/script: `python`
6. Add arguments: `C:\path\to\app\scripts\update_category_counts.py`

### Output

The script logs its progress to the console and a dedicated log file (`category_counts_update.log`), showing:
- How many categories were processed
- The updated count for each category
- Any errors that occurred during the process

## Remove Duplicate Tools Script

The `remove_duplicate_tools.py` script finds and removes duplicate tools from the database based on having the same name and link.

### Why This Script?

Duplicate tools can be created due to various reasons such as system errors, concurrent submissions, or data imports. These duplicates can confuse users and affect analytics. This script helps maintain data integrity by removing redundant entries.

### What This Script Does

1. Identifies tools that have the same name and link
2. For each set of duplicates, keeps the oldest tool (based on creation date) and removes the rest
3. Logs the removal process for auditing purposes

### How to Run

From the project root directory:

```bash
# On Unix/Linux/Mac (make executable first)
chmod +x app/scripts/remove_duplicate_tools.py
python app/scripts/remove_duplicate_tools.py

# On Windows
python app/scripts/remove_duplicate_tools.py
```

### Output

The script logs its progress to the console and a dedicated log file (`duplicate_tools_removal.log`), showing:
- Total number of tools in the database
- Number of duplicate sets found
- Which tools were kept and which were removed
- Total number of duplicates removed
- Any errors that occurred during the process 