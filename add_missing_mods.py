#!/usr/bin/env python3
"""
Script to process missing mods and attempt to add them using packwiz.
Successfully added mods are removed from the missing-mods file.

Usage:
  python add_missing_mods.py 1.21.10          # Provide version as argument
  echo "1.21.10" | python add_missing_mods.py # Pipe version from stdin
  python add_missing_mods.py                  # Interactive mode
"""

import subprocess
import sys
import os


def get_version():
    """Get version from command line args, stdin, or user input."""
    # Try command line argument first
    if len(sys.argv) > 1:
        return sys.argv[1].strip()

    # Try stdin (non-interactive)
    if not sys.stdin.isatty():
        return sys.stdin.read().strip()

    # Interactive input
    return input("Enter Minecraft version (e.g., 1.21.10): ").strip()


def read_missing_mods(missing_mods_file):
    """Read mod IDs from the missing-mods file."""
    if not os.path.exists(missing_mods_file):
        return []

    with open(missing_mods_file, "r") as f:
        return [line.strip() for line in f if line.strip()]


def add_mod(mod_id, working_dir):
    """Try to add a mod using packwiz mr add. Returns True if successful, False otherwise."""
    try:
        result = subprocess.run(
            ["packwiz", "mr", "add", mod_id],
            cwd=working_dir,
            capture_output=True,
            text=True,
            check=True,
        )
        print(f"✓ Successfully added: {mod_id}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ Failed to add: {mod_id}")
        if e.stderr:
            print(f"  Error: {e.stderr.strip()}")
        return False
    except FileNotFoundError:
        print("✗ Error: packwiz command not found. Make sure it's installed.")
        return False


def write_missing_mods(missing_mods_file, mod_ids):
    """Write the remaining mod IDs back to the missing-mods file."""
    with open(missing_mods_file, "w") as f:
        for mod_id in mod_ids:
            f.write(f"{mod_id}\n")


def main():
    # Get version from user
    version = get_version()

    if not version:
        print("Error: No version provided.")
        sys.exit(1)

    # Setup paths based on version
    working_dir = f"versions/active/{version}"
    missing_mods_file = os.path.join(working_dir, "missing-mods")

    # Check if directory exists
    if not os.path.exists(working_dir):
        print(f"Error: Directory '{working_dir}' does not exist.")
        sys.exit(1)

    print(f"Processing version: {version}")
    print(f"Working directory: {working_dir}\n")

    # Read all mod IDs
    mod_ids = read_missing_mods(missing_mods_file)
    print(f"Found {len(mod_ids)} mods to process\n")

    if not mod_ids:
        print("No mods to process.")
        return

    # Track which mods still need to be added
    still_missing = []

    # Try to add each mod
    for mod_id in mod_ids:
        if not add_mod(mod_id, working_dir):
            still_missing.append(mod_id)
        print()  # Empty line between mods

    # Update the missing-mods file with only the failed ones
    write_missing_mods(missing_mods_file, still_missing)

    # Summary
    print("=" * 40)
    print("SUMMARY")
    print("=" * 40)
    print(f"Total mods processed: {len(mod_ids)}")
    print(f"Successfully added: {len(mod_ids) - len(still_missing)}")
    print(f"Still missing: {len(still_missing)}")

    if still_missing:
        print("\nMods that still need to be added:")
        for mod_id in still_missing:
            print(f"  - {mod_id}")


if __name__ == "__main__":
    main()
