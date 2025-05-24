#!/usr/bin/env python3
"""
Test script to verify datetime handling and comparison.
"""

from datetime import datetime
from bson import ObjectId


def print_datetime_info(dt, name):
    """Print information about a datetime object."""
    print(f"{name}:")
    print(f"  Value: {dt}")
    print(f"  Type: {type(dt)}")
    print(f"  tzinfo: {dt.tzinfo}")
    print()


# Create various datetime objects
now = datetime.now()
print_datetime_info(now, "datetime.now()")

# Create an ObjectId and get its generation time
obj_id = ObjectId()
gen_time = obj_id.generation_time
print_datetime_info(gen_time, "ObjectId generation_time")

# Make the generation time offset-naive
naive_gen_time = gen_time.replace(tzinfo=None)
print_datetime_info(naive_gen_time, "Offset-naive generation_time")

# Try to compare them
print("Comparison tests:")
try:
    result = now < gen_time
    print(f"now < gen_time: {result}")
except TypeError as e:
    print(f"Error comparing now < gen_time: {e}")

try:
    result = now < naive_gen_time
    print(f"now < naive_gen_time: {result}")
except TypeError as e:
    print(f"Error comparing now < naive_gen_time: {e}")

# Test ISO format parsing
iso_formats = [
    "2023-05-16T12:34:56Z",
    "2023-05-16T12:34:56.789Z",
    "2023-05-16T12:34:56+00:00",
]

print("\nParsing ISO format strings:")
for iso_str in iso_formats:
    print(f"\nTrying to parse: {iso_str}")

    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        print_datetime_info(dt, "Parsed with fromisoformat")

        # Make it offset-naive
        naive_dt = dt.replace(tzinfo=None)
        print_datetime_info(naive_dt, "After making offset-naive")

        # Compare with now
        try:
            result = now < naive_dt
            print(f"now < naive_dt: {result}")
        except TypeError as e:
            print(f"Error comparing now < naive_dt: {e}")

    except ValueError as e:
        print(f"Error parsing with fromisoformat: {e}")

        try:
            if "Z" in iso_str:
                if "." in iso_str:
                    dt = datetime.strptime(iso_str, "%Y-%m-%dT%H:%M:%S.%fZ")
                else:
                    dt = datetime.strptime(iso_str, "%Y-%m-%dT%H:%M:%SZ")
                print_datetime_info(dt, "Parsed with strptime")
            else:
                print("Not attempting strptime for this format")
        except ValueError as e2:
            print(f"Error parsing with strptime: {e2}")
