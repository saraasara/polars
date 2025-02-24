from __future__ import annotations

import contextlib
from collections import OrderedDict
from datetime import timezone
from inspect import isclass
from typing import TYPE_CHECKING, Any, Iterable, Iterator, Mapping, Sequence

import polars._reexport as pl
import polars.datatypes

with contextlib.suppress(ImportError):  # Module not available when building docs
    from polars.polars import dtype_str_repr as _dtype_str_repr

if TYPE_CHECKING:
    from polars import Series
    from polars.type_aliases import (
        CategoricalOrdering,
        PolarsDataType,
        PythonDataType,
        SchemaDict,
        TimeUnit,
    )


class classinstmethod(classmethod):  # type: ignore[type-arg]
    """Decorator that allows a method to be called from the class OR instance."""

    def __get__(self, instance: Any, type_: type) -> Any:  # type: ignore[override]
        get = super().__get__ if instance is None else self.__func__.__get__
        return get(instance, type_)


class DataTypeClass(type):
    """Metaclass for nicely printing DataType classes."""

    def __repr__(cls) -> str:
        return cls.__name__

    def _string_repr(cls) -> str:
        return _dtype_str_repr(cls)

    # Methods below defined here in signature only to satisfy mypy

    @classmethod
    def base_type(cls) -> DataTypeClass:  # noqa: D102
        ...

    @classmethod
    def is_(cls, other: PolarsDataType) -> bool:  # noqa: D102
        ...

    @classmethod
    def is_not(cls, other: PolarsDataType) -> bool:  # noqa: D102
        ...

    @classmethod
    def is_numeric(cls) -> bool:  # noqa: D102
        ...

    @classmethod
    def is_decimal(cls) -> bool:  # noqa: D102
        ...

    @classmethod
    def is_integer(cls) -> bool:  # noqa: D102
        ...

    @classmethod
    def is_signed_integer(cls) -> bool:  # noqa: D102
        ...

    @classmethod
    def is_unsigned_integer(cls) -> bool:  # noqa: D102
        ...

    @classmethod
    def is_float(cls) -> bool:  # noqa: D102
        ...

    @classmethod
    def is_temporal(cls) -> bool:  # noqa: D102
        ...

    @classmethod
    def is_nested(self) -> bool:  # noqa: D102
        ...


