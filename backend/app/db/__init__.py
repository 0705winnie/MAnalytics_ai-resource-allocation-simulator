"""Database infrastructure package.

Import engine and session objects explicitly from ``app.db.session`` so modules
that only need declarative metadata do not require a configured database URL.
"""
