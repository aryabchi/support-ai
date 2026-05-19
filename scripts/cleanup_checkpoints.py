"""
Скрипт очистки старых чекпоинтов.
Запуск: python scripts/cleanup_checkpoints.py --keep 50
"""

import sys
import asyncpg
import asyncio
import argparse
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app.config import get_settings


async def cleanup_checkpoints(db_url: str, keep: int = 50):
    """
    Удаляет старые чекпоинты, оставляя последние N на каждую сессию.
    """
    conn_url = str(db_url).replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(conn_url)

    try:
        async with conn.transaction():
            # 1. Удаляем старые чекпоинты из основной таблицы
            result = await conn.execute(f"""
                DELETE FROM checkpoints
                WHERE (thread_id, checkpoint_ns, checkpoint_id) IN (
                    SELECT thread_id, checkpoint_ns, checkpoint_id
                    FROM (
                        SELECT
                            thread_id,
                            checkpoint_ns,
                            checkpoint_id,
                            ROW_NUMBER() OVER (
                                PARTITION BY thread_id, checkpoint_ns
                                ORDER BY checkpoint_id DESC
                            ) as rn
                        FROM checkpoints
                    ) ranked
                    WHERE rn > {keep}
                )
            """)

            # 2. Каскадная очистка checkpoint_writes
            await conn.execute("""
                DELETE FROM checkpoint_writes
                WHERE (thread_id, checkpoint_ns, checkpoint_id) NOT IN (
                    SELECT thread_id, checkpoint_ns, checkpoint_id FROM checkpoints
                )
            """)

            # 3. Каскадная очистка checkpoint_blobs
            await conn.execute("""
                DELETE FROM checkpoint_blobs
                WHERE (thread_id, checkpoint_ns) NOT IN (
                    SELECT thread_id, checkpoint_ns FROM checkpoints
                )
            """)

            total = 0
            if result:
                parts = result.split()
                if len(parts) >= 2:
                    total += int(parts[-1])

            return total

    finally:
        await conn.close()


async def main():
    parser = argparse.ArgumentParser(description="Очистка старых чекпоинтов LangGraph")
    parser.add_argument(
        "--keep", type=int, default=50, help="Сколько чекпоинтов сохранить на сессию"
    )
    args = parser.parse_args()

    settings = get_settings()
    db_url = str(settings.DATABASE_URL)

    print(f"Очистка чекпоинтов LangGraph (оставить последние {args.keep} на сессию)...")
    print(f"База данных: {db_url.split('@')[-1].split('/')[0]}")

    try:
        deleted = await cleanup_checkpoints(db_url, args.keep)
        print(f"Удалено записей: {deleted}")
        return 0
    except Exception as e:
        print(f"Ошибка: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
