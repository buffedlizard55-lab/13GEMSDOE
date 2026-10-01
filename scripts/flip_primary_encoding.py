#!/usr/bin/env python3
"""Retired historical migration: safe inspection only. See correction register13.

Original migration implementation is preserved in Git history. Never mutates
current downloads or schema2 roles; --dry-run inspects the existing manifest.
"""
from retired_migration import main

if __name__ == '__main__':
    raise SystemExit(main())
