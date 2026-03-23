"""
Утилиты для работы с базой данных через async/await
"""
import asyncpg
from typing import List, Dict, Any, Optional
from app.config import settings
import logging

logger = logging.getLogger(__name__)


class AsyncDatabaseUtils:
    """Утилиты для прямой работы с PostgreSQL через asyncpg"""
    
    @staticmethod
    def _normalize_url(url: str) -> str:
        """Нормализация URL для asyncpg"""
        if url.startswith("postgres://"):
            url = "postgresql://" + url[11:]
        # Убираем +asyncpg если есть (asyncpg не понимает этот суффикс)
        if "+asyncpg" in url:
            url = url.replace("postgresql+asyncpg://", "postgresql://")
        return url
    
    @classmethod
    async def execute_query(
        cls, 
        query: str, 
        params: Optional[tuple] = None,
        fetch_all: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Выполнить SELECT запрос и вернуть результат как список словарей
        
        Args:
            query: SQL запрос
            params: Параметры для запроса
            fetch_all: True для fetchall(), False для fetchone()
        
        Returns:
            Список словарей с результатами
        """
        database_url = cls._normalize_url(settings.database_url)
        
        conn = await asyncpg.connect(database_url)
        try:
            if params:
                if fetch_all:
                    rows = await conn.fetch(query, *params)
                else:
                    row = await conn.fetchrow(query, *params)
                    rows = [row] if row else []
            else:
                if fetch_all:
                    rows = await conn.fetch(query)
                else:
                    row = await conn.fetchrow(query)
                    rows = [row] if row else []
            
            return [dict(row) for row in rows]
        finally:
            await conn.close()
    
    @classmethod
    async def execute_ddl(cls, query: str, params: Optional[tuple] = None) -> None:
        """
        Выполнить DDL запрос (CREATE, DROP, ALTER) в транзакции
        
        Args:
            query: DDL запрос
            params: Параметры для запроса
        """
        database_url = cls._normalize_url(settings.database_url)
        
        conn = await asyncpg.connect(database_url)
        try:
            async with conn.transaction():
                if params:
                    await conn.execute(query, *params)
                else:
                    await conn.execute(query)
                logger.info(f"DDL executed successfully: {query[:100]}...")
        finally:
            await conn.close()
    
    @classmethod
    async def execute_dml(
        cls, 
        query: str, 
        params: Optional[tuple] = None,
        return_count: bool = False
    ) -> Optional[int]:
        """
        Выполнить DML запрос (INSERT, UPDATE, DELETE) в транзакции
        
        Args:
            query: DML запрос
            params: Параметры для запроса
            return_count: Вернуть количество затронутых строк
        
        Returns:
            Количество затронутых строк если return_count=True
        """
        database_url = cls._normalize_url(settings.database_url)
        
        conn = await asyncpg.connect(database_url)
        try:
            async with conn.transaction():
                if params:
                    result = await conn.execute(query, *params)
                else:
                    result = await conn.execute(query)
                
                if return_count:
                    # Парсим результат типа "UPDATE 5" -> 5
                    return int(result.split()[-1]) if result.split() else 0
                return None
        finally:
            await conn.close()
    
    @classmethod
    async def bulk_insert(
        cls,
        table: str,
        columns: List[str],
        data: List[tuple],
        on_conflict: str = "DO NOTHING"
    ) -> int:
        """
        Массовая вставка данных
        
        Args:
            table: Название таблицы
            columns: Список колонок
            data: Список кортежей с данными
            on_conflict: Действие при конфликте
        
        Returns:
            Количество вставленных строк
        """
        if not data:
            return 0
        
        placeholders = ", ".join([f"${i+1}" for i in range(len(columns))])
        columns_str = ", ".join(columns)
        
        query = f"""
            INSERT INTO {table} ({columns_str}) 
            VALUES ({placeholders}) 
            ON CONFLICT {on_conflict}
        """
        
        database_url = cls._normalize_url(settings.database_url)
        
        conn = await asyncpg.connect(database_url)
        try:
            async with conn.transaction():
                result = await conn.executemany(query, data)
                return len(data)  # asyncpg executemany не возвращает точное количество
        finally:
            await conn.close()


# Примеры использования в сервисах
class DatabaseService:
    """Примеры методов для использования в сервисах"""
    
    @staticmethod
    async def get_user_stats() -> Dict[str, Any]:
        """Получить статистику пользователей"""
        query = """
            SELECT 
                role,
                COUNT(*) as count,
                COUNT(CASE WHEN is_active THEN 1 END) as active_count
            FROM users 
            GROUP BY role
            ORDER BY role
        """
        
        rows = await AsyncDatabaseUtils.execute_query(query)
        return {
            "total_users": sum(row["count"] for row in rows),
            "by_role": rows
        }
    
    @staticmethod
    async def get_orders_summary(user_id: str) -> Dict[str, Any]:
        """Получить сводку заказов пользователя"""
        query = """
            SELECT 
                status,
                COUNT(*) as count,
                COALESCE(SUM(total_amount), 0) as total_amount
            FROM orders 
            WHERE user_id = $1
            GROUP BY status
            ORDER BY status
        """
        
        rows = await AsyncDatabaseUtils.execute_query(query, (user_id,))
        return {
            "orders_by_status": rows,
            "total_orders": sum(row["count"] for row in rows)
        }
    
    @staticmethod
    async def cleanup_old_data(days: int = 90) -> int:
        """Очистка старых данных"""
        query = """
            DELETE FROM wallet_transactions 
            WHERE created_at < NOW() - INTERVAL '%s days'
            AND type = 'MONTHLY_RESET'
        """
        
        count = await AsyncDatabaseUtils.execute_dml(
            query, 
            (days,), 
            return_count=True
        )
        
        logger.info(f"Cleaned up {count} old wallet transactions")
        return count or 0