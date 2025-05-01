#!/usr/bin/env python3
"""
Combine separate Swagger YAML files into a single complete Swagger documentation file.
"""
import os
import yaml
import copy


def read_yaml(file_path):
    """Read YAML file and return its contents as a dictionary."""
    try:
        with open(file_path, "r") as file:
            content = yaml.safe_load(file)
            print(
                f"Read file {file_path}: {'Success' if content else 'Empty or error'}"
            )
            return content or {}
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return {}


def combine_swagger_files():
    """Combine multiple Swagger YAML files into a single file."""
    # Files to combine
    files = [
        "swagger.yaml",  # Base file with OpenAPI info
        "swagger_auth.yaml",  # Authentication related endpoints
        "swagger_tools.yaml",  # Tool-related endpoints
        "swagger_search.yaml",  # Search-related endpoints
        "swagger_glossary.yaml",  # Glossary-related endpoints
        "swagger_queue.yaml",  # Site queue related endpoints
        "swagger_chat.yaml",  # Chat related endpoints
        "swagger_categories.yaml",  # Categories related endpoints
        "swagger_terms.yaml",  # Term definition related endpoints
        "swagger_blog.yaml",  # Blog related endpoints with glossary linking
    ]

    # Read the base file first
    with open(files[0], "r") as f:
        combined = yaml.safe_load(f)

    # Initialize paths and components if they don't exist
    if "paths" not in combined or combined["paths"] is None:
        combined["paths"] = {}
    if "components" not in combined or combined["components"] is None:
        combined["components"] = {}
    if (
        "schemas" not in combined["components"]
        or combined["components"]["schemas"] is None
    ):
        combined["components"]["schemas"] = {}

    # Process each additional file
    for file_path in files[1:]:
        if not os.path.exists(file_path):
            print(f"Warning: File {file_path} does not exist. Skipping.")
            continue

        with open(file_path, "r") as f:
            try:
                data = yaml.safe_load(f)

                # Only include the file's content if it has valid content
                if data:
                    # Add tags if they exist
                    if "tags" in data and data["tags"]:
                        if "tags" not in combined or combined["tags"] is None:
                            combined["tags"] = []

                        # Create a set of existing tag names to avoid duplicates
                        existing_tags = {tag["name"] for tag in combined["tags"]}

                        # Add only tags that don't already exist
                        for tag in data["tags"]:
                            if tag["name"] not in existing_tags:
                                combined["tags"].append(tag)
                                existing_tags.add(tag["name"])

                    # Add paths if they exist
                    if "paths" in data and data["paths"]:
                        for path, path_info in data["paths"].items():
                            if path in combined["paths"]:
                                # If path exists, merge the HTTP methods
                                for method, method_info in path_info.items():
                                    if method in combined["paths"][path]:
                                        print(
                                            f"Warning: Duplicate endpoint {method.upper()} {path} in {file_path}. Using the new definition."
                                        )
                                    combined["paths"][path][method] = method_info
                            else:
                                # If path doesn't exist, add it
                                combined["paths"][path] = path_info

                    # Add components if they exist
                    if "components" in data and data["components"]:
                        for comp_type, comp_items in data["components"].items():
                            if (
                                comp_type not in combined["components"]
                                or combined["components"][comp_type] is None
                            ):
                                combined["components"][comp_type] = {}

                            # Merge the component items
                            for item_name, item_info in comp_items.items():
                                if item_name in combined["components"][comp_type]:
                                    print(
                                        f"Warning: Duplicate component {comp_type}.{item_name} in {file_path}. Using the new definition."
                                    )
                                combined["components"][comp_type][item_name] = item_info
            except yaml.YAMLError as e:
                print(f"Error parsing {file_path}: {e}")
                continue

    # Write combined YAML
    with open("combined_swagger.yaml", "w") as f:
        yaml.dump(combined, f, default_flow_style=False, sort_keys=False)

    print("Combined Swagger file created: combined_swagger.yaml")


if __name__ == "__main__":
    combine_swagger_files()
