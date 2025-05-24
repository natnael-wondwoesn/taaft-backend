#!/usr/bin/env python3
"""
Test script for job impact indexing in Algolia
Tests the prepare_algolia_object function with a sample job impact record
"""

import json
from dotenv import load_dotenv
from app.algolia.migrater.tools_job_impacts_to_algolia import prepare_algolia_object

# Load environment variables
load_dotenv()

# Sample job impact record based on the provided example
sample_job_impact = {
    "_id": "682df6cb314b48ef94280110",
    "detail_page_link": "https://theresanaiforthat.com/job/veterinarian",
    "job_title": "Veterinarian",
    "ai_impact_score": "5%",
    "description": "A veterinarian is a licensed medical professional who specializes in caring for animals. They conduct physical exams, diagnose illnesses and injuries, prescribe medications, and perform surgeries.",
    "ai_impact_summary": "Veterinarians play a crucial role in animal healthcare, and AI can assist them significantly in various tasks related to diagnostics, treatment, and pet care.",
    "detailed_analysis": "AI technologies are transforming the veterinarian field by introducing tools that assist in diagnosing animal health issues, providing treatment recommendations, and enhancing overall efficiency in veterinary practices.",
    "job_category": "Veterinary",
    "tasks": [
        {
            "name": "Q&A about pets",
            "task_ai_impact_score": "100%",
            "tools": [
                {
                    "tool_name": "Ruru",
                    "tool_logo_url": "https://media.theresanaiforthat.com/assets/favicon-large.png",
                    "tool_link": "https://theresanaiforthat.com/ai/ruru/",
                }
            ],
        },
        {
            "name": "Pet health",
            "task_ai_impact_score": "100%",
            "tools": [
                {
                    "tool_name": "TTcare",
                    "tool_logo_url": "https://media.theresanaiforthat.com/assets/favicon-large.png",
                    "tool_link": "https://theresanaiforthat.com/ai/ttcare/",
                },
                {
                    "tool_name": "Pet Genius",
                    "tool_logo_url": "https://media.theresanaiforthat.com/assets/favicon-large.png",
                    "tool_link": "https://theresanaiforthat.com/ai/pet-genius/",
                },
            ],
        },
    ],
}


def main():
    """Test the job impact record transformation for Algolia"""
    print("Testing job impact transformation for Algolia...\n")

    # Transform the sample job impact record
    algolia_object = prepare_algolia_object(sample_job_impact)

    # Print the result
    print("Original Job Impact Record:")
    print("--------------------------")
    print(json.dumps(sample_job_impact, indent=2))

    print("\nTransformed Algolia Object:")
    print("-------------------------")
    print(json.dumps(algolia_object, indent=2))

    # Verify the transformation
    print("\nVerification:")
    print("------------")
    print(f"objectID: {algolia_object.get('objectID')}")
    print(f"job_title: {algolia_object.get('job_title')}")
    print(f"task_names: {algolia_object.get('task_names')}")
    print(f"tool_names: {algolia_object.get('tool_names')}")
    print(f"numeric_impact_score: {algolia_object.get('numeric_impact_score')}")
    print(f"keywords: {algolia_object.get('keywords')}")

    # Verify search properties
    if "task_names" in algolia_object and "tool_names" in algolia_object:
        print("\n✅ Successfully generated task_names and tool_names for faceting")
    else:
        print("\n❌ Failed to generate task_names and tool_names")

    if "numeric_impact_score" in algolia_object:
        print("✅ Successfully generated numeric_impact_score for sorting")
    else:
        print("❌ Failed to generate numeric_impact_score")


if __name__ == "__main__":
    main()
