def get_playbooks_version() -> str:
    """Get the version of the playbooks package."""
    try:
        from importlib.metadata import version

        return version("playbooks")
    except ImportError:
        # Fallback for Python < 3.8
        try:
            from importlib_metadata import version

            return version("playbooks")
        except ImportError:
            return "unknown"
    except Exception:
        return "unknown"
