"""SQLite helper functions for the eSewa FastAPI e‑commerce site.

This module centralises database access and schema management for the
e‑commerce application. It defines tables for products, orders and
order_items and exposes CRUD operations for products and orders. An
order includes a transaction UUID for payment integration and a
status column to track its lifecycle (INITIATED, COMPLETED, FAILED).
"""

import sqlite3
import uuid
from pathlib import Path
from typing import List, Dict, Tuple

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "db.sqlite"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create the database schema and seed with initial products."""
    conn = get_connection()
    cur = conn.cursor()
    # Products table
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            price REAL NOT NULL,
            image_url TEXT NOT NULL
        )
        """
    )
    # Orders table
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            transaction_uuid TEXT NOT NULL UNIQUE,
            customer_name TEXT NOT NULL,
            customer_email TEXT,
            customer_phone TEXT,
            customer_address TEXT,
            amount REAL NOT NULL,
            tax_amount REAL NOT NULL,
            service_charge REAL NOT NULL,
            delivery_charge REAL NOT NULL,
            total_amount REAL NOT NULL,
            status TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    # Order items table
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            price REAL NOT NULL,
            FOREIGN KEY(order_id) REFERENCES orders(id) ON DELETE CASCADE,
            FOREIGN KEY(product_id) REFERENCES products(id)
        )
        """
    )
    # Seed products if empty
    count = cur.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    if count == 0:
        products = [
            ("Classic Aviator Sunglasses", "Timeless aviator frames with UV400 protection and mirrored lenses.", 59.99, "/static/images/aviator.png"),
            ("Retro Round Sunglasses", "Vintage-inspired round sunglasses with polarized lenses.", 45.50, "/static/images/retro.png"),
            ("Sporty Wraparound Shades", "Durable wraparound sunglasses designed for outdoor sports.", 39.00, "/static/images/sporty.png"),
            ("Lucky Purchase", "Try your luck! Mystery sunglasses at an amazing price.", 1.00, "/static/images/lucky.png"),
        ]
        cur.executemany(
            "INSERT INTO products (name, description, price, image_url) VALUES (?,?,?,?)",
            products,
        )
    conn.commit()
    conn.close()


def get_products() -> List[Dict]:
    conn = get_connection()
    cur = conn.cursor()
    rows = cur.execute("SELECT id, name, description, price, image_url FROM products").fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_product(product_id: int) -> Dict:
    conn = get_connection()
    cur = conn.cursor()
    row = cur.execute(
        "SELECT id, name, description, price, image_url FROM products WHERE id = ?",
        (product_id,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def create_product(name: str, description: str, price: float, image_url: str) -> int:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO products (name, description, price, image_url) VALUES (?,?,?,?)",
        (name, description, price, image_url),
    )
    product_id = cur.lastrowid
    conn.commit()
    conn.close()
    return product_id


def update_product(product_id: int, name: str, description: str, price: float, image_url: str) -> None:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE products SET name=?, description=?, price=?, image_url=? WHERE id = ?",
        (name, description, price, image_url, product_id),
    )
    conn.commit()
    conn.close()


def delete_product(product_id: int) -> None:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM products WHERE id = ?", (product_id,))
    conn.commit()
    conn.close()


def create_order(
    customer_name: str,
    customer_email: str,
    customer_phone: str,
    customer_address: str,
    cart: List[Dict[str, int]],
    tax_amount: float,
    service_charge: float,
    delivery_charge: float,
) -> Dict:
    """Create an order and return its row as a dict."""
    conn = get_connection()
    cur = conn.cursor()
    # Compute subtotal
    amount = 0.0
    for item in cart:
        pid = item.get("productId")
        qty = item.get("quantity", 1)
        row = cur.execute("SELECT price FROM products WHERE id = ?", (pid,)).fetchone()
        if row is None:
            conn.close()
            raise ValueError(f"Product {pid} not found")
        amount += row["price"] * qty
    amount = round(amount, 2)
    total_amount = round(amount + tax_amount + service_charge + delivery_charge, 2)
    transaction_uuid = str(uuid.uuid4())
    # Insert into orders
    cur.execute(
        "INSERT INTO orders (transaction_uuid, customer_name, customer_email, customer_phone, customer_address, amount, tax_amount, service_charge, delivery_charge, total_amount, status) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (
            transaction_uuid,
            customer_name,
            customer_email,
            customer_phone,
            customer_address,
            amount,
            tax_amount,
            service_charge,
            delivery_charge,
            total_amount,
            "INITIATED",
        ),
    )
    order_id = cur.lastrowid
    # Insert order items
    for item in cart:
        pid = item.get("productId")
        qty = item.get("quantity", 1)
        price_row = cur.execute("SELECT price FROM products WHERE id = ?", (pid,)).fetchone()
        price = price_row["price"]
        cur.execute(
            "INSERT INTO order_items (order_id, product_id, quantity, price) VALUES (?,?,?,?)",
            (order_id, pid, qty, price),
        )
    conn.commit()
    # Retrieve inserted order with transaction_uuid
    order_row = cur.execute(
        "SELECT * FROM orders WHERE id = ?",
        (order_id,),
    ).fetchone()
    conn.close()
    return dict(order_row)


def get_order_by_id(order_id: int) -> Dict:
    conn = get_connection()
    cur = conn.cursor()
    row = cur.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_order_by_uuid(transaction_uuid: str) -> Dict:
    conn = get_connection()
    cur = conn.cursor()
    row = cur.execute("SELECT * FROM orders WHERE transaction_uuid = ?", (transaction_uuid,)).fetchone()
    conn.close()
    return dict(row) if row else None


def update_order_status(transaction_uuid: str, status: str) -> None:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE orders SET status = ? WHERE transaction_uuid = ?",
        (status, transaction_uuid),
    )
    conn.commit()
    conn.close()


def get_orders() -> List[Dict]:
    conn = get_connection()
    cur = conn.cursor()
    rows = cur.execute(
        "SELECT * FROM orders ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]