# Algolia Migration Scripts

This directory contains scripts for migrating data from MongoDB to Algolia search indices.

## Available Scripts

### 1. `tools_to_algolia.py`

Migrates the MongoDB `tools` collection to an Algolia index for efficient searching.

#### Features:
- Connects to MongoDB and retrieves all tools
- Configures an Algolia index with optimized search settings
- Transforms MongoDB documents to Algolia-friendly format
- Replaces the entire Algolia index with the latest data
- Uses Algolia v4 client syntax for improved performance

#### Prerequisites:
- Python 3.6+
- Required packages: `algoliasearch>=4.0.0`, `pymongo`, `python-dotenv`
- Environment variables properly configured in `.env` file

#### Environment Variables:
Make sure the following variables are set in your `.env` file:
```
MONGODB_URL=your_mongodb_connection_string
ALGOLIA_APP_ID=your_algolia_app_id
ALGOLIA_ADMIN_KEY=your_algolia_admin_key
ALGOLIA_TOOLS_INDEX=taaft_tools
```

#### Usage:
```bash
# Navigate to the project root
cd /path/to/project

# Run the script
python -m app.algolia.migrater.tools_to_algolia

# Or use the convenience script
python migrate_tools_to_algolia.py
```

### 2. `Algolia_index_load.py`

Example script for migrating the sample AirBnB dataset from MongoDB to Algolia (uses v3 client).

## Running a Migration

1. Ensure your `.env` file has all required credentials
2. Run the appropriate migration script
3. Verify data in the Algolia dashboard (https://www.algolia.com/apps/dashboard)

## Error Handling

If you encounter issues:
- Check MongoDB connection
- Verify Algolia credentials
- Look for any errors in the console output
- Ensure MongoDB collection contains data

## Customizing the Migration

To customize what data is migrated to Algolia:
1. Modify the `prepare_algolia_object()` function
2. Adjust the `configure_algolia_index()` settings
3. Update the attributes included in the migration

## Algolia v4 Client Notes

The `tools_to_algolia.py` script uses the Algolia v4 client syntax:

```python
# Initialize the client
from algoliasearch.search import SearchClientSync
client = SearchClientSync("ALGOLIA_APP_ID", "ALGOLIA_API_KEY")

# Search an index
client.search_single_index("INDEX_NAME", {"query": "SEARCH_TERM"})

# Save objects
client.save_objects("INDEX_NAME", [object1, object2], {"wait_for_task": True})

# Configure index
client.set_settings("INDEX_NAME", settings_dict)
``` 