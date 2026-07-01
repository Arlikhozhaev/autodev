"""PostgreSQL-compatible SQLAlchemy enum columns."""
import enum
from typing import Type

from sqlalchemy import Enum as SAEnum


def pg_enum(enum_cls: Type[enum.Enum], name: str) -> SAEnum:
    """Bind Python enums to existing Postgres ENUM types (by value, not name)."""
    return SAEnum(
        enum_cls,
        name=name,
        values_callable=lambda members: [member.value for member in members],
        validate_strings=True,
    )
