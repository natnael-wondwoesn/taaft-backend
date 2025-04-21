#!/usr/bin/env python3
"""
Combine separate Swagger YAML files into a single complete Swagger documentation file.
"""
import os
import yaml


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


def main():
    print("Starting Swagger combination process...")

    # Read the base Swagger file
    base_swagger = read_yaml("swagger.yaml")

    # Initialize paths and schemas
    if "paths" not in base_swagger:
        base_swagger["paths"] = {}
        print("Initialized empty paths dictionary")
    elif base_swagger["paths"] is None:
        base_swagger["paths"] = {}
        print("Paths was None, initialized empty dictionary")

    if "components" not in base_swagger:
        base_swagger["components"] = {}
        print("Initialized empty components dictionary")

    if "schemas" not in base_swagger["components"]:
        base_swagger["components"]["schemas"] = {}
        print("Initialized empty schemas dictionary")

    # List of all module Swagger files
    module_files = [
        "swagger_auth.yaml",
        "swagger_chat.yaml",
        "swagger_search.yaml",
        "swagger_tools.yaml",
        "swagger_queue.yaml",
    ]

    # Process each module file
    for module_file in module_files:
        print(f"Processing {module_file}...")
        if not os.path.exists(module_file):
            print(f"Warning: {module_file} does not exist. Skipping.")
            continue

        # Read the module file
        module_swagger = read_yaml(module_file)

        # Merge paths
        if "paths" in module_swagger and module_swagger["paths"]:
            print(f"Merging paths from {module_file}")
            paths_before = (
                len(base_swagger["paths"])
                if isinstance(base_swagger["paths"], dict)
                else 0
            )
            base_swagger["paths"].update(module_swagger["paths"])
            paths_after = (
                len(base_swagger["paths"])
                if isinstance(base_swagger["paths"], dict)
                else 0
            )
            print(f"  Added {paths_after - paths_before} paths")
        else:
            print(f"No paths found in {module_file}")

        # Merge components.schemas
        if "components" in module_swagger and "schemas" in module_swagger["components"]:
            if module_swagger["components"]["schemas"]:
                print(f"Merging schemas from {module_file}")
                schemas_before = (
                    len(base_swagger["components"]["schemas"])
                    if isinstance(base_swagger["components"]["schemas"], dict)
                    else 0
                )
                base_swagger["components"]["schemas"].update(
                    module_swagger["components"]["schemas"]
                )
                schemas_after = (
                    len(base_swagger["components"]["schemas"])
                    if isinstance(base_swagger["components"]["schemas"], dict)
                    else 0
                )
                print(f"  Added {schemas_after - schemas_before} schemas")
            else:
                print(f"Empty schemas in {module_file}")
        else:
            print(f"No schemas found in {module_file}")

    # Clean up any placeholder comments in the paths
    if isinstance(base_swagger["paths"], dict):
        print("Checking for placeholder comments...")
        placeholder_paths = []
        for path_key, path_value in base_swagger["paths"].items():
            if (
                path_key == "# Placeholder for paths - will be filled in separate files"
                or path_key == "#/paths"
            ):
                placeholder_paths.append(path_key)
            elif isinstance(path_value, str) and "# Placeholder" in path_value:
                placeholder_paths.append(path_key)

        # Remove any found placeholders
        if placeholder_paths:
            print(f"Found {len(placeholder_paths)} placeholder items to remove")
            for path_key in placeholder_paths:
                base_swagger["paths"].pop(path_key, None)
        else:
            print("No placeholder comments found")

    # Write the combined Swagger to a new file
    try:
        with open("combined_swagger.yaml", "w") as file:
            yaml.dump(base_swagger, file, sort_keys=False)
        print("Combined Swagger documentation generated: combined_swagger.yaml")
    except Exception as e:
        print(f"Error writing to combined_swagger.yaml: {e}")


if __name__ == "__main__":
    main()
