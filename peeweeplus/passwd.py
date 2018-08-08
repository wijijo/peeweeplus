"""Argon2-based password hashing."""

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, VerifyMismatchError
from peewee import FieldAccessor

from peeweeplus.exceptions import PasswordTooShortError


__all__ = ['PASSWORD_HASHER', 'Argon2FieldAccessor']


PASSWORD_HASHER = PasswordHasher()
_MIN_PW_LEN = 8


def is_hash(value, hasher=PASSWORD_HASHER):
    """Determines whether value is a valid Argon2 hash for hasher."""

    try:
        return hasher.verify(value, '')
    except VerifyMismatchError:
        return True
    except VerificationError:
        return False


class Argon2Hash(str):
    """An Argon2 hash."""

    def __new__(cls, _, value):
        """Override str constructor."""
        return str.__new__(cls, value)

    def __init__(self, hasher, _):
        """Sets the hasher."""
        super().__init__()
        self._hasher = hasher

    def verify(self, passwd):
        """Validates the plain text password against this hash."""
        return self._hasher.verify(self, passwd)


class Argon2FieldAccessor(FieldAccessor):
    """Accessor class for Argon2Field."""

    def __get__(self, instance, instance_type=None):
        """Returns an Argon2 hash."""
        value = super().__get__(instance, instance_type=instance_type)

        if instance is not None:
            if value is None:
                return None

            return Argon2Hash(self.field.hasher, value)

        return value

    def __set__(self, instance, value):
        """Sets the password hash."""
        if value is not None and not is_hash(self.field.hasher, value):
            # If value is a plain text password, hash it.
            if len(value) < _MIN_PW_LEN:
                raise PasswordTooShortError(len(value), _MIN_PW_LEN)

            value = self.field.hasher.hash(value)

        super().__set__(instance, value)
