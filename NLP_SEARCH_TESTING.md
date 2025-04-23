# NLP-Powered Algolia Search Testing

This directory contains scripts to test the NLP-powered Algolia search functionality. These tools allow you to test the natural language query processing and search capabilities from the command line.

## Pre-requisites

- Python 3.6+
- OpenAI API key (optional for mock mode)
- Algolia credentials (optional for mock mode)

## Available Tools

### 1. Single Query Testing (`search_test.py`)

Test a single natural language query:

```bash
# On Linux/Mac
python search_test.py "I need a free tool for writing blog posts" --mock

# On Windows
search_test.bat "I need a free tool for writing blog posts" --mock
```

Options:
- `--mock`: Use mock data instead of real Algolia search
- `--process-only`: Only process the query, don't perform the search
- `--openai-key KEY`: OpenAI API key to use for processing
- `--page NUMBER`: Page number (default: 1)
- `--per-page NUMBER`: Results per page (default: 10)

### 2. Batch Query Testing (`batch_search_test.py`)

Test multiple queries from a file:

```bash
python batch_search_test.py test_queries.txt --output results.json --mock
```

Options:
- `--output`, `-o`: Output file to save results (JSON)
- `--mock`: Generate mock search results
- `--openai-key KEY`: OpenAI API key to use for processing

### 3. Test Queries File (`test_queries.txt`)

The `test_queries.txt` file contains sample natural language queries for testing. You can add your own queries to this file, one per line. Lines starting with `#` are treated as comments and ignored.

## Output Format

### Single Query Output

For a single query, the output includes:
1. Processed query information (search terms, categories, pricing types, etc.)
2. Search results (either real from Algolia or mock data)

### Batch Query Output (JSON)

For batch queries, the output JSON contains:
1. Original query
2. Processed query information
3. Mock results (if --mock is used)
4. Timestamp

## Troubleshooting

### OpenAI API Issues

If you encounter OpenAI API errors, you have several options:

1. Provide your API key directly:
   ```bash
   python search_test.py "your query" --openai-key YOUR_API_KEY
   ```

2. Set the OPENAI_API_KEY environment variable:
   ```bash
   # On Linux/Mac
   export OPENAI_API_KEY=your-api-key-here
   
   # On Windows
   set OPENAI_API_KEY=your-api-key-here
   ```

3. Use mock mode to skip OpenAI API calls:
   ```bash
   python search_test.py "your query" --mock
   ```

4. Use process-only mode with mock data for testing query processing without search:
   ```bash
   python search_test.py "your query" --process-only --mock
   ```

Note: The scripts include fallback keyword extraction that will work even if OpenAI API calls fail.

### Mock Mode

If Algolia isn't configured or you don't want to use actual search:

```bash
python search_test.py "your query" --mock
```

### Query Processing Only

To only test the NLP processing without search:

```bash
python search_test.py "your query" --process-only
```

## Examples

1. Test a single query with mock data:
   ```bash
   python search_test.py "I need a free tool for writing blog posts" --mock
   ```

2. Process a query without searching:
   ```bash
   python search_test.py "Show me AI image generators" --process-only
   ```

3. Test multiple queries and save results:
   ```bash
   python batch_search_test.py test_queries.txt --output results.json --mock
   ```

4. Use your OpenAI API key:
   ```bash
   python search_test.py "Need coding assistant for Python" --openai-key sk-your-key-here
   ``` 