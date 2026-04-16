CREATE OR REPLACE FUNCTION check_stock_before_order()
RETURNS TRIGGER AS $$
DECLARE current_stock INT;
BEGIN
    SELECT stock_level INTO current_stock FROM menu_items WHERE item_id = NEW.item_id;
    IF current_stock < NEW.quantity THEN
        RAISE EXCEPTION 'Insufficient stock! Only % units left.', current_stock;
    END IF;
    -- Deduct stock automatically here
    UPDATE menu_items SET stock_level = stock_level - NEW.quantity WHERE item_id = NEW.item_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_check_stock
BEFORE INSERT ON order_items
FOR EACH ROW EXECUTE FUNCTION check_stock_before_order();

CREATE OR REPLACE FUNCTION update_order_total()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE orders SET total_amount = (
        SELECT SUM(oi.quantity * m.price)
        FROM order_items oi
        JOIN menu_items m ON oi.item_id = m.item_id
        WHERE oi.order_id = NEW.order_id
    ) WHERE order_id = NEW.order_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_update_total
AFTER INSERT OR UPDATE ON order_items
FOR EACH ROW EXECUTE FUNCTION update_order_total();

CREATE OR REPLACE FUNCTION update_stock_after_supply()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE menu_items SET stock_level = stock_level + NEW.quantity_received WHERE item_id = NEW.item_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_restock_inventory
AFTER INSERT ON supply_order_items
FOR EACH ROW EXECUTE FUNCTION update_stock_after_supply();


INSERT INTO suppliers (name, contact_email, phone_number) VALUES ('Fresh Farms Ltd', 'sales@freshfarms.com', '555-0101');
INSERT INTO menu_items (name, price, stock_level, supplier_id) VALUES ('Fillet Burger', 15.50, 50, 1);
INSERT INTO employees (name, role, username, password) VALUES ('Alice Johnson', 'Manager', 'alice_mgr', 'password123');