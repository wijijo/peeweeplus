"""Practical extension of the peewee ORM framework."""

from base64 import b64encode, b64decode
from collections import namedtuple
from contextlib import suppress
from datetime import datetime, date, time
from logging import getLogger
from types import GeneratorType

from timelib import strpdatetime, strpdate, strptime

import peewee

__all__ = [
    'FieldValueError',
    'FieldNotNullError',
    'InvalidEnumerationValue',
    'create',
    'dec2dom',
    'dec2dict',
    'dec2orm',
    'date2orm',
    'datetime2orm',
    'list_fields',
    'filter_fields',
    'filter_fk_dupes',
    'field_to_json',
    'value_to_field',
    'DisabledAutoIncrement',
    'MySQLDatabase',
    'JSONModel',
    'EnumField']


TIME_FIELDS = (peewee.DateTimeField, peewee.DateField, peewee.TimeField)
KEY_FIELDS = (peewee.PrimaryKeyField, peewee.ForeignKeyField)
LOGGER = getLogger('peeweeplus')


AttributeValue = namedtuple('AttributeValue', ('attribute', 'value'))


class NullError(TypeError):
    """Indicates that the respective field
    was set to NULL but must not be NULL.
    """

    pass


class FieldValueError(ValueError):
    """Indicates that the field cannot store data of the provided type."""

    TEMPLATE = (
        '<{field.__class__.__name__} {field.db_column}> at '
        '<{model.__class__.__name__}.{attr}> cannot store {typ}: {value}.')

    def __init__(self, model, attr, field, value):
        """Sets the field and value."""
        super().__init__((model, attr, field, value))
        self.model = model
        self.attr = attr
        self.field = field
        self.value = value

    def __str__(self):
        """Returns the respective error message."""
        return self.TEMPLATE.format(
            field=self.field, model=self.model, attr=self.attr,
            typ=type(self.value), value=self.value)

    def to_dict(self):
        """Returns a JSON-ish representation of this error."""
        return {
            'model': self.model.__class__.__name__,
            'attr': self.attr,
            'field': self.field.__class__.__name__,
            'db_column': self.field.db_column,
            'value': str(self.value),
            'type': type(self.value)}


class FieldNotNullError(FieldValueError):
    """Indicates that the field was assigned
    a NULL value which it cannot store.
    """

    TEMPLATE = (
        '<{field.__class__.__name__} {field.db_column}> at '
        '<{model.__class__.__name__}.{attr}> must not be NULL.')

    def __init__(self, model, attr, field):
        """Sets the field."""
        super().__init__(model, attr, field, None)

    def __str__(self):
        """Returns the respective error message."""
        return self.TEMPLATE.format(
            field=self.field, model=self.model, attr=self.attr)


class InvalidEnumerationValue(ValueError):
    """Indicates that an invalid enumeration value has been specified."""

    def __init__(self, value):
        super().__init__('Invalid enum value: "{}".'.format(value))


def create(model):
    """Decorator for peewee.Model definitions that
    actually should be created on load.

    Usage:
        @create
        class MyModel(peewee.Model):
            pass
    """

    with suppress(peewee.OperationalError):
        with model._meta.database.execution_context():
            model.create_table(fail_silently=True)

    return model


def dec2dom(value):
    """Converts a decimal into a string."""

    if value is not None:
        return str(value)


def dec2dict(value):
    """Converts a decimal into a string."""

    if value is not None:
        return float(value)


def dec2orm(value):
    """Converts a decimal into an ORM compliant value."""

    return dec2dict(value)


def date2orm(value):
    """Converts a PyXB date object to a datetime.date object."""

    if value is not None:
        return value.date()


def datetime2orm(value):
    """Converts a PyXB date object to a datetime.date object."""

    if value is not None:
        return strpdatetime(value.isoformat())


def list_fields(model, protected=False):
    """Yields attribute-value tuples of fields of a peewee.Model."""

    return filter(lambda aval: isinstance(aval.value, peewee.Field), map(
        lambda attr: AttributeValue(attr, getattr(model, attr)), filter(
            lambda attr: protected or not attr.startswith('_'), dir(model))))


