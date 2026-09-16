"""Data layer: the genre-agnostic ``GenrePack`` contract and the packs built on it.

Nothing under ``nodes/`` or ``engine/`` may import a concrete pack module from
here. Node classes are *generated* from a pack that the repo-root
``__init__.py`` hands them, which is the seam that makes a second genre cost one
data module and two registration lines. ``tests/test_genre_contract.py`` pins it.
"""