class DataType(metaclass=DataTypeClass):
    """Base class for all Polars data types."""

    __slots__ = ()

    def _string_repr(self) -> str:
        return _dtype_str_repr(self)

    def __eq__(self, other: PolarsDataType) -> bool:  # type: ignore[override]
        if type(other) is DataTypeClass:
            return issubclass(other, type(self))
        else:
            return isinstance(other, type(self))

    def __hash__(self) -> int:
        return hash(self.__class__)

    def __repr__(self) -> str:
        return self.__class__.__name__

    @classmethod
    def base_type(cls) -> DataTypeClass:
        """
        Return this DataType's fundamental/root type class.

        Examples
        --------
        >>> pl.Datetime("ns").base_type()
        Datetime
        >>> pl.List(pl.Int32).base_type()
        List
        >>> pl.Struct([pl.Field("a", pl.Int64), pl.Field("b", pl.Boolean)]).base_type()
        Struct
        """
        return cls

    @classinstmethod  # type: ignore[arg-type]
    def is_(self, other: PolarsDataType) -> bool:
        """
        Check if this DataType is the same as another DataType.

        This is a stricter check than `self == other`, as it enforces an exact
        match of all dtype attributes for nested and/or uninitialised dtypes.

        Parameters
        ----------
        other
            the other polars dtype to compare with.

        Examples
        --------
        >>> pl.List == pl.List(pl.Int32)
        True
        >>> pl.List.is_(pl.List(pl.Int32))
        False
        """
        return self == other and hash(self) == hash(other)

    @classinstmethod  # type: ignore[arg-type]
    def is_not(self, other: PolarsDataType) -> bool:
        """
        Check if this DataType is NOT the same as another DataType.

        .. deprecated:: 0.19.14
            Use `not dtype.is_(...)` instead.

        This is a stricter check than `self != other`, as it enforces an exact
        match of all dtype attributes for nested and/or uninitialised dtypes.

        Parameters
        ----------
        other
            the other polars dtype to compare with.

        Examples
        --------
        >>> pl.List != pl.List(pl.Int32)
        False
        >>> pl.List.is_not(pl.List(pl.Int32))  # doctest: +SKIP
        True
        """
        from polars.utils.deprecation import issue_deprecation_warning

        issue_deprecation_warning(
            "`DataType.is_not` is deprecated and will be removed in the next breaking release."
            " Use `not dtype.is_(...)` instead.",
            version="0.19.14",
        )
        return not self.is_(other)

    @classmethod
    def is_numeric(cls) -> bool:
        """Check whether the data type is a numeric type."""
        return issubclass(cls, NumericType)

    @classmethod
    def is_decimal(cls) -> bool:
        """Check whether the data type is a decimal type."""
        return issubclass(cls, Decimal)

    @classmethod
    def is_integer(cls) -> bool:
        """Check whether the data type is an integer type."""
        return issubclass(cls, IntegerType)

    @classmethod
    def is_signed_integer(cls) -> bool:
        """Check whether the data type is a signed integer type."""
        return issubclass(cls, SignedIntegerType)

    @classmethod
    def is_unsigned_integer(cls) -> bool:
        """Check whether the data type is an unsigned integer type."""
        return issubclass(cls, UnsignedIntegerType)

    @classmethod
    def is_float(cls) -> bool:
        """Check whether the data type is a temporal type."""
        return issubclass(cls, FloatType)

    @classmethod
    def is_temporal(cls) -> bool:
        """Check whether the data type is a temporal type."""
        return issubclass(cls, TemporalType)

    @classmethod
    def is_nested(cls) -> bool:
        """Check whether the data type is a nested type."""
        return issubclass(cls, NestedType)


class DataTypeGroup(frozenset):  # type: ignore[type-arg]
    """Group of data types."""

    __slots__ = ("_match_base_type",)
    _match_base_type: bool

    def __new__(
        cls, items: Iterable[DataType | DataTypeClass], *, match_base_type: bool = True
    ) -> DataTypeGroup:
        """
        Construct a DataTypeGroup.

        Parameters
        ----------
        items :
            iterable of data types
        match_base_type:
            match the base type
        """
        for it in items:
            if not isinstance(it, (DataType, DataTypeClass)):
                msg = f"DataTypeGroup items must be dtypes; found {type(it).__name__!r}"
                raise TypeError(msg)
        dtype_group = super().__new__(cls, items)  # type: ignore[arg-type]
        dtype_group._match_base_type = match_base_type
        return dtype_group

    def __contains__(self, item: Any) -> bool:
        if self._match_base_type and isinstance(item, (DataType, DataTypeClass)):
            item = item.base_type()
        return super().__contains__(item)


class NumericType(DataType):
    """Base class for numeric data types."""

    __slots__ = ()


class IntegerType(NumericType):
    """Base class for integer data types."""

    __slots__ = ()


class SignedIntegerType(IntegerType):
    """Base class for signed integer data types."""

    __slots__ = ()


class UnsignedIntegerType(IntegerType):
    """Base class for unsigned integer data types."""

    __slots__ = ()


class FloatType(NumericType):
    """Base class for float data types."""

    __slots__ = ()


class TemporalType(DataType):
    """Base class for temporal data types."""

    __slots__ = ()


class NestedType(DataType):
    """Base class for nested data types."""

    __slots__ = ()


class Int8(SignedIntegerType):
    """8-bit signed integer type."""

    __slots__ = ()


class Int16(SignedIntegerType):
    """16-bit signed integer type."""

    __slots__ = ()


class Int32(SignedIntegerType):
    """32-bit signed integer type."""

    __slots__ = ()


class Int64(SignedIntegerType):
    """64-bit signed integer type."""

    __slots__ = ()


class UInt8(UnsignedIntegerType):
    """8-bit unsigned integer type."""

    __slots__ = ()


