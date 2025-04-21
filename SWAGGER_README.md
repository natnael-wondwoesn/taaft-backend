# TAAFT API Documentation

This directory contains the OpenAPI/Swagger documentation for the TAAFT (Tools Analysis and Functionality Testing) backend API.

## Documentation Structure

The API documentation is split into several YAML files:

- `swagger.yaml`: Base document with general information
- `swagger_auth.yaml`: Authentication endpoints
- `swagger_chat.yaml`: Chat-related endpoints
- `swagger_search.yaml`: Search-related endpoints
- `swagger_tools.yaml`: Tools management endpoints
- `swagger_queue.yaml`: Sites queue endpoints

## Combining Documentation

To combine all the files into a single comprehensive Swagger document:

1. Ensure you have Python installed with the PyYAML package.
2. Install PyYAML if needed: `pip install pyyaml`
3. Run the combination script: `python combine_swagger.py`
4. This will generate a `combined_swagger.yaml` file that contains the complete API documentation.

## Sharing the Documentation

There are several ways to share the Swagger documentation:

### Option 1: Share the YAML File

You can directly share the `combined_swagger.yaml` file with others who can then:

- Import it into tools like Postman, Insomnia, or other API clients.
- Upload it to Swagger UI or Swagger Editor online.
- Host it on their own Swagger UI instance.

### Option 2: Swagger UI

You can host the documentation using Swagger UI:

1. Set up a simple web server with Swagger UI (a static website).
2. Configure Swagger UI to use your `combined_swagger.yaml` file.
3. Share the URL with others.

#### Quick Method Using Docker

```bash
docker run -p 8080:8080 -e SWAGGER_JSON=/foo/combined_swagger.yaml -v $(pwd):/foo swaggerapi/swagger-ui
```

Then visit http://localhost:8080 in your browser.

### Option 3: Swagger Editor Online

You can use the online Swagger Editor to view and share the documentation:

1. Go to https://editor.swagger.io/
2. Import your `combined_swagger.yaml` file using File > Import File
3. Share the URL with others (note: the URL will not save your changes permanently)

### Option 4: Generate Interactive Documentation

If you're using FastAPI for your application, you already have interactive documentation available:

1. Run your FastAPI app
2. Access the documentation at: `http://localhost:8000/docs` (Swagger UI) or `http://localhost:8000/redoc` (ReDoc)

## Integration with FastAPI

If you're using FastAPI, you can integrate this OpenAPI documentation with your application:

```python
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
import yaml

app = FastAPI()

def custom_openapi():
    with open("combined_swagger.yaml") as f:
        openapi_schema = yaml.safe_load(f)
    return openapi_schema

app.openapi = custom_openapi
```

## Exporting to Other Formats

The Swagger/OpenAPI documentation can be converted to other formats using tools like:

- **Swagger Codegen**: Generate client code in various languages
- **Swagger2Markup**: Convert to AsciiDoc or Markdown
- **ReDoc**: Generate attractive, responsive documentation

## API Documentation Best Practices

1. Keep documentation up-to-date with code changes
2. Provide examples for request/response payloads
3. Document all error responses
4. Use consistent naming conventions
5. Include authentication details 