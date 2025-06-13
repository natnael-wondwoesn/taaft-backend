# Job Impact Tool Count Calculator

This script calculates and saves tool counts for all job impacts in the database. Instead of calculating tool counts on-demand, this script pre-calculates them and stores them in the database for efficient retrieval.

## Purpose

The purpose of this script is to:
1. Retrieve all job impacts from the database
2. Calculate the total tool count for each job impact directly from the tools collection
3. Save the tool count in the `job_impact_tool_counts` collection
4. Store detailed task-level counts in the `job_impact_task_counts` collection
5. Provide detailed logging of the process
6. Ensure no job impact has a zero tool count (using a configurable minimum)
7. Process job impacts in batches for better efficiency

## Usage

### Running the Script

```bash
# Run with default settings
python app/scripts/calculate_job_impact_tool_counts.py

# Run with environment variables to configure
FORCE_UPDATE=true MIN_TOOL_COUNT=10 BATCH_SIZE=20 python app/scripts/calculate_job_impact_tool_counts.py

# Alternatively, use the wrapper script with optional environment variables
./update_job_impact_counts.sh
# OR with custom settings:
FORCE_UPDATE=true MIN_TOOL_COUNT=10 BATCH_SIZE=20 ./update_job_impact_counts.sh
```

### Environment Variables

- `FORCE_UPDATE`: Whether to force update existing tool counts (default: false)
- `MIN_TOOL_COUNT`: Minimum tool count to set for job impacts with no tools (default: 5)
- `BATCH_SIZE`: Number of job impacts to process in each batch (default: 50)

### Scheduling

It's recommended to set up a cron job to run this script periodically to ensure that tool counts are up-to-date.

Example cron entry (run daily at 2 AM):

```
0 2 * * * cd /path/to/taaft-backend && ./update_job_impact_counts.sh >> /path/to/logs/job_impact_tool_counts_cron.log 2>&1
```

## Implementation Details

### Efficient Database Access

The script now directly queries the tools collection to count related tools for each task, rather than making API requests. This significantly improves performance and reliability.

### Batch Processing

To avoid overwhelming the database, the script processes job impacts in configurable batches, with concurrency within each batch.

### Minimum Tool Count

To prevent zero tool counts in the UI, the script sets a configurable minimum tool count for any job impact that would otherwise have zero.

### Detailed Task Counts

Task-level counts are now stored in a separate collection (`job_impact_task_counts`), allowing for more detailed analysis.

## Database Collections

The script interacts with the following collections:

1. `job_impacts`: Source collection containing all job impacts and their tasks
2. `tools`: Collection containing tools with their related tasks
3. `job_impact_tool_counts`: Target collection for storing job impact total tool counts
4. `job_impact_task_counts`: Target collection for storing detailed task-level counts

## Logging

The script generates detailed logs in `app/scripts/job_impact_tool_counts.log` and also outputs to standard output. Logs include:

- Start and end times
- Total number of job impacts processed
- Batch processing details
- Number of successful, failed, and skipped job impacts
- Detailed information for each job impact processed
- Task-level tool counts

## API Integration

The script works in tandem with the following endpoints:

1. `/api/jobs/by-title`: Retrieves job impact by title with tool count
2. `/api/jobs/tool-counts/{job_title}`: Retrieves tool count for a specific job impact
3. `/api/jobs/tool-counts`: Lists all job impact tool counts

These endpoints now efficiently retrieve pre-calculated tool counts from the database instead of calculating them on each request. 