class UInt16(UnsignedIntegerType):
    """16-bit unsigned integer type."""

    __slots__ = ()


class UInt32(UnsignedIntegerType):
    """32-bit unsigned integer type."""

    __slots__ = ()


class UInt64(UnsignedIntegerType):
    """64-bit unsigned integer type."""

    __slots__ = ()


class Float32(FloatType):
    """32-bit floating point type."""

    __slots__ = ()


class Float64(FloatType):
    """64-bit floating point type."""

    __slots__ = ()


class Decimal(NumericType):
    """
    Decimal 128-bit type with an optional precision and non-negative scale.

    .. warning::
        This functionality is considered **unstable**.
        It is a work-in-progress feature and may not always work as expected.
        It may be changed at any point without it being considered a breaking change.

    Parameters
    ----------
    precision
        Maximum number of digits in each number.
        If set to `None` (default), the precision is inferred.
    scale
        Number of digits to the right of the decimal point in each number.
    """

    __slots__ = ("precision", "scale")
    precision: int | None
    scale: int

    def __init__(
        self,
        precision: int | None = None,
        scale: int = 0,
    ):
        # Issuing the warning on `__init__` does not trigger when the class is used
        # without being instantiated, but it's better than nothing
        from polars.utils.unstable import issue_unstable_warning

        issue_unstable_warning(
            "The Decimal data type is considered unstable."
            " It is a work-in-progress feature and may not always work as expected."
        )

        self.precision = precision
        self.scale = scale

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}(precision={self.precision}, scale={self.scale})"
        )

    def __eq__(self, other: PolarsDataType) -> bool:  # type: ignore[override]
        # allow comparing object instances to class
        if type(other) is DataTypeClass and issubclass(other, Decimal):
            return True
        elif isinstance(other, Decimal):
            return self.precision == other.precision and self.scale == other.scale
        else:
            return False

    def __hash__(self) -> int:
        return hash((self.__class__, self.precision, self.scale))


class Boolean(DataType):
    """Boolean type."""

    __slots__ = ()


class String(DataType):
    """UTF-8 encoded string type."""

    __slots__ = ()


# Allow Utf8 as an alias for String
Utf8 = String


class Binary(DataType):
    """Binary type."""

    __slots__ = ()


class Date(TemporalType):
    """
    Data type representing a calendar date.

    Notes
    -----
    The underlying representation of this type is a 32-bit signed integer.
    The integer indicates the number of days since the Unix epoch (1970-01-01).
    The number can be negative to indicate dates before the epoch.
    """

    __slots__ = ()


class Time(TemporalType):
    """
    Data type representing the time of day.

    Notes
    -----
    The underlying representation of this type is a 64-bit signed integer.
    The integer indicates the number of nanoseconds since midnight.
    """

    __slots__ = ()


class Datetime(TemporalType):
    """
    Data type representing a calendar date and time of day.

    Parameters
    ----------
    time_unit : {'us', 'ns', 'ms'}
        Unit of time. Defaults to `'us'` (microseconds).
    time_zone
        Time zone string, as defined in zoneinfo (to see valid strings run
        `import zoneinfo; zoneinfo.available_timezones()` for a full list).
        When using to match dtypes, can use "*" to check for Datetime columns
        that have any timezone.

    Notes
    -----
    The underlying representation of this type is a 64-bit signed integer.
    The integer indicates the number of time units since the Unix epoch
    (1970-01-01 00:00:00). The number can be negative to indicate datetimes before the
    epoch.
    """

    time_unit: TimeUnit | None = None
    time_zone: str | None = None

    def __init__(
        self, time_unit: TimeUnit = "us", time_zone: str | timezone | None = None
    ):
        if time_unit is None:
            from polars.utils.deprecation import issue_deprecation_warning

            issue_deprecation_warning(
                "Passing `time_unit=None` to the Datetime constructor is deprecated."
                " Either avoid passing a time unit to use the default value ('us'),"
                " or pass a valid time unit instead ('ms', 'us', 'ns').",
                version="0.20.11",
            )
            time_unit = "us"

        if time_unit not in ("ms", "us", "ns"):
            msg = (
                "invalid `time_unit`"
                f"\n\nExpected one of {{'ns','us','ms'}}, got {time_unit!r}."
            )
            raise ValueError(msg)

        if isinstance(time_zone, timezone):
            time_zone = str(time_zone)

        self.time_unit = time_unit
        self.time_zone = time_zone

    def __eq__(self, other: PolarsDataType) -> bool:  # type: ignore[override]
        # allow comparing object instances to class
        if type(other) is DataTypeClass and issubclass(other, Datetime):
            return True
        elif isinstance(other, Datetime):
            return (
                self.time_unit == other.time_unit and self.time_zone == other.time_zone
            )
        else:
            return False

    def __hash__(self) -> int:
        return hash((self.__class__, self.time_unit, self.time_zone))

    def __repr__(self) -> str:
        class_name = self.__class__.__name__
        return (
            f"{class_name}(time_unit={self.time_unit!r}, time_zone={self.time_zone!r})"
        )