def filter_fk_dupes(fields):
    """Filters out shortest-named foreign key descriptors."""

    fk_fields = {}

    for attribute, field in fields:
        if isinstance(field, peewee.ForeignKeyField):
            fk_fields[attribute] = field
        else:
            yield (attribute, field)

    for attribute, field in fk_fields.items():
        # Skip ID descriptors generated by peewee.
        if attribute.endswith('_id'):
            try:
                alt_field = fk_fields[attribute[:-3]]
            except KeyError:
                pass
            else:
                if field.db_column == alt_field.db_column:
                    continue

        yield (attribute, field)


def filter_fields(fields, exclude=KEY_FIELDS):
    """Filters field types."""

    return filter(lambda aval: not isinstance(aval.value, exclude), fields)


def field_to_json(field, value):
    """Converts the given field's value into JSON-ish data."""

    if value is None:
        return value
    elif isinstance(field, peewee.ForeignKeyField):
        try:
            return value._get_pk_value()
        except AttributeError:
            return value
    elif isinstance(field, peewee.DecimalField):
        return float(value)
    elif isinstance(field, TIME_FIELDS):
        return value.isoformat()
    elif isinstance(field, peewee.BlobField):
        return b64encode(value)

    return value


def value_to_field(value, field):
    """Converts a value for the provided field."""

    if value is None:
        if not field.null:
            raise NullError()

        return value
    elif isinstance(field, peewee.BooleanField):
        if isinstance(value, (bool, int)):
            return bool(value)

        raise ValueError(value)
    elif isinstance(field, peewee.IntegerField):
        return int(value)
    elif isinstance(field, peewee.FloatField):
        return float(value)
    elif isinstance(field, peewee.DecimalField):
        return float(value)
    elif isinstance(field, peewee.DateTimeField):
        if isinstance(value, datetime):
            return value

        return strpdatetime(value)
    elif isinstance(field, peewee.DateField):
        if isinstance(value, date):
            return value

        return strpdate(value)
    elif isinstance(field, peewee.TimeField):
        if isinstance(value, time):
            return value

        return strptime(value)
    elif isinstance(field, peewee.BlobField):
        if isinstance(value, bytes):
            return value

        return b64decode(value)

    return value


class DisabledAutoIncrement:
    """Disables auto increment on the respective model."""

    def __init__(self, model):
        self.model = model

    def __enter__(self):
        self.model._meta.auto_increment = False
        return self

    def __exit__(self, *_):
        self.model._meta.auto_increment = True


class MySQLDatabase(peewee.MySQLDatabase):
    """Extension of peewee.MySQLDatabase with closing option."""

    def __init__(self, *args, closing=False, **kwargs):
        """Adds closing switch for automatic connection closing."""
        super().__init__(*args, **kwargs)
        self.closing = closing

    def execute_sql(self, *args, **kwargs):
        """Conditionally execute the SQL query in an
        execution context iff closing is enabled.
        """
        if self.closing:
            with self.execution_context():
                return super().execute_sql(*args, **kwargs)

        return super().execute_sql(*args, **kwargs)


class Blacklist:
    """Blacklist of fields and attributes."""

    def __init__(self, attributes=None, fields=None):
        """Sets the respective attributes and fields."""
        self.attributes = set() if attributes is None else set(attributes)
        self.fields = set() if fields is None else set(fields)

    def __contains__(self, item):
        """Determines whether the item is contained within the blacklist."""
        try:
            attribute, field = item
        except ValueError:
            if isinstance(item, peewee.Field):
                return isinstance(item, tuple(self.fields))

            return item in self.attributes

        return attribute in self.attributes or isinstance(
            field, tuple(self.fields))

    @classmethod
    def load(cls, value):
        """Loads a blacklist from the respective value."""
        if value is None:
            return cls()
        elif isinstance(value, str):
            return cls(attributes=[value])
        elif isinstance(value, peewee.Field):
            return cls(fields=[value])
        elif isinstance(value, (tuple, list, GeneratorType)):
            attributes = set()
            fields = set()

            for item in value:
                if isinstance(item, str):
                    attributes.add(item)
                elif isinstance(item, peewee.Field):
                    fields.add(item)
                else:
                    raise TypeError('Invalid blacklist item {}.'.format(item))

            return cls(attributes=attributes, fields=fields)

        raise TypeError('Cannot create blacklist from {}.'.format(value))


