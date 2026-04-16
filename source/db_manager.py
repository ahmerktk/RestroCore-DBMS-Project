import psycopg2
from psycopg2 import pool

# Database configuration
DB_CONFIG = {
    "dbname": "restaurant_pos",
    "user": "postgres",
    "password": "your_password",
    "host": "localhost",
    "port": "5432"
}

class DatabaseManager:
    _pool = None

    @classmethod
    def initialize_pool(cls):
        """Initializes the connection pool once."""
        if cls._pool is None:
            cls._pool = psycopg2.pool.SimpleConnectionPool(1, 10, **DB_CONFIG)
            print("Connection pool initialized.")

    def __init__(self):
        self.conn = self._pool.getconn()
        self.cursor = self.conn.cursor()

    def execute_query(self, query, params=None):
        try:
            self.cursor.execute(query, params)
            self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            print(f"Query error: {e}")
            raise e

    def fetch_all(self, query, params=None):
        self.cursor.execute(query, params)
        return self.cursor.fetchall()

    def release(self):
        """Returns the connection to the pool instead of closing it."""
        self.cursor.close()
        self._pool.putconn(self.conn)

# --- Initialization ---
DatabaseManager.initialize_pool()

# Example usage function
def add_new_order(table_number):
    db = DatabaseManager()
    try:
        query = "INSERT INTO orders (table_number) VALUES (%s) RETURNING order_id"
        db.execute_query(query, (table_number,))
        print(f"Order added successfully for Table {table_number}")
    finally:
        db.release() # Very important: always release!