class Duration(TemporalType):
    """
    Data type representing a time duration.

    Parameters
    ----------
    time_unit : {'us', 'ns', 'ms'}
        Unit of time. Defaults to `'us'` (microseconds).

    Notes
    -----
    The underlying representation of this type is a 64-bit signed integer.
    The integer indicates an amount of time units and can be negative to indicate
    negative time offsets.
    """

    time_unit: TimeUnit | None = None

    def __init__(self, time_unit: TimeUnit = "us"):
        if time_unit not in ("ms", "us", "ns"):
            msg = (
                "invalid `time_unit`"
                f"\n\nExpected one of {{'ns','us','ms'}}, got {time_unit!r}."
            )
            raise ValueError(msg)

        self.time_unit = time_unit

    def __eq__(self, other: PolarsDataType) -> bool:  # type: ignore[override]
        # allow comparing object instances to class
        if type(other) is DataTypeClass and issubclass(other, Duration):
            return True
        elif isinstance(other, Duration):
            return self.time_unit == other.time_unit
        else:
            return False

    def __hash__(self) -> int:
        return hash((self.__class__, self.time_unit))

    def __repr__(self) -> str:
        class_name = self.__class__.__name__
        return f"{class_name}(time_unit={self.time_unit!r})"


class Categorical(DataType):
    """
    A categorical encoding of a set of strings.

    Parameters
    ----------
    ordering : {'lexical', 'physical'}
        Ordering by order of appearance (`'physical'`, default)
        or string value (`'lexical'`).
    """

    __slots__ = ("ordering",)
    ordering: CategoricalOrdering | None

    def __init__(
        self,
        ordering: CategoricalOrdering | None = "physical",
    ):
        self.ordering = ordering

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(ordering={self.ordering!r})"

    def __eq__(self, other: PolarsDataType) -> bool:  # type: ignore[override]
        # allow comparing object instances to class
        if type(other) is DataTypeClass and issubclass(other, Categorical):
            return True
        elif isinstance(other, Categorical):
            return self.ordering == other.ordering
        else:
            return False

    def __hash__(self) -> int:
        return hash((self.__class__, self.ordering))


