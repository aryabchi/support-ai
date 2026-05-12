from sqlalchemy.orm import DeclarativeBase

# Конвенции для имён объектов в БД (опционально, но рекомендуется)
# Например, индексы будут называться: ix_table_column
convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """
    Базовый класс для всех моделей SQLAlchemy.

    Все модели должны наследоваться от этого класса.
    """

    pass


Base.metadata.naming_convention = convention
