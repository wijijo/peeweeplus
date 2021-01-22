"""Database enhancements."""

from __future__ import annotations
from configparser import SectionProxy
from typing import Any

from peewee import OperationalError, MySQLDatabase


__all__ = ['MySQLDatabase']


class MySQLDatabase(MySQLDatabase):     # pylint: disable=E0102,W0223
    """Extension of peewee.MySQLDatabase with closing option."""

    def __init__(self, *args, closing: bool = False, retry: bool = False,
                 **kwargs):
        """Adds closing switch for automatic connection closing."""
        super().__init__(*args, **kwargs)
        self.closing = closing
        self.retry = retry

    @classmethod
    def from_config(cls, config: SectionProxy) -> MySQLDatabase:
        """Creates a database from the respective configuration."""
        try:
            database = config['db']
        except KeyError:
            database = config['database']

        try:
            passwd = config['passwd']
        except KeyError:
            passwd = config['password']

        closing = config.getboolean('closing', True)
        retry = config.getboolean('retry', False)

        return cls(
            database, host=config['host'], user=config['user'], passwd=passwd,
            closing=closing, retry=retry)

    # pylint: disable=W0221
    def execute_sql(self, *args, retried: bool = False, **kwargs) -> Any:
        """Conditionally execute the SQL query in an
        execution context iff closing is enabled.
        """
        if self.closing:
            with self.connection_context():
                return super().execute_sql(*args, **kwargs)

        try:
            return super().execute_sql(*args, **kwargs)
        except OperationalError:
            if not self.retry or retried:
                raise

            if not self.is_closed():
                self.close()

            return self.execute_sql(*args, retried=True, **kwargs)
