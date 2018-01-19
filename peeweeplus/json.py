"""JSON serializable and deserializable model definitions."""

from base64 import b64decode, b64encode
from contextlib import suppress
from datetime import datetime, date, time

from peewee import Model, Field, PrimaryKeyField, ForeignKeyField, \
    BooleanField, IntegerField, FloatField, DecimalField, DateTimeField, \
    DateField, TimeField, BlobField

from timelib import strpdatetime, strpdate, strptime

from peeweeplus.fields import EnumField

__all__ = [
    'FieldValueError',
    'FieldNotNullable',
    'iterfields',
    'filter_fk_dupes',
    'map_fields',
    'deserialize',
    'patch',
    'serialize',
    'JSONModel']


class NullError(ValueError):
    """Indicates that the respective field cannot be null."""

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


class FieldNotNullable(FieldValueError):
    """Indicates that the field was assigned
    a NULL value which it cannot store.
    """

    def __init__(self, model, attr, field):
        """Sets the field."""
        super().__init__(model, attr, field, None)

    def __str__(self):
        """Returns the respective error message."""
        return (
            '<{field.__class__.__name__} {field.db_column}> at '
            '<{model.__class__.__name__}.{attr}> must not be NULL.').format(
                field=self.field, model=self.model, attr=self.attr)


def iterfields(model, protected=False, primary_key=True, foreign_keys=False):
    """Yields fields of the model."""

    for attribute in dir(model):
        if protected or not attribute.startswith('_'):
            field = getattr(model, attribute)

            if isinstance(field, Field):
                if not primary_key and isinstance(field, PrimaryKeyField):
                    continue
                if not foreign_keys and isinstance(field, ForeignKeyField):
                    continue

                yield (attribute, field)


def filter_fk_dupes(fields):
    """Filters out shortest-named foreign key descriptors."""

    fk_fields = {}

    for attribute, field in fields:
        if isinstance(field, ForeignKeyField):
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


def map_fields(model, protected=False, primary_key=True, foreign_keys=False):
    """Returns a dictionary of the respective database fields."""

    if foreign_keys:
        return {
            field.db_column: (attribute, field) for attribute, field
            in filter_fk_dupes(iterfields(
                model, protected=protected, primary_key=primary_key,
                foreign_keys=True))}

    # No need to filter foreign key duplicates if
    # we excluded foreign keys in the fist place.
    return {
        field.db_column: (attribute, field) for attribute, field in iterfields(
            model, protected=protected, primary_key=primary_key,
            foreign_keys=False)}


def filter_fields(iterable):
    """Yields subclasses of peewee.Field from the iterable."""

    for item in iterable:
        with suppress(TypeError):
            if issubclass(item, Field):
                yield item


def field_to_json(field, value):
    """Converts the given field's value into JSON-ish data."""

    if value is None:
        return value
    elif isinstance(field, ForeignKeyField):
        try:
            return value._get_pk_value()
        except AttributeError:
            return value
    elif isinstance(field, DecimalField):
        return float(value)
    elif isinstance(field, (DateTimeField, DateField, TimeField)):
        return value.isoformat()
    elif isinstance(field, BlobField):
        return b64encode(value)
    elif isinstance(field, EnumField):
        return value.value

    return value


def value_to_field(value, field):
    """Converts a value for the provided field."""

    if value is None:
        if not field.null:
            raise NullError()

        return value
    elif isinstance(field, BooleanField):
        if isinstance(value, (bool, int)):
            return bool(value)

        raise ValueError(value)
    elif isinstance(field, IntegerField):
        return int(value)
    elif isinstance(field, FloatField):
        return float(value)
    elif isinstance(field, DecimalField):
        return float(value)
    elif isinstance(field, DateTimeField):
        if isinstance(value, datetime):
            return value

        return strpdatetime(value)
    elif isinstance(field, DateField):
        if isinstance(value, date):
            return value

        return strpdate(value)
    elif isinstance(field, TimeField):
        if isinstance(value, time):
            return value

        return strptime(value)
    elif isinstance(field, BlobField):
        if isinstance(value, bytes):
            return value

        return b64decode(value)

    return value


def deserialize(model, dictionary, protected=False, foreign_keys=False):
    """Creates a record from the provided JSON-ish dictionary.
    This will consume the provided dictionary.
    """

    field_map = map_fields(
        model, protected=protected, foreign_keys=foreign_keys)
    record = model()

    for db_column, (attribute, field) in field_map.items():
        try:
            value = dictionary.pop(db_column)
        except KeyError:
            if not field.null and field.default is None:
                raise FieldNotNullable(model, attribute, field)

            continue

        try:
            field_value = value_to_field(value, field)
        except NullError:
            raise FieldNotNullable(model, attribute, field)
        except (TypeError, ValueError):
            raise FieldValueError(model, attribute, field, value)

        setattr(record, attribute, field_value)

    return record


def patch(record, dictionary, protected=False, foreign_keys=False):
    """Patches the record with the provided JSON-ish dictionary.
    This will consume the provided dictionary.
    """

    field_map = map_fields(
        record.__class__, protected=protected, foreign_keys=foreign_keys)

    for db_column, (attribute, field) in field_map.items():
        try:
            value = dictionary.pop(db_column)
        except KeyError:
            continue

        try:
            field_value = value_to_field(value, field)
        except NullError:
            raise FieldNotNullable(record.__class__, attribute, field)
        except (TypeError, ValueError):
            raise FieldValueError(record.__class__, attribute, field, value)

        setattr(record, attribute, field_value)

    return record


def serialize(record, ignore=(), null=True, protected=False, primary_key=True,
              foreign_keys=False):
    """Returns a JSON-ish dictionary with the record's values."""

    ignored_fields = tuple(filter_fields(ignore))
    dictionary = {}
    field_map = map_fields(
        record.__class__, protected=protected, primary_key=primary_key,
        foreign_keys=foreign_keys)

    for db_column, (attribute, field) in field_map.items():
        if any((db_column in ignore, attribute in ignore,
                isinstance(field, ignored_fields))):
            continue

        value = getattr(record, attribute)

        if value is not None or null:
            dictionary[field.db_column] = field_to_json(field, value)

    return dictionary


class JSONModel(Model):
    """A JSON serializable and deserializable model."""

    @classmethod
    def from_dict(cls, dictionary, protected=False, foreign_keys=False):
        """Creates a record from the provided JSON-ish dictionary."""
        return deserialize(
            cls, dictionary, protected=protected, foreign_keys=foreign_keys)

    def patch(self, json, protected=False, foreign_keys=False):
        """Patches the record with the provided JSON-ish dictionary."""
        return patch(
            self, json, protected=protected, foreign_keys=foreign_keys)

    def to_dict(self, ignore=(), null=True, protected=False, primary_key=True,
                foreign_keys=False):
        """Returns a JSON-ish dictionary with the record's values."""
        return serialize(
            self, ignore=ignore, null=null, protected=protected,
            primary_key=primary_key, foreign_keys=foreign_keys)
