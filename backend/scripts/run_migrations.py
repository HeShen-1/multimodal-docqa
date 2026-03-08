from alembic.config import main
from sqlalchemy import create_engine, inspect

from app.config import get_settings
from app.models.base import Base
from app.models.conversation import Conversation, Message
from app.models.document_db import Document
from app.models.share import ShareLink
from app.models.tag import Tag, document_tags
from app.models.user import RefreshToken, TokenBlacklist, User


def bootstrap_base_tables() -> None:
    settings = get_settings()
    sync_url = settings.database_url.replace("postgresql+asyncpg", "postgresql+psycopg2", 1)
    engine = create_engine(sync_url, future=True)

    required_tables = {
        "users",
        "refresh_tokens",
        "token_blacklist",
        "documents",
        "tags",
        "document_tags",
        "share_links",
        "conversations",
        "messages",
    }

    try:
        with engine.begin() as connection:
            existing_tables = set(inspect(connection).get_table_names())
            if required_tables - existing_tables:
                Base.metadata.create_all(
                    bind=connection,
                    tables=[
                        User.__table__,
                        RefreshToken.__table__,
                        TokenBlacklist.__table__,
                        Document.__table__,
                        Tag.__table__,
                        document_tags,
                        ShareLink.__table__,
                        Conversation.__table__,
                        Message.__table__,
                    ],
                    checkfirst=True,
                )
    finally:
        engine.dispose()


if __name__ == "__main__":
    bootstrap_base_tables()
    raise SystemExit(main(argv=["-c", "alembic.ini", "upgrade", "head"]))
