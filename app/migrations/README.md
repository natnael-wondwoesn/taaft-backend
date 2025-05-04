# Database Migrations

This directory contains migration scripts for database schema changes.

## Available Migrations

### Migrate Shares from tool_id to tool_unique_id

The `migrate_shares.py` script updates the shares collection to use `tool_unique_id` instead of `tool_id`.

To run this migration:

```bash
python migrate_shares.py
```

This migration:
1. Identifies shares that have `tool_id` but no `tool_unique_id`
2. Looks up the corresponding tool to get its `unique_id`
3. Updates each share record with the `tool_unique_id` and removes the old `tool_id` field
4. Updates database indexes (drops the `tool_id` index and creates a `tool_unique_id` index if needed)

After running this migration, all shares should use `tool_unique_id` for consistency with the favorites implementation. 