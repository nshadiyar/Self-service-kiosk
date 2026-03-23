"""
Примеры правильной работы с PostgreSQL через async/await + asyncpg
"""
import asyncio
import asyncpg
from typing import List, Dict, Any
import os


async def example_select_with_asyncpg():
    """Пример SELECT запроса с возвратом списка словарей"""
    database_url = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/bromart_db")
    
    # Нормализация URL для asyncpg (убираем postgres:// -> postgresql://)
    if database_url.startswith("postgres://"):
        database_url = "postgresql://" + database_url[11:]
    
    # Async подключение
    conn = await asyncpg.connect(database_url)
    try:
        # SELECT запрос - возвращаем список словарей
        rows = await conn.fetch("SELECT id, email, full_name, role FROM users LIMIT 10")
        
        # Конвертируем Record в dict
        result: List[Dict[str, Any]] = [dict(row) for row in rows]
        return result
    finally:
        await conn.close()


async def example_ddl_with_transaction():
    """Пример DDL операций с транзакцией"""
    database_url = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/bromart_db")
    
    if database_url.startswith("postgres://"):
        database_url = "postgresql://" + database_url[11:]
    
    conn = await asyncpg.connect(database_url)
    try:
        # DDL операции в транзакции
        async with conn.transaction():
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS temp_test (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(100),
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
            
            await conn.execute("INSERT INTO temp_test (name) VALUES ($1)", "Test User")
            
            # Можем откатить если нужно
            # raise Exception("Rollback test")
    finally:
        await conn.close()


async def example_with_sqlalchemy_async():
    """Пример через SQLAlchemy async (рекомендуемый для проекта)"""
    from app.database import AsyncSessionLocal
    from app.models import User
    from sqlalchemy import select, text
    
    async with AsyncSessionLocal() as session:
        # Вариант 1: Через ORM
        stmt = select(User).limit(10)
        result = await session.execute(stmt)
        users = result.scalars().all()
        
        # Конвертируем в словари
        users_dict = [
            {
                "id": str(user.id),
                "email": user.email,
                "full_name": user.full_name,
                "role": user.role.value,
                "is_active": user.is_active
            }
            for user in users
        ]
        
        # Вариант 2: Raw SQL через text()
        raw_result = await session.execute(
            text("SELECT id, email, full_name FROM users WHERE is_active = :active LIMIT :limit"),
            {"active": True, "limit": 5}
        )
        raw_rows = raw_result.fetchall()
        
        # Конвертируем Row в dict
        raw_dict = [dict(row._mapping) for row in raw_rows]
        
        return users_dict, raw_dict


async def example_bulk_operations():
    """Пример массовых операций"""
    database_url = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/bromart_db")
    
    if database_url.startswith("postgres://"):
        database_url = "postgresql://" + database_url[11:]
    
    conn = await asyncpg.connect(database_url)
    try:
        # Массовая вставка
        data_to_insert = [
            ("user1@example.com", "User One"),
            ("user2@example.com", "User Two"),
            ("user3@example.com", "User Three"),
        ]
        
        async with conn.transaction():
            await conn.executemany(
                "INSERT INTO temp_test (email, name) VALUES ($1, $2) ON CONFLICT DO NOTHING",
                data_to_insert
            )
        
        # Массовое чтение
        rows = await conn.fetch("SELECT * FROM temp_test ORDER BY id")
        return [dict(row) for row in rows]
    finally:
        await conn.close()


async def example_connection_pool():
    """Пример с connection pool (для высоконагруженных приложений)"""
    database_url = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/bromart_db")
    
    if database_url.startswith("postgres://"):
        database_url = "postgresql://" + database_url[11:]
    
    # Создаём pool подключений
    pool = await asyncpg.create_pool(
        database_url,
        min_size=2,
        max_size=10,
        command_timeout=60
    )
    
    try:
        # Используем подключение из pool
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT COUNT(*) as total_users FROM users")
            return dict(rows[0])
    finally:
        await pool.close()


# Пример использования в FastAPI endpoint
async def get_users_endpoint():
    """Пример endpoint для FastAPI"""
    try:
        users = await example_select_with_asyncpg()
        return {"success": True, "data": users, "message": "Users retrieved successfully"}
    except Exception as e:
        return {"success": False, "data": None, "message": f"Error: {str(e)}"}


if __name__ == "__main__":
    # Тестирование примеров
    async def main():
        print("1. Testing SELECT with asyncpg...")
        try:
            users = await example_select_with_asyncpg()
            print(f"Found {len(users)} users")
        except Exception as e:
            print(f"Error: {e}")
        
        print("\n2. Testing SQLAlchemy async...")
        try:
            users_orm, users_raw = await example_with_sqlalchemy_async()
            print(f"ORM: {len(users_orm)} users, Raw: {len(users_raw)} users")
        except Exception as e:
            print(f"Error: {e}")
    
    asyncio.run(main())