class JSONModel(peewee.Model):
    """A JSON-serializable model."""

    @classmethod
    def from_dict(cls, dictionary, blacklist=None, protected=False,
                  by_attr=False):
        """Creates a new record from a JSON-ish dictionary."""
        record = cls()
        blacklist = Blacklist.load(blacklist)

        for attribute, field in filter_fields(list_fields(
                cls, protected=protected)):
            if (attribute, field) in blacklist:
                continue

            value = dictionary.get(attribute if by_attr else field.db_column)

            try:
                field_value = value_to_field(value, field)
            except NullError:
                raise FieldNotNullError(cls, attribute, field) from None
            except (TypeError, ValueError):
                raise FieldValueError(cls, attribute, field, value) from None
            else:
                setattr(record, attribute, field_value)

        return record

    def patch(self, dictionary, blacklist=None, protected=False,
              by_attr=False):
        """Modifies the record with the values from a JSON-ish dictionary."""
        cls = self.__class__
        blacklist = Blacklist.load(blacklist)

        for attribute, field in filter_fields(list_fields(
                cls, protected=protected)):
            if (attribute, field) in blacklist:
                continue

            try:
                value = dictionary[attribute if by_attr else field.db_column]
            except KeyError:
                continue

            try:
                field_value = value_to_field(value, field)
            except NullError:
                raise FieldNotNullError(cls, attribute, field) from None
            except (TypeError, ValueError):
                raise FieldValueError(cls, attribute, field, value) from None
            else:
                setattr(self, attribute, field_value)

    def to_dict(self, blacklist=None, null=True, protected=False,
                by_attr=False):
        """Returns a JSON-ish dictionary with the record's values."""
        dictionary = {}
        blacklist = Blacklist.load(blacklist)

        for attribute, field in filter_fk_dupes(list_fields(
                self.__class__, protected=protected)):
            if (attribute, field) in blacklist:
                continue

            value = getattr(self, attribute)

            if value is None and not null:
                continue

            key = attribute if by_attr else field.db_column
            dictionary[key] = field_to_json(field, value)

        return dictionary


class EnumField(peewee.CharField):
    """CharField-based enumeration field."""

    def __init__(self, values, *args, max_length=None, null=None, **kwargs):
        """Initializes the enumeration field with the possible values.

        :enum: The respective enumeration.
        :max_length: Ignored.
        :null: Ignored.
        """
        super().__init__(*args, max_length=max_length, null=null, **kwargs)
        self.values = set(values)

        # Try to build translation dict for enum.Enum.
        with suppress(AttributeError):
            self.values = {item.value: item for item in self.values}

    @property
    def max_length(self):
        """Derives the required field size from the enumeration values."""
        return max(len(value) for value in self.values if value is not None)

    @max_length.setter
    def max_length(self, max_length):
        """Mockup to comply with super class' __init__."""
        if max_length is not None:
            raise TypeError('Cannot set max_length to non-None value.')

    @property
    def null(self):
        """Determines nullability by enum values."""
        return any(value is None for value in self.values)

    @null.setter
    def null(self, null):
        """Mockup to comply with super class' __init__."""
        if null is not None:
            raise TypeError('Cannot set null to non-None value.')

    def db_value(self, value):
        """Coerce enumeration value for database."""
        with suppress(AttributeError):
            value = value.value

        if value in self.values:
            return value

        raise InvalidEnumerationValue(value)

    def python_value(self, value):
        """Coerce enumeration value for python."""
        try:
            return self.values[value]
        except TypeError:
            if value in self.values:
                return value

            raise InvalidEnumerationValue(value)
        except KeyError:
            raise InvalidEnumerationValue(value)
