-- 1. Employees
CREATE TABLE employees (
    employee_id SERIAL PRIMARY KEY,
    name VARCHAR(100),
    role VARCHAR(50),
    username VARCHAR(50) UNIQUE,
    password VARCHAR(100)
);

-- 2. Suppliers
CREATE TABLE suppliers (
    supplier_id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    contact_email VARCHAR(100),
    phone_number VARCHAR(20)
);

-- 3. Menu Items
CREATE TABLE menu_items (
    item_id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    price DECIMAL(10, 2) NOT NULL CHECK (price >= 0),
    stock_level INT DEFAULT 0,
    supplier_id INT REFERENCES suppliers(supplier_id),
    image_path VARCHAR(255)
);

-- 4. Orders
CREATE TABLE orders (
    order_id SERIAL PRIMARY KEY,
    table_number INT NOT NULL,
    order_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    total_amount DECIMAL(10, 2) DEFAULT 0.00
);

-- 5. Order Items (Bridge Table)
CREATE TABLE order_items (
    order_item_id SERIAL PRIMARY KEY,
    order_id INT REFERENCES orders(order_id) ON DELETE CASCADE,
    item_id INT REFERENCES menu_items(item_id),
    quantity INT NOT NULL CHECK (quantity > 0)
);

-- 6. Supply Orders
CREATE TABLE supply_orders (
    supply_order_id SERIAL PRIMARY KEY,
    supplier_id INT REFERENCES suppliers(supplier_id),
    order_date DATE DEFAULT CURRENT_DATE,
    total_cost DECIMAL(10, 2) DEFAULT 0.00
);

-- 7. Supply Order Items
CREATE TABLE supply_order_items (
    supply_item_id SERIAL PRIMARY KEY,
    supply_order_id INT REFERENCES supply_orders(supply_order_id) ON DELETE CASCADE,
    item_id INT REFERENCES menu_items(item_id),
    quantity_received INT NOT NULL,
    unit_cost DECIMAL(10, 2) NOT NULL
);

-- 8. View
CREATE OR REPLACE VIEW view_supplier_inventory AS
SELECT s.name AS supplier_name, m.name AS item_name, m.stock_level, m.price
FROM suppliers s
JOIN menu_items m ON s.supplier_id = m.supplier_id;