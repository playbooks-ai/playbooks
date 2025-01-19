#!/usr/bin/env python3
import subprocess
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


def revert_cache_changes(cache_dir):
    """Revert changes to cache files if they were staged."""
    try:
        # Get the relative path to cache dir from repo root
        repo_root = cache_dir.parent.parent.parent.parent.parent
        rel_cache_dir = cache_dir.relative_to(repo_root)
        
        # Reset any staged changes in the cache directory
        subprocess.run(
            ["git", "reset", "HEAD", f"{rel_cache_dir}/*"],
            cwd=repo_root,
            check=True,
            capture_output=True,
        )
        
        # Restore the files to their original state
        subprocess.run(
            ["git", "checkout", "--", f"{rel_cache_dir}/*"],
            cwd=repo_root,
            check=True,
            capture_output=True,
        )
        print("Reverted cache file changes")
    except subprocess.CalledProcessError as e:
        print(f"Failed to revert cache changes: {e.stderr.decode()}")
    except Exception as e:
        print(f"Error reverting cache changes: {e}")


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
        print("No new cache keys were added, reverting cache file changes")
        revert_cache_changes(cache_dir)
        sys.exit(0)  # Allow commit to proceed

    # Update the keys file with current keys
    keys_file.write_text("\n".join(sorted(current_keys)))
    print(f"Added {len(new_keys)} new cache keys")
    sys.exit(0)


if __name__ == "__main__":
    main()
