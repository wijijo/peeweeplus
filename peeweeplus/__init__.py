"""Practical extensions of the peewee ORM framework."""

from logging import getLogger

from peeweeplus.contextmanagers import ChangedConnection
from peeweeplus.converters import dec2dom
from peeweeplus.converters import dec2dict
from peeweeplus.converters import dec2orm
from peeweeplus.converters import date2orm
from peeweeplus.converters import datetime2orm
from peeweeplus.database import MySQLDatabase
from peeweeplus.exceptions import MissingModule
from peeweeplus.exceptions import FieldValueError
from peeweeplus.exceptions import FieldNotNullable
from peeweeplus.exceptions import MissingKeyError
from peeweeplus.exceptions import InvalidKeys
from peeweeplus.exceptions import NonUniqueValue
from peeweeplus.exceptions import PasswordTooShortError
from peeweeplus.fields import *
from peeweeplus.fields import __all__ as ALL_FIELDS
from peeweeplus.json import deserialize, serialize, JSONMixin, JSONModel
from peeweeplus.transaction import Transaction


__all__ = [
    'FieldValueError',
    'FieldNotNullable',
    'MissingKeyError',
    'InvalidKeys',
    'NonUniqueValue',
    'PasswordTooShortError',
    'dec2dom',
    'dec2dict',
    'dec2orm',
    'date2orm',
    'datetime2orm',
    'deserialize',
    'serialize',
    'ChangedConnection',
    'MySQLDatabase',
    'JSONMixin',
    'JSONModel',
    'Transaction'
] + ALL_FIELDS


LOGGER = getLogger(__file__)


try:
    from peeweeplus.authlib import *
    from peeweeplus.authlib import __all__  as ALL_OAUTHLIB
except MissingModule as error:
    LOGGER.warning('Missing module "%s".', error.module)
    LOGGER.warning('oauthlib integration not available.')
else:
    __all__ += ALL_OAUTHLIB