class Enum(DataType):
    """
    A fixed set categorical encoding of a set of strings.

    .. warning::
        This functionality is considered **unstable**.
        It is a work-in-progress feature and may not always work as expected.
        It may be changed at any point without it being considered a breaking change.

    Parameters
    ----------
    categories
        The categories in the dataset. Categories must be strings.
    """

    __slots__ = ("categories",)
    categories: Series

    def __init__(self, categories: Series | Iterable[str]):
        # Issuing the warning on `__init__` does not trigger when the class is used
        # without being instantiated, but it's better than nothing
        from polars.utils.unstable import issue_unstable_warning

        issue_unstable_warning(
            "The Enum data type is considered unstable."
            " It is a work-in-progress feature and may not always work as expected."
        )

        if not isinstance(categories, pl.Series):
            categories = pl.Series(values=categories)

        if categories.is_empty():
            self.categories = pl.Series(name="category", dtype=String)
            return

        if categories.null_count() > 0:
            msg = "Enum categories must not contain null values"
            raise TypeError(msg)

        if (dtype := categories.dtype) != String:
            msg = f"Enum categories must be strings; found data of type {dtype}"
            raise TypeError(msg)

        if categories.n_unique() != categories.len():
            duplicate = categories.filter(categories.is_duplicated())[0]
            msg = f"Enum categories must be unique; found duplicate {duplicate!r}"
            raise ValueError(msg)

        self.categories = categories.rechunk().alias("category")

    def __eq__(self, other: PolarsDataType) -> bool:  # type: ignore[override]
        # allow comparing object instances to class
        if type(other) is DataTypeClass and issubclass(other, Enum):
            return True
        elif isinstance(other, Enum):
            return self.categories.equals(other.categories)
        else:
            return False

    def __hash__(self) -> int:
        return hash((self.__class__, tuple(self.categories)))

    def __repr__(self) -> str:
        class_name = self.__class__.__name__
        return f"{class_name}(categories={self.categories.to_list()!r})"


class Object(DataType):
    """Data type for wrapping arbitrary Python objects."""

    __slots__ = ()


class Null(DataType):
    """Data type representing null values."""

    __slots__ = ()


class Unknown(DataType):
    """Type representing DataType values that could not be determined statically."""

    __slots__ = ()


class List(NestedType):
    """
    Variable length list type.

    Parameters
    ----------
    inner
        The `DataType` of the values within each list.

    Examples
    --------
    >>> df = pl.DataFrame(
    ...     {
    ...         "integer_lists": [[1, 2], [3, 4]],
    ...         "float_lists": [[1.0, 2.0], [3.0, 4.0]],
    ...     }
    ... )
    >>> df
    shape: (2, 2)
    ┌───────────────┬─────────────┐
    │ integer_lists ┆ float_lists │
    │ ---           ┆ ---         │
    │ list[i64]     ┆ list[f64]   │
    ╞═══════════════╪═════════════╡
    │ [1, 2]        ┆ [1.0, 2.0]  │
    │ [3, 4]        ┆ [3.0, 4.0]  │
    └───────────────┴─────────────┘
    """

    inner: PolarsDataType | None = None

    def __init__(self, inner: PolarsDataType | PythonDataType):
        self.inner = polars.datatypes.py_type_to_dtype(inner)

    def __eq__(self, other: PolarsDataType) -> bool:  # type: ignore[override]
        # This equality check allows comparison of type classes and type instances.
        # If a parent type is not specific about its inner type, we infer it as equal:
        # > list[i64] == list[i64] -> True
        # > list[i64] == list[f32] -> False
        # > list[i64] == list      -> True

        # allow comparing object instances to class
        if type(other) is DataTypeClass and issubclass(other, List):
            return True
        if isinstance(other, List):
            if self.inner is None or other.inner is None:
                return True
            else:
                return self.inner == other.inner
        else:
            return False

    def __hash__(self) -> int:
        return hash((self.__class__, self.inner))

    def __repr__(self) -> str:
        class_name = self.__class__.__name__
        return f"{class_name}({self.inner!r})"


class Array(NestedType):
    """
    Fixed length list type.

    Parameters
    ----------
    inner
        The `DataType` of the values within each array.
    width
        The length of the arrays.

    Examples
    --------
    >>> s = pl.Series("a", [[1, 2], [4, 3]], dtype=pl.Array(pl.Int64, 2))
    >>> s
    shape: (2,)
    Series: 'a' [array[i64, 2]]
    [
            [1, 2]
            [4, 3]
    ]
    """

    inner: PolarsDataType | None = None
    width: int

    def __init__(self, inner: PolarsDataType | PythonDataType, width: int):
        self.inner = polars.datatypes.py_type_to_dtype(inner)
        self.width = width

    def __eq__(self, other: PolarsDataType) -> bool:  # type: ignore[override]
        # This equality check allows comparison of type classes and type instances.
        # If a parent type is not specific about its inner type, we infer it as equal:
        # > array[i64] == array[i64] -> True
        # > array[i64] == array[f32] -> False
        # > array[i64] == array      -> True

        # allow comparing object instances to class
        if type(other) is DataTypeClass and issubclass(other, Array):
            return True
        if isinstance(other, Array):
            if self.width != other.width:
                return False
            elif self.inner is None or other.inner is None:
                return True
            else:
                return self.inner == other.inner
        else:
            return False

    def __hash__(self) -> int:
        return hash((self.__class__, self.inner, self.width))

    def __repr__(self) -> str:
        class_name = self.__class__.__name__
        return f"{class_name}({self.inner!r}, width={self.width})"


