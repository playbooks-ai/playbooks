#!/usr/bin/env python3
import sys
from pathlib import Path
from diskcache import Cache


def get_cache_keys(cache_dir):
    """Get all cache keys from the LiteLLM cache."""
    if not cache_dir.exists():
        print(f"Cache directory not found at: {cache_dir}")
        return set()

    # Open the cache directory using diskcache
    cache = Cache(str(cache_dir))
    try:
        # Get all keys from the cache
        keys = set(cache.iterkeys())
        print(f"Found {len(keys)} cache keys: {keys}")
        return keys
    finally:
        cache.close()


def main():
    # Get absolute path to cache directory
    repo_root = Path(__file__).parent.parent
    cache_dir = repo_root / "python" / "packages" / "playbooks" / ".litellm_cache"
    print(f"Looking for cache in: {cache_dir}")

    # Path to store the previous keys
    keys_file = cache_dir / ".cache_keys"

    # Get current cache keys
    current_keys = get_cache_keys(cache_dir)

    # If keys file doesn't exist, create it with current keys
    if not keys_file.exists():
        keys_file.write_text("\n".join(sorted(current_keys)))
        print("Created initial cache keys file")
        sys.exit(0)

    # Read previous keys
    previous_keys = set(keys_file.read_text().splitlines())
    print(f"Previous {len(previous_keys)} cache keys: {previous_keys}")

    # Check if any new keys were added
    new_keys = current_keys - previous_keys
    if not new_keys:
        print("No new cache keys were added")
        sys.exit(1)  # Exit with error to prevent commit

    # Update the keys file with current keys
    keys_file.write_text("\n".join(sorted(current_keys)))
    print(f"Added {len(new_keys)} new cache keys")
    sys.exit(0)


if __name__ == "__main__":
    main()
