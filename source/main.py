import ttkbootstrap as tb
from ttkbootstrap.constants import *
from ttkbootstrap.dialogs import Messagebox
import psycopg2
import os
from datetime import datetime
from cloud_service import sync_to_cloud, update_cloud_status   # ← added update_cloud_status

try:
    from PIL import Image, ImageTk
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

# ─── Database configuration ──────────────────────────────────────────────────
DB_CONFIG = {
    "dbname": "restaurant_pos",
    "user": "postgres",
    "password": "umar1234gul",
    "host": "localhost",
    "port": "5432"
}


class RestroCoreApp:
    def __init__(self, root):
        self.root = root
        self.root.title("RestroCore - Advanced Management Dashboard")
        self.root.geometry("1300x850")
        self.root.position_center()

        # State Variables
        self.current_user    = None
        self.placeholder_img = None
        self.menu_image_map  = {}
        self.menu_data       = {}
        self.order_cart      = []
        self.thumb_refs      = {}
        self.active_bill_id  = None

        # Database Connection
        try:
            self.conn   = psycopg2.connect(**DB_CONFIG)
            self.cursor = self.conn.cursor()
        except Exception as e:
            Messagebox.show_error(f"Database Connection Failed:\n{e}", "Database Error")
            self.root.destroy()
            return

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.build_login_screen()

    # ═══════════════════════════════ LOGIN ═══════════════════════════════════
    def build_login_screen(self):
        for w in self.root.winfo_children():
            w.destroy()

        self.login_frame = tb.Frame(self.root)
        self.login_frame.pack(expand=True, padx=40, pady=40)

        tb.Label(self.login_frame, text="RestroCore",
                 font=("Helvetica", 36, "bold"), bootstyle=INFO).pack(pady=10)
        tb.Label(self.login_frame, text="Restaurant Management System",
                 font=("Helvetica", 12)).pack(pady=5)

        self.ent_user = tb.Entry(self.login_frame, font=("Helvetica", 12), width=30)
        self.ent_user.insert(0, "alice_mgr")
        self.ent_user.pack(pady=10)

        self.ent_pass = tb.Entry(self.login_frame, font=("Helvetica", 12), width=30, show="*")
        self.ent_pass.insert(0, "password123")
        self.ent_pass.pack(pady=10)

        tb.Button(self.login_frame, text="Login", bootstyle=SUCCESS,
                  width=28, command=self.attempt_login).pack(pady=20)

        self.root.bind('<Return>', lambda e: self.attempt_login())

    def attempt_login(self):
        username = self.ent_user.get()
        password = self.ent_pass.get()

        try:
            self.cursor.execute(
                "SELECT employee_id, name, role FROM employees "
                "WHERE username=%s AND password=%s", (username, password))
            user = self.cursor.fetchone()

            if user:
                self.current_user = {"id": user[0], "name": user[1], "role": user[2]}
                self.root.unbind('<Return>')
                self._log_activity(user[0], "LOGIN", f"User '{user[1]}' logged in.")
                self.build_main_dashboard()
            else:
                Messagebox.show_error("Invalid username or password.", "Login Failed")
        except Exception as e:
            self._safe_rollback()
            Messagebox.show_error(f"Login Error: {e}", "Error")

    # ═══════════════════════════════ DASHBOARD ═══════════════════════════════
    def build_main_dashboard(self):
        for w in self.root.winfo_children():
            w.destroy()

        header = tb.Frame(self.root, bootstyle=DARK)
        header.pack(fill=X)
        tb.Label(header,
                 text=f"👤 {self.current_user['name']} | Role: {self.current_user['role']}",
                 font=("Helvetica", 12), bootstyle=INVERSE).pack(side=LEFT, padx=15, pady=10)
        tb.Button(header, text="Logout", bootstyle=(DANGER, OUTLINE),
                  command=self.logout).pack(side=RIGHT, padx=15, pady=10)

        self.tab_control = tb.Notebook(self.root, bootstyle=INFO)
        self.tab_control.pack(expand=True, fill=BOTH, padx=20, pady=20)

        role = self.current_user['role'].lower()

        # ── Tabs visible to all roles ──
        self.tab_menu    = tb.Frame(self.tab_control)
        self.tab_orders  = tb.Frame(self.tab_control)
        self.tab_billing = tb.Frame(self.tab_control)

        self.tab_control.add(self.tab_menu,    text='📋 Menu & Inventory')
        self.tab_control.add(self.tab_orders,  text='🍔 Place Order')
        self.tab_control.add(self.tab_billing, text='💳 Billing')

        # ── Manager-only tabs ──
        if role == 'manager':
            self.tab_stock  = tb.Frame(self.tab_control)
            self.tab_staff  = tb.Frame(self.tab_control)
            self.tab_actlog = tb.Frame(self.tab_control)
            self.tab_control.add(self.tab_stock,  text='📦 Stock Management')
            self.tab_control.add(self.tab_staff,  text='👥 Staff Management')
            self.tab_control.add(self.tab_actlog, text='📜 Activity Log')
            self.setup_stock_tab()
            self.setup_staff_tab()
            self.setup_activity_log_tab()

        # ── Chef-only tab ──
        if role == 'chef':
            self.tab_kitchen = tb.Frame(self.tab_control)
            self.tab_control.add(self.tab_kitchen, text='🍳 Kitchen Orders')
            self.setup_kitchen_tab()

        self.setup_menu_tab()
        self.setup_order_tab()
        self.setup_billing_tab()

    # ═══════════════════════════════ MENU TAB ════════════════════════════════
    def setup_menu_tab(self):
        container = tb.Frame(self.tab_menu)
        container.pack(fill=BOTH, expand=True)

        left_frame = tb.Frame(container)
        left_frame.pack(side=LEFT, fill=BOTH, expand=True)

        cols = ('id', 'name', 'price', 'stock')
        self.tree_menu = tb.Treeview(left_frame, columns=cols,
                                     show='headings', bootstyle=PRIMARY)
        for c in cols:
            self.tree_menu.heading(c, text=c.capitalize())
        self.tree_menu.column('id',    width=50,  anchor=CENTER)
        self.tree_menu.column('name',  width=250)
        self.tree_menu.column('price', width=80)
        self.tree_menu.column('stock', width=80)
        self.tree_menu.pack(fill=BOTH, expand=True)
        self.tree_menu.bind('<<TreeviewSelect>>', self.on_menu_select)

        tb.Button(left_frame, text="↻ Refresh List", bootstyle=INFO,
                  command=self.load_menu_data).pack(pady=10)

        self.preview_frame = tb.LabelFrame(container, text=" Item Preview ")
        self.preview_frame.pack(side=RIGHT, fill=Y, padx=10, pady=20)

        self.img_label = tb.Label(self.preview_frame,
                                  text="Select an item\nto view image",
                                  font=("Helvetica", 10))
        self.img_label.pack(expand=True, fill=BOTH, pady=(0, 20), padx=10)

        self.load_menu_data()

    def load_menu_data(self):
        for i in self.tree_menu.get_children():
            self.tree_menu.delete(i)

        try:
            self.cursor.execute(
                "SELECT item_id, name, price, stock_level, image_path "
                "FROM menu_items ORDER BY item_id")
            rows = self.cursor.fetchall()
        except psycopg2.Error as e:
            self._safe_rollback()
            Messagebox.show_error(f"Error loading menu:\n{e}", "Database Error")
            return

        self.menu_data = {}
        for item_id, name, price, stock, image_path in rows:
            self.menu_image_map[str(item_id)] = image_path
            self.menu_data[item_id] = {
                "name": name, "price": price,
                "stock": stock or 0, "image_path": image_path
            }
            self.tree_menu.insert('', END, values=(item_id, name, price, stock))

        if hasattr(self, '_order_tab_ready'):
            self.build_food_cards()

        if hasattr(self, 'tree_stock'):
            self._load_stock_tree()

    def on_menu_select(self, event):
        sel = self.tree_menu.selection()
        if not sel:
            return

        item_id = str(self.tree_menu.item(sel[0])['values'][0])
        img_path = self.menu_image_map.get(item_id)

        if HAS_PIL and img_path and os.path.exists(img_path):
            try:
                img = Image.open(img_path).resize((280, 280), Image.Resampling.LANCZOS)
                self.placeholder_img = ImageTk.PhotoImage(img)
                self.img_label.config(image=self.placeholder_img, text="")
                return
            except Exception:
                pass

        self.img_label.config(image='', text="No Image Available")

    # ═══════════════════════════ STOCK MANAGEMENT TAB (Manager only) ═════════
    def setup_stock_tab(self):
        top = tb.Frame(self.tab_stock)
        top.pack(fill=X, padx=10, pady=10)

        tb.Label(top, text="Stock Management",
                 font=("Helvetica", 16, "bold"), bootstyle=INFO).pack(side=LEFT)
        tb.Button(top, text="↻ Refresh", bootstyle=INFO,
                  command=self._load_stock_tree).pack(side=RIGHT)

        cols = ('id', 'name', 'price', 'stock')
        self.tree_stock = tb.Treeview(self.tab_stock, columns=cols,
                                      show='headings', bootstyle=PRIMARY)
        self.tree_stock.heading('id',    text='ID')
        self.tree_stock.heading('name',  text='Item Name')
        self.tree_stock.heading('price', text='Price')
        self.tree_stock.heading('stock', text='Current Stock')
        self.tree_stock.column('id',    width=50,  anchor=CENTER)
        self.tree_stock.column('name',  width=280)
        self.tree_stock.column('price', width=90,  anchor=CENTER)
        self.tree_stock.column('stock', width=120, anchor=CENTER)
        self.tree_stock.pack(fill=BOTH, expand=True, padx=10, pady=(0, 10))

        update_frame = tb.LabelFrame(self.tab_stock, text=" Update Stock Level ")
        update_frame.pack(fill=X, padx=10, pady=10)

        row1 = tb.Frame(update_frame)
        row1.pack(fill=X, padx=10, pady=(10, 4))

        tb.Label(row1, text="Selected Item:", font=("Helvetica", 11)).pack(side=LEFT, padx=(0, 6))
        self.lbl_stock_item = tb.Label(row1, text="(click a row above)",
                                       font=("Helvetica", 11, "italic"), bootstyle=WARNING)
        self.lbl_stock_item.pack(side=LEFT)

        row2 = tb.Frame(update_frame)
        row2.pack(fill=X, padx=10, pady=(4, 10))

        tb.Label(row2, text="Add Quantity:", font=("Helvetica", 11)).pack(side=LEFT, padx=(0, 6))
        self.ent_stock_add = tb.Entry(row2, width=10, font=("Helvetica", 11))
        self.ent_stock_add.pack(side=LEFT, padx=(0, 10))

        tb.Label(row2, text="Set Absolute:", font=("Helvetica", 11)).pack(side=LEFT, padx=(0, 6))
        self.ent_stock_set = tb.Entry(row2, width=10, font=("Helvetica", 11))
        self.ent_stock_set.pack(side=LEFT, padx=(0, 20))

        tb.Button(row2, text="➕ Add Stock", bootstyle=SUCCESS,
                  command=self._add_stock).pack(side=LEFT, padx=4)
        tb.Button(row2, text="✏️ Set Stock", bootstyle=WARNING,
                  command=self._set_stock).pack(side=LEFT, padx=4)

        self.tree_stock.bind('<<TreeviewSelect>>', self._on_stock_select)
        self._selected_stock_id = None
        self._load_stock_tree()

    def _load_stock_tree(self):
        if not hasattr(self, 'tree_stock'):
            return
        for i in self.tree_stock.get_children():
            self.tree_stock.delete(i)
        try:
            self.cursor.execute(
                "SELECT item_id, name, price, stock_level FROM menu_items ORDER BY item_id")
            for row in self.cursor.fetchall():
                self.tree_stock.insert('', END, values=row)
        except psycopg2.Error as e:
            self._safe_rollback()
            Messagebox.show_error(f"Error loading stock:\n{e}", "DB Error")

    def _on_stock_select(self, event):
        sel = self.tree_stock.selection()
        if not sel:
            return
        vals = self.tree_stock.item(sel[0])['values']
        self._selected_stock_id   = vals[0]
        self._selected_stock_name = vals[1]
        self.lbl_stock_item.config(text=f"{vals[1]}  (current stock: {vals[3]})")

    def _add_stock(self):
        if not self._selected_stock_id:
            Messagebox.show_warning("Please select an item first.", "No Item Selected")
            return
        val = self.ent_stock_add.get().strip()
        if not val.isdigit() or int(val) <= 0:
            Messagebox.show_warning("Enter a positive integer to add.", "Invalid Input")
            return
        qty = int(val)
        try:
            self.cursor.execute(
                "UPDATE menu_items SET stock_level = stock_level + %s WHERE item_id = %s",
                (qty, self._selected_stock_id))
            self.conn.commit()
            self._log_activity(
                self.current_user['id'], "STOCK_ADD",
                f"Added {qty} units to '{self._selected_stock_name}' (item_id={self._selected_stock_id}).")
            Messagebox.show_info(f"Added {qty} units to '{self._selected_stock_name}'.", "Stock Updated")
            self.ent_stock_add.delete(0, END)
            self._load_stock_tree()
            self.load_menu_data()
        except psycopg2.Error as e:
            self._safe_rollback()
            Messagebox.show_error(f"Failed to update stock:\n{e}", "DB Error")

    def _set_stock(self):
        if not self._selected_stock_id:
            Messagebox.show_warning("Please select an item first.", "No Item Selected")
            return
        val = self.ent_stock_set.get().strip()
        if not val.isdigit():
            Messagebox.show_warning("Enter a non-negative integer.", "Invalid Input")
            return
        qty = int(val)
        try:
            self.cursor.execute(
                "UPDATE menu_items SET stock_level = %s WHERE item_id = %s",
                (qty, self._selected_stock_id))
            self.conn.commit()
            self._log_activity(
                self.current_user['id'], "STOCK_SET",
                f"Set stock of '{self._selected_stock_name}' to {qty} (item_id={self._selected_stock_id}).")
            Messagebox.show_info(f"'{self._selected_stock_name}' stock set to {qty}.", "Stock Updated")
            self.ent_stock_set.delete(0, END)
            self._load_stock_tree()
            self.load_menu_data()
        except psycopg2.Error as e:
            self._safe_rollback()
            Messagebox.show_error(f"Failed to set stock:\n{e}", "DB Error")

    # ═══════════════════════════ ORDER TAB ═══════════════════════════════════
    def setup_order_tab(self):
        top_bar = tb.Frame(self.tab_orders)
        top_bar.pack(fill=X, pady=(0, 8))

        tb.Label(top_bar, text="Table Number:", font=("Helvetica", 12, "bold")).pack(side=LEFT, padx=(0, 6))
        self.ent_table = tb.Entry(top_bar, width=6, font=("Helvetica", 12))
        self.ent_table.pack(side=LEFT, padx=(0, 20))

        tb.Label(top_bar, text="Search:", font=("Helvetica", 11)).pack(side=LEFT, padx=(0, 4))
        self.search_var = tb.StringVar()
        self.search_var.trace_add("write", lambda *a: self.build_food_cards())
        tb.Entry(top_bar, textvariable=self.search_var, width=16, font=("Helvetica", 11)).pack(side=LEFT)
        tb.Button(top_bar, text="↻ Refresh", bootstyle=INFO, command=self.load_menu_data).pack(side=RIGHT)

        main = tb.Frame(self.tab_orders)
        main.pack(fill=BOTH, expand=True)

        right_panel = tb.Frame(main, width=300)
        right_panel.pack(side=RIGHT, fill=Y, padx=(10, 0))
        right_panel.pack_propagate(False)

        tb.Label(right_panel, text="🛒  Cart", font=("Helvetica", 12, "bold")).pack(anchor=W, pady=(0, 4))

        cart_cols = ('name', 'qty', 'sub')
        self.tree_cart = tb.Treeview(right_panel, columns=cart_cols,
                                     show='headings', bootstyle=SUCCESS, height=16)
        self.tree_cart.heading('name', text='Item')
        self.tree_cart.heading('qty',  text='Qty')
        self.tree_cart.heading('sub',  text='Subtotal')
        self.tree_cart.column('name', width=140)
        self.tree_cart.column('qty',  width=50,  anchor=CENTER)
        self.tree_cart.column('sub',  width=90,  anchor=E)
        self.tree_cart.pack(fill=BOTH, expand=True)

        tb.Button(right_panel, text="✕ Remove Selected",
                  bootstyle=(DANGER, OUTLINE), command=self.remove_cart_item).pack(fill=X, pady=(6, 2))

        self.lbl_total = tb.Label(right_panel, text="Total: $0.00",
                                  font=("Helvetica", 12, "bold"), bootstyle=WARNING)
        self.lbl_total.pack(anchor=E, pady=4)

        tb.Button(right_panel, text="✔  Place Order", bootstyle=SUCCESS,
                  command=self.place_order_from_cart).pack(fill=X, pady=(4, 0))

        left_panel = tb.Frame(main)
        left_panel.pack(side=LEFT, fill=BOTH, expand=True)

        self.cards_canvas = tb.Canvas(left_panel, highlightthickness=0)
        vsb = tb.Scrollbar(left_panel, orient=VERTICAL, command=self.cards_canvas.yview)
        self.cards_canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side=RIGHT, fill=Y)
        self.cards_canvas.pack(side=LEFT, fill=BOTH, expand=True)

        self.cards_inner = tb.Frame(self.cards_canvas)
        self._canvas_win = self.cards_canvas.create_window((0, 0), window=self.cards_inner, anchor=NW)

        self.cards_inner.bind(
            "<Configure>",
            lambda e: self.cards_canvas.configure(scrollregion=self.cards_canvas.bbox("all")))
        self.cards_canvas.bind(
            "<Configure>",
            lambda e: self.cards_canvas.itemconfig(self._canvas_win, width=e.width))

        self._order_tab_ready = True
        self.build_food_cards()

    def build_food_cards(self):
        if not hasattr(self, 'cards_inner'):
            return
        for w in self.cards_inner.winfo_children():
            w.destroy()
        self.thumb_refs.clear()

        search = self.search_var.get().lower()
        items = [(iid, d) for iid, d in self.menu_data.items() if search in d['name'].lower()]

        COLS = 3
        for idx, (item_id, data) in enumerate(items):
            r, c = divmod(idx, COLS)
            card = tb.Frame(self.cards_inner, bootstyle=SECONDARY)
            card.grid(row=r, column=c, padx=8, pady=8, sticky=NSEW)
            self.cards_inner.columnconfigure(c, weight=1)

            img_lbl = tb.Label(card, text="🍽", font=("Helvetica", 32))
            if HAS_PIL and data['image_path'] and os.path.exists(data['image_path']):
                try:
                    p_img = Image.open(data['image_path']).resize((100, 100), Image.Resampling.LANCZOS)
                    photo = ImageTk.PhotoImage(p_img)
                    self.thumb_refs[item_id] = photo
                    img_lbl.config(image=photo, text="")
                except Exception:
                    pass
            img_lbl.pack(pady=5)

            tb.Label(card, text=data['name'], font=("Helvetica", 10, "bold"), justify=CENTER).pack()
            tb.Label(card, text=f"${float(data['price']):.2f}", bootstyle=SUCCESS).pack()

            qty_var = tb.IntVar(value=1)
            row_f = tb.Frame(card)
            row_f.pack(pady=5)
            tb.Spinbox(row_f, from_=1, to=99, textvariable=qty_var, width=5).pack(side=LEFT)
            tb.Button(card, text="Add", bootstyle=SUCCESS, width=8,
                      command=lambda i=item_id, q=qty_var: self.add_to_cart(i, q.get())).pack()

    def add_to_cart(self, item_id, quantity):
        for row in self.order_cart:
            if row['item_id'] == item_id:
                row['quantity'] += quantity
                self.refresh_cart_view()
                return
        data = self.menu_data[item_id]
        self.order_cart.append({
            'item_id': item_id, 'name': data['name'],
            'price': float(data['price']), 'quantity': quantity
        })
        self.refresh_cart_view()

    def refresh_cart_view(self):
        for i in self.tree_cart.get_children():
            self.tree_cart.delete(i)
        total = 0.0
        for row in self.order_cart:
            sub = row['price'] * row['quantity']
            total += sub
            self.tree_cart.insert('', END, values=(row['name'], row['quantity'], f"${sub:.2f}"))
        self.lbl_total.config(text=f"Total: ${total:.2f}")

    def remove_cart_item(self):
        sel = self.tree_cart.selection()
        if sel:
            idx = self.tree_cart.index(sel[0])
            self.order_cart.pop(idx)
            self.refresh_cart_view()

    def place_order_from_cart(self):                          # ← fixed: back inside class
        table = self.ent_table.get().strip()
        if not table.isdigit() or not self.order_cart:
            Messagebox.show_warning("Invalid table number or empty cart.", "Warning")
            return
        try:
            self.cursor.execute(
                "INSERT INTO orders (table_number, employee_id, kitchen_status) "
                "VALUES (%s, %s, 'Waiting') RETURNING order_id",
                (table, self.current_user['id']))
            order_id = self.cursor.fetchone()[0]
            for row in self.order_cart:
                self.cursor.execute(
                    "INSERT INTO order_items (order_id, item_id, quantity) VALUES (%s, %s, %s)",
                    (order_id, row['item_id'], row['quantity']))
            self.conn.commit()
            self._log_activity(
                self.current_user['id'], "ORDER_PLACED",
                f"Order #{order_id} placed for table {table}.")

            # ── Cloud sync ────────────────────────────────────────
            try:
                sync_to_cloud("orders", order_id, {
                    "order_id":       order_id,
                    "table_number":   int(table),
                    "employee":       self.current_user['name'],
                    "kitchen_status": "Waiting",
                    "status":         "Pending",
                    "created_at":     datetime.now().isoformat(),
                    "items": [
                        {
                            "name":     r['name'],
                            "quantity": r['quantity'],
                            "price":    r['price']
                        }
                        for r in self.order_cart
                    ]
                })
            except Exception as ce:
                print(f"Cloud sync failed (non-critical): {ce}")
            # ──────────────────────────────────────────────────────

            Messagebox.show_info(f"Order #{order_id} placed!", "Success")
            self.order_cart.clear()
            self.refresh_cart_view()
        except Exception as e:
            self._safe_rollback()
            Messagebox.show_error(str(e), "Error")

    # ═══════════════════════════ BILLING TAB ═════════════════════════════════
    def setup_billing_tab(self):
        import tkinter as tk

        top = tb.Frame(self.tab_billing)
        top.pack(fill=X, pady=(10, 6), padx=20)

        tb.Label(top, text="Table #:", font=("Helvetica", 12, "bold")).pack(side=LEFT, padx=(0, 6))
        self.ent_bill_table = tb.Entry(top, width=8, font=("Helvetica", 12))
        self.ent_bill_table.pack(side=LEFT, padx=(0, 10))
        tb.Button(top, text="🧾  Generate Bill", bootstyle=INFO,
                  command=self.generate_bill).pack(side=LEFT, padx=4)
        self.btn_pay = tb.Button(top, text="✅  Mark as Paid", bootstyle=SUCCESS,
                                  state=DISABLED, command=self.checkout)
        self.btn_pay.pack(side=RIGHT, padx=4)

        card_outer = tb.Frame(self.tab_billing, bootstyle=SECONDARY)
        card_outer.pack(fill=BOTH, expand=True, padx=40, pady=10)

        self.receipt_canvas = tk.Canvas(card_outer, bg="#1e1e2e", highlightthickness=0)
        vsb = tb.Scrollbar(card_outer, orient=VERTICAL, command=self.receipt_canvas.yview)
        self.receipt_canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side=RIGHT, fill=Y)
        self.receipt_canvas.pack(side=LEFT, fill=BOTH, expand=True)

        self.receipt_inner = tk.Frame(self.receipt_canvas, bg="#1e1e2e")
        self._receipt_win  = self.receipt_canvas.create_window(
            (0, 0), window=self.receipt_inner, anchor="nw")

        self.receipt_inner.bind(
            "<Configure>",
            lambda e: self.receipt_canvas.configure(
                scrollregion=self.receipt_canvas.bbox("all")))
        self.receipt_canvas.bind(
            "<Configure>",
            lambda e: self.receipt_canvas.itemconfig(self._receipt_win, width=e.width))

        self._show_receipt_placeholder()

    def _clear_receipt(self):
        for w in self.receipt_inner.winfo_children():
            w.destroy()

    def _show_receipt_placeholder(self):
        import tkinter as tk
        self._clear_receipt()
        tk.Label(self.receipt_inner,
                 text="\n\n\n🧾\n\nEnter a table number above\nand click  Generate Bill",
                 bg="#1e1e2e", fg="#555577",
                 font=("Courier", 13), justify="center").pack(expand=True, pady=80)

    def generate_bill(self):
        import tkinter as tk

        table = self.ent_bill_table.get().strip()
        if not table.isdigit():
            self._show_receipt_placeholder()
            return

        try:
            self.cursor.execute(
                "SELECT order_id, total_amount, created_at "
                "FROM orders WHERE table_number=%s AND status='Pending'",
                (table,))
            order = self.cursor.fetchone()
        except psycopg2.Error as e:
            self._safe_rollback()
            Messagebox.show_error(f"Database error while generating bill:\n{e}", "Database Error")
            return

        self._clear_receipt()

        BG   = "#1e1e2e"
        CARD = "#252538"
        ACC  = "#7c6af7"
        GRN  = "#50fa7b"
        WHT  = "#cdd6f4"
        DIM  = "#6272a4"
        RED  = "#ff5555"
        ALT  = "#23233a"

        def lbl(parent, text, fg=WHT, font=("Courier", 10), bg=BG, **kw):
            return tk.Label(parent, text=text, fg=fg, font=font, bg=bg, **kw)

        outer = tk.Frame(self.receipt_inner, bg=BG, padx=40, pady=24)
        outer.pack(fill=BOTH, expand=True)

        if not order:
            lbl(outer, "\n❌  No pending orders found for this table.",
                fg=RED, font=("Courier", 13, "bold")).pack(pady=40)
            self.btn_pay.config(state=DISABLED)
            return

        self.active_bill_id = order[0]
        order_id   = order[0]
        total_amt  = float(order[1]) if order[1] else 0.0
        created_at = order[2]
        date_str   = (created_at.strftime("%d %b %Y   %H:%M")
                      if hasattr(created_at, 'strftime') else str(created_at))

        lbl(outer, "R E S T R O C O R E", fg=ACC, font=("Courier", 20, "bold")).pack()
        lbl(outer, "━━━  Fine Dining & Beyond  ━━━", fg=DIM, font=("Courier", 10)).pack(pady=(2, 0))
        lbl(outer, " ", bg=BG).pack()

        meta = tk.Frame(outer, bg=BG)
        meta.pack(fill=X)
        lbl(meta, f"Order  #  {order_id}", fg=WHT, font=("Courier", 10, "bold")).pack(side=LEFT)
        lbl(meta, date_str, fg=DIM, font=("Courier", 9)).pack(side=RIGHT)

        lbl(outer, f"Table :  {table}", fg=WHT, font=("Courier", 10)).pack(anchor="w", pady=(4, 0))
        lbl(outer, f"Server :  {self.current_user['name']}", fg=WHT, font=("Courier", 10)).pack(anchor="w")

        tk.Frame(outer, bg=ACC, height=2).pack(fill=X, pady=12)

        hdr = tk.Frame(outer, bg=CARD, pady=7, padx=8)
        hdr.pack(fill=X)
        tk.Label(hdr, text="ITEM",     bg=CARD, fg=ACC, font=("Courier", 10, "bold"), width=28, anchor="w").grid(row=0, column=0, padx=(4, 0))
        tk.Label(hdr, text="QTY",      bg=CARD, fg=ACC, font=("Courier", 10, "bold"), width=6,  anchor="center").grid(row=0, column=1)
        tk.Label(hdr, text="UNIT",     bg=CARD, fg=ACC, font=("Courier", 10, "bold"), width=10, anchor="e").grid(row=0, column=2)
        tk.Label(hdr, text="SUBTOTAL", bg=CARD, fg=ACC, font=("Courier", 10, "bold"), width=12, anchor="e").grid(row=0, column=3, padx=(0, 4))

        try:
            self.cursor.execute("""
                SELECT mi.name, oi.quantity, mi.price
                FROM order_items oi
                JOIN menu_items mi ON oi.item_id = mi.item_id
                WHERE oi.order_id = %s
                ORDER BY mi.name
            """, (order_id,))
            items = self.cursor.fetchall()
        except psycopg2.Error as e:
            self._safe_rollback()
            Messagebox.show_error(f"Error fetching order items:\n{e}", "DB Error")
            return

        running = 0.0
        for i, (name, qty, unit_price) in enumerate(items):
            unit_price = float(unit_price)
            sub = unit_price * qty
            running += sub
            row_bg = BG if i % 2 == 0 else ALT
            row_f = tk.Frame(outer, bg=row_bg, pady=5, padx=8)
            row_f.pack(fill=X)
            tk.Label(row_f, text=name[:30], bg=row_bg, fg=WHT,  font=("Courier", 10), width=28, anchor="w").grid(row=0, column=0, padx=(4, 0))
            tk.Label(row_f, text=f"× {qty}",           bg=row_bg, fg=DIM, font=("Courier", 10), width=6,  anchor="center").grid(row=0, column=1)
            tk.Label(row_f, text=f"${unit_price:.2f}",  bg=row_bg, fg=DIM, font=("Courier", 10), width=10, anchor="e").grid(row=0, column=2)
            tk.Label(row_f, text=f"${sub:.2f}",         bg=row_bg, fg=GRN, font=("Courier", 10, "bold"), width=12, anchor="e").grid(row=0, column=3, padx=(0, 4))

        tk.Frame(outer, bg=DIM, height=1).pack(fill=X, pady=12)

        TAX_RATE = 0.08
        tax_amt  = running * TAX_RATE
        grand    = running + tax_amt

        summary = tk.Frame(outer, bg=BG)
        summary.pack(anchor="e", padx=8)

        def srow(r, label, value, fg_val=WHT, bold=False):
            f = ("Courier", 10, "bold") if bold else ("Courier", 10)
            tk.Label(summary, text=label, bg=BG, fg=DIM, font=f, anchor="e", width=20).grid(row=r, column=0, sticky="e", pady=2)
            tk.Label(summary, text=value, bg=BG, fg=fg_val, font=f, anchor="e", width=12).grid(row=r, column=1, sticky="e", pady=2)

        srow(0, "Subtotal :", f"${running:.2f}")
        srow(1, f"Tax  ({int(TAX_RATE*100)}%) :", f"${tax_amt:.2f}")

        total_frame = tk.Frame(outer, bg=ACC, pady=12, padx=20)
        total_frame.pack(fill=X, pady=(10, 0))
        tk.Label(total_frame, text="TOTAL  DUE", bg=ACC, fg="#ffffff", font=("Courier", 14, "bold")).pack(side=LEFT)
        tk.Label(total_frame, text=f"  ${grand:.2f}", bg=ACC, fg="#ffffff", font=("Courier", 18, "bold")).pack(side=RIGHT)

        lbl(outer, " ", bg=BG).pack()
        tk.Frame(outer, bg=DIM, height=1).pack(fill=X)
        lbl(outer, "Thank you for dining with us!  🍽️", fg=DIM, font=("Courier", 10, "italic")).pack(pady=(8, 2))
        lbl(outer, "Please come again  •  RestroCore POS  v1.0", fg=DIM, font=("Courier", 8)).pack()
        lbl(outer, " ", bg=BG).pack()

        try:
            self.cursor.execute(
                "SELECT kitchen_status FROM orders WHERE order_id = %s",
                (self.active_bill_id,))
            row = self.cursor.fetchone()
            kitchen_status = row[0] if row else None
        except psycopg2.Error as e:
            self._safe_rollback()
            kitchen_status = None

        if kitchen_status == "Completed":
            self.btn_pay.config(state=NORMAL)
        else:
            self.btn_pay.config(state=DISABLED)
            Messagebox.show_warning(
                "Payment is not allowed yet.\n\n"
                "The chef must mark this order as  ✅ Completed  "
                "before it can be billed.",
                "Order Not Ready")

    def checkout(self):
        try:
            self.cursor.execute(
                "UPDATE orders SET status='Paid' WHERE order_id=%s",
                (self.active_bill_id,))
            self.conn.commit()
            self._log_activity(
                self.current_user['id'], "ORDER_PAID",
                f"Order #{self.active_bill_id} marked as Paid.")

            # ── Cloud sync ────────────────────────────────────────
            # Uses update() so only these fields change; the rest of
            # the order document (items, table, etc.) is preserved.
            try:
                update_cloud_status("orders", self.active_bill_id, "Paid")
            except Exception as ce:
                print(f"Cloud sync failed (non-critical): {ce}")
            # ──────────────────────────────────────────────────────

            Messagebox.show_info("Payment Complete!  Thank you 🎉", "Success")
            self._show_receipt_placeholder()
            self.btn_pay.config(state=DISABLED)
        except psycopg2.Error as e:
            self._safe_rollback()
            Messagebox.show_error(f"Checkout failed:\n{e}", "DB Error")

    # ═══════════════════════════ KITCHEN TAB (Chef only) ═════════════════════
    def setup_kitchen_tab(self):
        top = tb.Frame(self.tab_kitchen)
        top.pack(fill=X, padx=10, pady=10)

        tb.Label(top, text="Kitchen Order Board",
                 font=("Helvetica", 16, "bold"), bootstyle=WARNING).pack(side=LEFT)
        tb.Button(top, text="↻ Refresh Orders", bootstyle=INFO,
                  command=self._load_kitchen_orders).pack(side=RIGHT)

        filter_frame = tb.Frame(self.tab_kitchen)
        filter_frame.pack(fill=X, padx=10, pady=(0, 8))

        tb.Label(filter_frame, text="Filter by Status:", font=("Helvetica", 11)).pack(side=LEFT, padx=(0, 6))
        self.kitchen_filter_var = tb.StringVar(value="All")
        for opt in ["All", "Waiting", "In Process", "Completed"]:
            tb.Radiobutton(filter_frame, text=opt, variable=self.kitchen_filter_var,
                           value=opt, bootstyle=INFO,
                           command=self._load_kitchen_orders).pack(side=LEFT, padx=6)

        cols = ('order_id', 'table', 'placed_by', 'placed_at', 'kitchen_status')
        self.tree_kitchen = tb.Treeview(self.tab_kitchen, columns=cols,
                                        show='headings', bootstyle=WARNING, height=12)
        self.tree_kitchen.heading('order_id',       text='Order #')
        self.tree_kitchen.heading('table',          text='Table')
        self.tree_kitchen.heading('placed_by',      text='Placed By')
        self.tree_kitchen.heading('placed_at',      text='Placed At')
        self.tree_kitchen.heading('kitchen_status', text='Kitchen Status')
        self.tree_kitchen.column('order_id',       width=80,  anchor=CENTER)
        self.tree_kitchen.column('table',          width=70,  anchor=CENTER)
        self.tree_kitchen.column('placed_by',      width=160)
        self.tree_kitchen.column('placed_at',      width=180, anchor=CENTER)
        self.tree_kitchen.column('kitchen_status', width=130, anchor=CENTER)
        self.tree_kitchen.pack(fill=BOTH, expand=False, padx=10, pady=(0, 6))

        self.tree_kitchen.bind('<<TreeviewSelect>>', self._on_kitchen_select)

        detail_frame = tb.LabelFrame(self.tab_kitchen, text=" Order Items ")
        detail_frame.pack(fill=X, padx=10, pady=(0, 8))

        dcols = ('item', 'qty')
        self.tree_kitchen_detail = tb.Treeview(detail_frame, columns=dcols,
                                               show='headings', bootstyle=SECONDARY, height=5)
        self.tree_kitchen_detail.heading('item', text='Menu Item')
        self.tree_kitchen_detail.heading('qty',  text='Qty')
        self.tree_kitchen_detail.column('item', width=320)
        self.tree_kitchen_detail.column('qty',  width=80, anchor=CENTER)
        self.tree_kitchen_detail.pack(fill=X)

        action_frame = tb.LabelFrame(self.tab_kitchen, text=" Update Status ")
        action_frame.pack(fill=X, padx=10, pady=(0, 10))

        self.lbl_kitchen_sel = tb.Label(action_frame,
                                        text="(select an order above to update its status)",
                                        font=("Helvetica", 11, "italic"), bootstyle=SECONDARY)
        self.lbl_kitchen_sel.pack(anchor=W, pady=(0, 8))

        btn_row = tb.Frame(action_frame)
        btn_row.pack(fill=X)
        tb.Button(btn_row, text="⏳  Mark as Waiting",    bootstyle=(WARNING, OUTLINE), width=22,
                  command=lambda: self._update_kitchen_status("Waiting")).pack(side=LEFT, padx=4)
        tb.Button(btn_row, text="🔥  Mark as In Process", bootstyle=(INFO, OUTLINE),    width=22,
                  command=lambda: self._update_kitchen_status("In Process")).pack(side=LEFT, padx=4)
        tb.Button(btn_row, text="✅  Mark as Completed",  bootstyle=SUCCESS,            width=22,
                  command=lambda: self._update_kitchen_status("Completed")).pack(side=LEFT, padx=4)

        self._selected_kitchen_order_id = None
        self._load_kitchen_orders()

    def _load_kitchen_orders(self):
        if not hasattr(self, 'tree_kitchen'):
            return
        for i in self.tree_kitchen.get_children():
            self.tree_kitchen.delete(i)

        status_filter = self.kitchen_filter_var.get()

        try:
            if status_filter == "All":
                self.cursor.execute("""
                    SELECT o.order_id, o.table_number, e.name,
                           o.created_at, o.kitchen_status
                    FROM orders o
                    JOIN employees e ON o.employee_id = e.employee_id
                    WHERE o.status = 'Pending'
                    ORDER BY
                        CASE o.kitchen_status
                            WHEN 'Waiting'    THEN 1
                            WHEN 'In Process' THEN 2
                            WHEN 'Completed'  THEN 3
                            ELSE 4
                        END,
                        o.created_at ASC
                """)
            else:
                self.cursor.execute("""
                    SELECT o.order_id, o.table_number, e.name,
                           o.created_at, o.kitchen_status
                    FROM orders o
                    JOIN employees e ON o.employee_id = e.employee_id
                    WHERE o.status = 'Pending'
                      AND o.kitchen_status = %s
                    ORDER BY o.created_at ASC
                """, (status_filter,))
            rows = self.cursor.fetchall()
        except psycopg2.Error as e:
            self._safe_rollback()
            Messagebox.show_error(f"Error loading kitchen orders:\n{e}", "DB Error")
            return

        STATUS_ICONS = {
            "Waiting":    "⏳ Waiting",
            "In Process": "🔥 In Process",
            "Completed":  "✅ Completed",
        }
        for row in rows:
            order_id, table, placed_by, created_at, kstatus = row
            ts = created_at.strftime("%d %b %Y  %H:%M") if hasattr(created_at, 'strftime') else str(created_at)
            display_status = STATUS_ICONS.get(kstatus, kstatus or "⏳ Waiting")
            self.tree_kitchen.insert('', END,
                                     values=(order_id, table, placed_by, ts, display_status))

        for i in self.tree_kitchen_detail.get_children():
            self.tree_kitchen_detail.delete(i)
        self._selected_kitchen_order_id = None
        self.lbl_kitchen_sel.config(text="(select an order above to update its status)")

    def _on_kitchen_select(self, event):
        sel = self.tree_kitchen.selection()
        if not sel:
            return
        vals = self.tree_kitchen.item(sel[0])['values']
        self._selected_kitchen_order_id = vals[0]
        self.lbl_kitchen_sel.config(
            text=f"Selected  →  Order #{vals[0]}  |  Table {vals[1]}  |  Status: {vals[4]}")

        for i in self.tree_kitchen_detail.get_children():
            self.tree_kitchen_detail.delete(i)
        try:
            self.cursor.execute("""
                SELECT mi.name, oi.quantity
                FROM order_items oi
                JOIN menu_items mi ON oi.item_id = mi.item_id
                WHERE oi.order_id = %s
                ORDER BY mi.name
            """, (self._selected_kitchen_order_id,))
            for item_name, qty in self.cursor.fetchall():
                self.tree_kitchen_detail.insert('', END, values=(item_name, qty))
        except psycopg2.Error as e:
            self._safe_rollback()

    def _update_kitchen_status(self, new_status):
        if not self._selected_kitchen_order_id:
            Messagebox.show_warning("Please select an order first.", "No Order Selected")
            return
        try:
            self.cursor.execute(
                "UPDATE orders SET kitchen_status = %s WHERE order_id = %s",
                (new_status, self._selected_kitchen_order_id))
            self.conn.commit()
            self._log_activity(
                self.current_user['id'], "KITCHEN_STATUS",
                f"Order #{self._selected_kitchen_order_id} kitchen status → '{new_status}'.")

            # ── Cloud sync ────────────────────────────────────────
            # Uses .update() so only kitchen_status changes in Firestore
            try:
                update_cloud_status("orders", self._selected_kitchen_order_id, new_status)
            except Exception as ce:
                print(f"Cloud sync failed (non-critical): {ce}")
            # ──────────────────────────────────────────────────────

            Messagebox.show_info(
                f"Order #{self._selected_kitchen_order_id} marked as '{new_status}'.", "Status Updated")
            self._load_kitchen_orders()
        except psycopg2.Error as e:
            self._safe_rollback()
            Messagebox.show_error(f"Failed to update status:\n{e}", "DB Error")

    # ═══════════════════════════ STAFF TAB (Manager only) ════════════════════
    def setup_staff_tab(self):
        list_frame = tb.LabelFrame(self.tab_staff, text=" Current Staff ")
        list_frame.pack(fill=BOTH, expand=True, padx=10, pady=10)

        scols = ('id', 'name', 'role', 'username')
        self.tree_staff = tb.Treeview(list_frame, columns=scols, show='headings',
                                      bootstyle=PRIMARY, height=10)
        self.tree_staff.heading('id',       text='ID')
        self.tree_staff.heading('name',     text='Full Name')
        self.tree_staff.heading('role',     text='Role')
        self.tree_staff.heading('username', text='Username')
        self.tree_staff.column('id',       width=50,  anchor=CENTER)
        self.tree_staff.column('name',     width=200)
        self.tree_staff.column('role',     width=120)
        self.tree_staff.column('username', width=150)
        self.tree_staff.pack(fill=BOTH, expand=True)

        btn_row = tb.Frame(list_frame)
        btn_row.pack(fill=X, pady=(8, 0))
        tb.Button(btn_row, text="↻ Refresh Staff", bootstyle=INFO,
                  command=self._load_staff_list).pack(side=LEFT, padx=4)
        tb.Button(btn_row, text="🗑 Remove Selected", bootstyle=(DANGER, OUTLINE),
                  command=self._remove_staff).pack(side=LEFT, padx=4)

        form_frame = tb.LabelFrame(self.tab_staff, text=" Add New Staff ")
        form_frame.pack(fill=X, padx=10, pady=(0, 10))

        form = tb.Frame(form_frame)
        form.pack()
        self.staff_entries = []
        labels = ["Full Name:", "Position:", "Username:", "Password:"]
        for i, lbl_text in enumerate(labels):
            tb.Label(form, text=lbl_text).grid(row=i, column=0, sticky=E, padx=5, pady=5)
            e = tb.Entry(form, width=25, show="*" if "Password" in lbl_text else "")
            e.grid(row=i, column=1, padx=5, pady=5)
            self.staff_entries.append(e)
        tb.Button(form, text="➕  Add Staff", bootstyle=SUCCESS,
                  command=self.add_staff).grid(row=4, columnspan=2, pady=10)

        self._load_staff_list()

    def _load_staff_list(self):
        if not hasattr(self, 'tree_staff'):
            return
        for i in self.tree_staff.get_children():
            self.tree_staff.delete(i)
        try:
            self.cursor.execute(
                "SELECT employee_id, name, role, username FROM employees ORDER BY employee_id")
            for row in self.cursor.fetchall():
                self.tree_staff.insert('', END, values=row)
        except psycopg2.Error as e:
            self._safe_rollback()

    def add_staff(self):
        vals = [e.get().strip() for e in self.staff_entries]
        if not all(vals):
            Messagebox.show_warning("All fields are required.", "Missing Data")
            return
        try:
            self.cursor.execute(
                "INSERT INTO employees (name, role, username, password) VALUES (%s,%s,%s,%s)",
                vals)
            self.conn.commit()
            self._log_activity(
                self.current_user['id'], "STAFF_ADDED",
                f"New staff added: '{vals[0]}' (role={vals[1]}, username={vals[2]}).")
            Messagebox.show_info(f"Staff '{vals[0]}' added successfully.", "Success")
            for e in self.staff_entries:
                e.delete(0, END)
            self._load_staff_list()
        except psycopg2.Error as e:
            self._safe_rollback()
            Messagebox.show_error(f"Failed to add staff:\n{e}", "DB Error")

    def _remove_staff(self):
        sel = self.tree_staff.selection()
        if not sel:
            Messagebox.show_warning("Select a staff member to remove.", "No Selection")
            return
        vals = self.tree_staff.item(sel[0])['values']
        emp_id, emp_name = vals[0], vals[1]

        if emp_id == self.current_user['id']:
            Messagebox.show_error("You cannot remove yourself.", "Not Allowed")
            return

        confirm = Messagebox.yesno(
            f"Remove '{emp_name}' (ID: {emp_id})?\nThis cannot be undone.", "Confirm Remove")
        if not confirm:
            return

        try:
            self.cursor.execute(
                "DELETE FROM employees WHERE employee_id = %s", (emp_id,))
            self.conn.commit()
            self._log_activity(
                self.current_user['id'], "STAFF_REMOVED",
                f"Staff removed: '{emp_name}' (employee_id={emp_id}).")
            Messagebox.show_info(f"'{emp_name}' has been removed.", "Removed")
            self._load_staff_list()
        except psycopg2.Error as e:
            self._safe_rollback()
            Messagebox.show_error(f"Cannot remove staff (may have linked orders):\n{e}", "DB Error")

    # ═══════════════════════════ ACTIVITY LOG TAB (Manager only) ════════════
    def setup_activity_log_tab(self):
        top = tb.Frame(self.tab_actlog)
        top.pack(fill=X, padx=10, pady=10)

        tb.Label(top, text="Activity Log",
                 font=("Helvetica", 16, "bold"), bootstyle=INFO).pack(side=LEFT)

        right_controls = tb.Frame(top)
        right_controls.pack(side=RIGHT)

        tb.Label(right_controls, text="Filter:", font=("Helvetica", 11)).pack(side=LEFT, padx=(0, 4))
        self.log_filter_var = tb.StringVar(value="All")
        log_categories = ["All", "LOGIN", "STAFF_ADDED", "STAFF_REMOVED",
                          "ORDER_PLACED", "ORDER_PAID", "STOCK_ADD", "STOCK_SET",
                          "KITCHEN_STATUS"]
        self.log_filter_cb = tb.Combobox(right_controls, textvariable=self.log_filter_var,
                                         values=log_categories, width=16, state='readonly')
        self.log_filter_cb.pack(side=LEFT, padx=(0, 8))
        self.log_filter_cb.bind("<<ComboboxSelected>>", lambda e: self._load_activity_log())

        tb.Button(right_controls, text="↻ Refresh", bootstyle=INFO,
                  command=self._load_activity_log).pack(side=LEFT)

        cols = ('log_id', 'timestamp', 'employee', 'action', 'details')
        self.tree_actlog = tb.Treeview(self.tab_actlog, columns=cols,
                                       show='headings', bootstyle=INFO)
        self.tree_actlog.heading('log_id',    text='#')
        self.tree_actlog.heading('timestamp', text='Timestamp')
        self.tree_actlog.heading('employee',  text='Employee')
        self.tree_actlog.heading('action',    text='Action')
        self.tree_actlog.heading('details',   text='Details')
        self.tree_actlog.column('log_id',    width=50,  anchor=CENTER)
        self.tree_actlog.column('timestamp', width=170, anchor=CENTER)
        self.tree_actlog.column('employee',  width=150)
        self.tree_actlog.column('action',    width=140)
        self.tree_actlog.column('details',   width=500)

        vsb = tb.Scrollbar(self.tab_actlog, orient=VERTICAL, command=self.tree_actlog.yview)
        self.tree_actlog.configure(yscrollcommand=vsb.set)
        vsb.pack(side=RIGHT, fill=Y, padx=(0, 10))
        self.tree_actlog.pack(fill=BOTH, expand=True, padx=(10, 0), pady=(0, 10))

        ACTION_COLORS = {
            "STAFF_ADDED":    "success",
            "STAFF_REMOVED":  "danger",
            "LOGIN":          "info",
            "ORDER_PLACED":   "primary",
            "ORDER_PAID":     "success",
            "STOCK_ADD":      "warning",
            "STOCK_SET":      "warning",
            "KITCHEN_STATUS": "secondary",
        }
        legend = tb.Frame(self.tab_actlog)
        legend.pack(fill=X, padx=10, pady=(0, 6))
        for action, color in ACTION_COLORS.items():
            tb.Label(legend, text=f" {action} ", bootstyle=color,
                     font=("Helvetica", 8)).pack(side=LEFT, padx=2)

        self._load_activity_log()

    def _load_activity_log(self):
        if not hasattr(self, 'tree_actlog'):
            return
        for i in self.tree_actlog.get_children():
            self.tree_actlog.delete(i)

        action_filter = self.log_filter_var.get()
        try:
            if action_filter == "All":
                self.cursor.execute("""
                    SELECT al.log_id, al.created_at, e.name, al.action, al.details
                    FROM activity_log al
                    LEFT JOIN employees e ON al.employee_id = e.employee_id
                    ORDER BY al.log_id DESC
                    LIMIT 500
                """)
            else:
                self.cursor.execute("""
                    SELECT al.log_id, al.created_at, e.name, al.action, al.details
                    FROM activity_log al
                    LEFT JOIN employees e ON al.employee_id = e.employee_id
                    WHERE al.action = %s
                    ORDER BY al.log_id DESC
                    LIMIT 500
                """, (action_filter,))
            rows = self.cursor.fetchall()
        except psycopg2.Error as e:
            self._safe_rollback()
            Messagebox.show_error(f"Error loading activity log:\n{e}", "DB Error")
            return

        for row in rows:
            log_id, ts, emp_name, action, details = row
            ts_str = ts.strftime("%d %b %Y  %H:%M:%S") if hasattr(ts, 'strftime') else str(ts)
            self.tree_actlog.insert('', END,
                                    values=(log_id, ts_str, emp_name or "—", action, details))

    # ═══════════════════════════ HELPERS ═════════════════════════════════════
    def _log_activity(self, employee_id, action, details):
        try:
            self.cursor.execute(
                "INSERT INTO activity_log (employee_id, action, details) "
                "VALUES (%s, %s, %s)",
                (employee_id, action, details))
            self.conn.commit()
        except Exception:
            self._safe_rollback()

    def _safe_rollback(self):
        try:
            self.conn.rollback()
        except Exception:
            pass

    # ═══════════════════════════ LOGOUT & CLOSING ════════════════════════════
    def logout(self):
        if self.current_user:
            self._log_activity(
                self.current_user['id'], "LOGOUT",
                f"User '{self.current_user['name']}' logged out.")

        self.order_cart      = []
        self.thumb_refs      = {}
        self.current_user    = None
        self.active_bill_id  = None
        self.menu_data       = {}
        self.menu_image_map  = {}

        for attr in ('_order_tab_ready', '_selected_stock_id', '_selected_kitchen_order_id'):
            if hasattr(self, attr):
                delattr(self, attr)

        for w in self.root.winfo_children():
            w.destroy()

        self.build_login_screen()

    def on_closing(self):
        if self.current_user:
            self._log_activity(
                self.current_user['id'], "LOGOUT",
                f"User '{self.current_user['name']}' closed the application.")
        if hasattr(self, 'conn') and self.conn:
            try:
                self.conn.close()
            except Exception:
                pass
        self.root.destroy()


# ═══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    app_root = tb.Window(themename="cyborg")
    app = RestroCoreApp(app_root)
    try:
        app_root.mainloop()
    except KeyboardInterrupt:
        print("\nProgram stopped by user via terminal (Ctrl+C).")
    finally:
        if hasattr(app, 'conn') and app.conn:
            try:
                app.conn.close()
                print("Database connection safely closed.")
            except Exception:
                pass
        try:
            app_root.destroy()
        except Exception:
            pass