class Field:
    """
    Definition of a single field within a `Struct` DataType.

    Parameters
    ----------
    name
        The name of the field within its parent `Struct`.
    dtype
        The `DataType` of the field's values.
    """

    __slots__ = ("name", "dtype")
    name: str
    dtype: PolarsDataType

    def __init__(self, name: str, dtype: PolarsDataType):
        self.name = name
        self.dtype = polars.datatypes.py_type_to_dtype(dtype)

    def __eq__(self, other: Field) -> bool:  # type: ignore[override]
        return (self.name == other.name) & (self.dtype == other.dtype)

    def __hash__(self) -> int:
        return hash((self.name, self.dtype))

    def __repr__(self) -> str:
        class_name = self.__class__.__name__
        return f"{class_name}({self.name!r}, {self.dtype})"


class Struct(NestedType):
    """
    Struct composite type.

    Parameters
    ----------
    fields
        The fields that make up the struct. Can be either a sequence of Field
        objects or a mapping of column names to data types.

    Examples
    --------
    Initialize using a dictionary:

    >>> dtype = pl.Struct({"a": pl.Int8, "b": pl.List(pl.String)})
    >>> dtype
    Struct({'a': Int8, 'b': List(String)})

    Initialize using a list of Field objects:

    >>> dtype = pl.Struct([pl.Field("a", pl.Int8), pl.Field("b", pl.List(pl.String))])
    >>> dtype
    Struct({'a': Int8, 'b': List(String)})

    When initializing a Series, Polars can infer a struct data type from the data.

    >>> s = pl.Series([{"a": 1, "b": ["x", "y"]}, {"a": 2, "b": ["z"]}])
    >>> s
    shape: (2,)
    Series: '' [struct[2]]
    [
            {1,["x", "y"]}
            {2,["z"]}
    ]
    >>> s.dtype
    Struct({'a': Int64, 'b': List(String)})
    """

    __slots__ = ("fields",)
    fields: list[Field]

    def __init__(self, fields: Sequence[Field] | SchemaDict):
        if isinstance(fields, Mapping):
            self.fields = [Field(name, dtype) for name, dtype in fields.items()]
        else:
            self.fields = list(fields)

    def __eq__(self, other: PolarsDataType) -> bool:  # type: ignore[override]
        # The comparison allows comparing objects to classes, and specific
        # inner types to those without (eg: inner=None). if one of the
        # arguments is not specific about its inner type we infer it
        # as being equal. (See the List type for more info).
        if isclass(other) and issubclass(other, Struct):
            return True
        elif isinstance(other, Struct):
            return self.fields == other.fields
        else:
            return False

    def __hash__(self) -> int:
        return hash((self.__class__, tuple(self.fields)))

    def __iter__(self) -> Iterator[tuple[str, PolarsDataType]]:
        for fld in self.fields:
            yield fld.name, fld.dtype

    def __reversed__(self) -> Iterator[tuple[str, PolarsDataType]]:
        for fld in reversed(self.fields):
            yield fld.name, fld.dtype

    def __repr__(self) -> str:
        class_name = self.__class__.__name__
        return f"{class_name}({dict(self)})"

    def to_schema(self) -> OrderedDict[str, PolarsDataType]:
        """Return Struct dtype as a schema dict."""
        return OrderedDict(self)
