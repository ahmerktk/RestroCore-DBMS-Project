import ttkbootstrap as tb
from ttkbootstrap.constants import *
from ttkbootstrap.dialogs import Messagebox
import psycopg2
import os

try:
    from PIL import Image, ImageTk
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

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

        self.current_user    = None
        self.placeholder_img = None
        self.menu_image_map  = {}
        self.menu_data       = {}   # {item_id: {name, price, stock, image_path}}
        self.order_cart      = []   # [{item_id, name, price, quantity}]
        self.thumb_refs      = {}   # keep PhotoImage references alive

        try:
            self.conn   = psycopg2.connect(**DB_CONFIG)
            self.cursor = self.conn.cursor()
        except Exception as e:
            Messagebox.show_error(f"Database Connection Failed:\n{e}", "Database Error")
            self.root.destroy()
            return

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.build_login_screen()

    # ─────────────────────────── LOGIN ───────────────────────────
    def build_login_screen(self):
        self.login_frame = tb.Frame(self.root, padding=40)
        self.login_frame.pack(expand=True)

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
        self.cursor.execute(
            "SELECT employee_id, name, role FROM employees "
            "WHERE username=%s AND password=%s", (username, password))
        user = self.cursor.fetchone()
        if user:
            self.current_user = {"id": user[0], "name": user[1], "role": user[2]}
            self.root.unbind('<Return>')
            self.login_frame.destroy()
            self.build_main_dashboard()
        else:
            Messagebox.show_error("Invalid username or password.", "Login Failed")

    # ─────────────────────────── DASHBOARD ───────────────────────────
    def build_main_dashboard(self):
        header = tb.Frame(self.root, bootstyle=DARK, padding=15)
        header.pack(fill=X)
        tb.Label(header,
                 text=f"👤 {self.current_user['name']} | Role: {self.current_user['role']}",
                 font=("Helvetica", 12), bootstyle=INVERSE).pack(side=LEFT)
        tb.Button(header, text="Logout", bootstyle=(DANGER, OUTLINE),
                  command=self.logout).pack(side=RIGHT)

        self.tab_control = tb.Notebook(self.root, bootstyle=INFO)
        self.tab_control.pack(expand=True, fill=BOTH, padx=20, pady=20)

        self.tab_menu    = tb.Frame(self.tab_control, padding=10)
        self.tab_orders  = tb.Frame(self.tab_control, padding=10)
        self.tab_billing = tb.Frame(self.tab_control, padding=10)

        self.tab_control.add(self.tab_menu,    text='📋 Menu & Inventory')
        self.tab_control.add(self.tab_orders,  text='🍔 Place Order')
        self.tab_control.add(self.tab_billing, text='💳 Billing')

        if self.current_user['role'].lower() == 'manager':
            self.tab_staff = tb.Frame(self.tab_control, padding=10)
            self.tab_control.add(self.tab_staff, text='👥 Staff Management')
            self.setup_staff_tab()

        self.setup_menu_tab()
        self.setup_order_tab()
        self.setup_billing_tab()

    # ─────────────────────────── MENU TAB ───────────────────────────
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
        self.img_label.pack(expand=True, fill=BOTH, pady=(0, 20))

        self.load_menu_data()

    def load_menu_data(self):
        for i in self.tree_menu.get_children():
            self.tree_menu.delete(i)

        self.cursor.execute(
            "SELECT item_id, name, price, stock_level, image_path "
            "FROM menu_items ORDER BY item_id")
        rows = self.cursor.fetchall()

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

    # ─────────────────────────── ORDER TAB ───────────────────────────
    def setup_order_tab(self):
        # ── Top bar ──────────────────────────────────────────────────
        top_bar = tb.Frame(self.tab_orders)
        top_bar.pack(fill=X, pady=(0, 8))

        tb.Label(top_bar, text="Table Number:",
                 font=("Helvetica", 12, "bold")).pack(side=LEFT, padx=(0, 6))
        self.ent_table = tb.Entry(top_bar, width=6, font=("Helvetica", 12))
        self.ent_table.pack(side=LEFT, padx=(0, 20))

        tb.Label(top_bar, text="Search:",
                 font=("Helvetica", 11)).pack(side=LEFT, padx=(0, 4))
        self.search_var = tb.StringVar()
        self.search_var.trace_add("write", lambda *a: self.build_food_cards())
        tb.Entry(top_bar, textvariable=self.search_var,
                 width=16, font=("Helvetica", 11)).pack(side=LEFT)

        tb.Button(top_bar, text="↻ Refresh", bootstyle=INFO,
                  command=self.load_menu_data).pack(side=RIGHT)

        # ── Main split: food grid LEFT, cart RIGHT ────────────────────
        main = tb.Frame(self.tab_orders)
        main.pack(fill=BOTH, expand=True)

        # RIGHT cart panel (packed first with side=RIGHT so it gets fixed space)
        right_panel = tb.Frame(main, width=280)
        right_panel.pack(side=RIGHT, fill=Y, padx=(10, 0))
        right_panel.pack_propagate(False)

        tb.Label(right_panel, text="🛒  Cart",
                 font=("Helvetica", 12, "bold")).pack(anchor=W, pady=(0, 4))

        cart_cols = ('name', 'qty', 'sub')
        self.tree_cart = tb.Treeview(right_panel, columns=cart_cols,
                                     show='headings', bootstyle=SUCCESS, height=16)
        self.tree_cart.heading('name', text='Item')
        self.tree_cart.heading('qty',  text='Qty')
        self.tree_cart.heading('sub',  text='Subtotal')
        self.tree_cart.column('name', width=130)
        self.tree_cart.column('qty',  width=40,  anchor=CENTER)
        self.tree_cart.column('sub',  width=80,  anchor=E)
        self.tree_cart.pack(fill=BOTH, expand=True)

        tb.Button(right_panel, text="✕ Remove Selected",
                  bootstyle=(DANGER, OUTLINE),
                  command=self.remove_cart_item).pack(fill=X, pady=(6, 2))

        self.lbl_total = tb.Label(right_panel, text="Total: $0.00",
                                  font=("Helvetica", 12, "bold"),
                                  bootstyle=WARNING)
        self.lbl_total.pack(anchor=E, pady=4)

        tb.Button(right_panel, text="✔  Place Order",
                  bootstyle=SUCCESS,
                  command=self.place_order_from_cart).pack(fill=X, pady=(4, 0))

        # LEFT food grid panel (gets all remaining space)
        left_panel = tb.Frame(main)
        left_panel.pack(side=LEFT, fill=BOTH, expand=True)

        tb.Label(left_panel, text="🍽  Select Items",
                 font=("Helvetica", 12, "bold")).pack(anchor=W, pady=(0, 4))

        canvas_holder = tb.Frame(left_panel)
        canvas_holder.pack(fill=BOTH, expand=True)

        self.cards_canvas = tb.Canvas(canvas_holder, highlightthickness=0)
        vsb = tb.Scrollbar(canvas_holder, orient=VERTICAL,
                           command=self.cards_canvas.yview)
        self.cards_canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side=RIGHT, fill=Y)
        self.cards_canvas.pack(side=LEFT, fill=BOTH, expand=True)

        self.cards_inner = tb.Frame(self.cards_canvas)
        self._canvas_win = self.cards_canvas.create_window(
            (0, 0), window=self.cards_inner, anchor=NW)

        self.cards_inner.bind("<Configure>",
            lambda e: self.cards_canvas.configure(
                scrollregion=self.cards_canvas.bbox("all")))
        self.cards_canvas.bind("<Configure>",
            lambda e: self.cards_canvas.itemconfig(
                self._canvas_win, width=e.width))
        self.cards_canvas.bind("<MouseWheel>",
            lambda e: self.cards_canvas.yview_scroll(
                int(-1 * (e.delta / 120)), "units"))

        self._order_tab_ready = True
        self.build_food_cards()

    # ── Food card grid ─────────────────────────────────────────────
    def build_food_cards(self):
        for w in self.cards_inner.winfo_children():
            w.destroy()
        self.thumb_refs.clear()

        search = self.search_var.get().lower() if hasattr(self, 'search_var') else ""
        COLS  = 3
        THUMB = 100

        items = [(iid, d) for iid, d in self.menu_data.items()
                 if search in d['name'].lower()]

        if not items:
            tb.Label(self.cards_inner, text="No items found.",
                     font=("Helvetica", 11)).grid(row=0, column=0,
                                                   padx=20, pady=20)
            return

        for idx, (item_id, data) in enumerate(items):
            r, c = divmod(idx, COLS)

            card = tb.Frame(self.cards_inner, bootstyle=SECONDARY, padding=8)
            card.grid(row=r, column=c, padx=6, pady=6, sticky=NSEW)
            self.cards_inner.columnconfigure(c, weight=1)

            # image or emoji fallback
            img_lbl = tb.Label(card, text="🍽", font=("Helvetica", 26))
            if HAS_PIL and data['image_path'] and os.path.exists(data['image_path']):
                try:
                    pil_img = Image.open(data['image_path']).resize(
                        (THUMB, THUMB), Image.Resampling.LANCZOS)
                    photo = ImageTk.PhotoImage(pil_img)
                    self.thumb_refs[item_id] = photo
                    img_lbl.config(image=photo, text="")
                except Exception:
                    pass
            img_lbl.pack(pady=(0, 4))

            tb.Label(card, text=data['name'],
                     font=("Helvetica", 10, "bold"),
                     wraplength=150, justify=CENTER).pack()
            tb.Label(card, text=f"${float(data['price']):.2f}",
                     font=("Helvetica", 10), bootstyle=SUCCESS).pack()

            stock_val = data['stock'] if data['stock'] is not None else 0
            tb.Label(card, text=f"Stock: {stock_val}",
                     font=("Helvetica", 9),
                     bootstyle=WARNING if stock_val < 10 else INFO).pack(pady=(2, 6))

            qty_var = tb.IntVar(value=1)
            row_f = tb.Frame(card)
            row_f.pack()
            tb.Label(row_f, text="Qty:").pack(side=LEFT, padx=(0, 4))
            tb.Spinbox(row_f, from_=1, to=max(1, stock_val),
                       textvariable=qty_var, width=5).pack(side=LEFT)

            tb.Button(card, text="Add to Cart",
                      bootstyle=(SUCCESS, OUTLINE), width=13,
                      command=lambda iid=item_id, qv=qty_var:
                          self.add_to_cart(iid, qv.get())).pack(pady=(6, 0))

    def add_to_cart(self, item_id, quantity):
        if item_id not in self.menu_data:
            return
        quantity = max(1, int(quantity))
        for row in self.order_cart:
            if row['item_id'] == item_id:
                row['quantity'] += quantity
                self.refresh_cart_view()
                return
        data = self.menu_data[item_id]
        self.order_cart.append({
            'item_id':  item_id,
            'name':     data['name'],
            'price':    float(data['price']),
            'quantity': quantity
        })
        self.refresh_cart_view()

    def refresh_cart_view(self):
        for i in self.tree_cart.get_children():
            self.tree_cart.delete(i)
        total = 0.0
        for row in self.order_cart:
            sub = row['price'] * row['quantity']
            total += sub
            self.tree_cart.insert('', END,
                values=(row['name'], row['quantity'], f"${sub:.2f}"))
        self.lbl_total.config(text=f"Total: ${total:.2f}")

    def remove_cart_item(self):
        sel = self.tree_cart.selection()
        if not sel:
            return
        idx = self.tree_cart.index(sel[0])
        if 0 <= idx < len(self.order_cart):
            self.order_cart.pop(idx)
        self.refresh_cart_view()

    def place_order_from_cart(self):
        table = self.ent_table.get().strip()
        if not table.isdigit():
            Messagebox.show_warning("Enter a valid table number.", "Input Error")
            return
        if not self.order_cart:
            Messagebox.show_warning("Your cart is empty.", "Empty Cart")
            return
        try:
            self.cursor.execute(
                "SELECT order_id FROM orders "
                "WHERE table_number=%s AND status='Pending'", (table,))
            existing = self.cursor.fetchone()
            order_id = existing[0] if existing else None

            if not order_id:
                self.cursor.execute(
                    "INSERT INTO orders (table_number, employee_id) "
                    "VALUES (%s, %s) RETURNING order_id",
                    (table, self.current_user['id']))
                order_id = self.cursor.fetchone()[0]

            for row in self.order_cart:
                self.cursor.execute(
                    "INSERT INTO order_items (order_id, item_id, quantity) "
                    "VALUES (%s, %s, %s)",
                    (order_id, row['item_id'], row['quantity']))

            self.conn.commit()
            Messagebox.show_info(
                f"Order #{order_id} placed for Table {table}!\n"
                f"{len(self.order_cart)} item(s) added.", "Order Placed")
            self.order_cart.clear()
            self.refresh_cart_view()
            self.load_menu_data()
        except Exception as e:
            self.conn.rollback()
            Messagebox.show_error(f"Order failed:\n{e}", "Error")

    # ─────────────────────────── BILLING TAB ───────────────────────────
    def setup_billing_tab(self):
        top = tb.Frame(self.tab_billing)
        top.pack(fill=X, pady=10)
        tb.Label(top, text="Table #:", font=("Helvetica", 12)).pack(side=LEFT, padx=10)
        self.ent_bill_table = tb.Entry(top, width=10)
        self.ent_bill_table.pack(side=LEFT, padx=5)
        tb.Button(top, text="Generate Receipt", bootstyle=INFO,
                  command=self.generate_bill).pack(side=LEFT, padx=10)

        self.txt_bill = tb.Text(self.tab_billing, height=20, width=80,
                                font=("Courier", 10))
        self.txt_bill.pack(pady=10)
        self.txt_bill.config(state=DISABLED)

        self.btn_pay = tb.Button(self.tab_billing, text="Complete Payment",
                                 bootstyle=SUCCESS, state=DISABLED,
                                 command=self.checkout)
        self.btn_pay.pack(pady=10)
        self.active_bill_id = None

    def generate_bill(self):
        table = self.ent_bill_table.get()
        if not table.isdigit():
            return
        self.cursor.execute(
            "SELECT order_id, total_amount FROM orders "
            "WHERE table_number=%s AND status='Pending'", (table,))
        order = self.cursor.fetchone()

        self.txt_bill.config(state=NORMAL)
        self.txt_bill.delete(1.0, END)

        if not order:
            self.txt_bill.insert(END, f"\n   No pending orders for Table {table}.")
            self.btn_pay.config(state=DISABLED)
        else:
            self.active_bill_id, total = order[0], order[1]
            self.cursor.execute(
                "SELECT m.name, oi.quantity, m.price, (oi.quantity * m.price) "
                "FROM order_items oi JOIN menu_items m ON oi.item_id=m.item_id "
                "WHERE oi.order_id=%s", (self.active_bill_id,))
            items = self.cursor.fetchall()

            res  = f"{'RESTROCORE BILLING':^60}\n"
            res += f" Table: {table:<10} | Order ID: {self.active_bill_id}\n"
            res += "-" * 60 + "\n"
            res += f" {'Item':<25} {'Qty':<8} {'Price':<10} {'Sub'}\n"
            res += "-" * 60 + "\n"
            for item in items:
                res += f" {item[0][:24]:<25} {item[1]:<8} ${item[2]:<9} ${item[3]}\n"
            res += "-" * 60 + "\n"
            res += f" {'TOTAL DUE:':<44} ${total}\n"
            res += "=" * 60 + "\n"

            self.txt_bill.insert(END, res)
            self.btn_pay.config(state=NORMAL)

        self.txt_bill.config(state=DISABLED)

    def checkout(self):
        try:
            self.cursor.execute(
                "UPDATE orders SET status='Paid' WHERE order_id=%s",
                (self.active_bill_id,))
            self.conn.commit()
            Messagebox.show_info("Table Cleared.", "Success")
            self.generate_bill()
        except Exception as e:
            self.conn.rollback()
            Messagebox.show_error(str(e), "Error")

    # ─────────────────────────── STAFF TAB ───────────────────────────
    def setup_staff_tab(self):
        form = tb.Frame(self.tab_staff)
        form.pack(pady=20)
        self.staff_entries = []
        for i, label in enumerate(["Full Name:", "Position:", "Username:", "Password:"]):
            tb.Label(form, text=label).grid(row=i, column=0, padx=5, pady=8, sticky=E)
            e = tb.Entry(form, width=30)
            if "Password" in label:
                e.config(show="*")
            e.grid(row=i, column=1, padx=5, pady=8)
            self.staff_entries.append(e)
        tb.Button(form, text="Register Employee", bootstyle=PRIMARY,
                  command=self.add_staff).grid(row=4, columnspan=2, pady=20)

    def add_staff(self):
        vals = [e.get() for e in self.staff_entries]
        if not all(vals):
            return
        try:
            self.cursor.execute(
                "INSERT INTO employees (name, role, username, password) "
                "VALUES (%s,%s,%s,%s)", vals)
            self.conn.commit()
            Messagebox.show_info("Staff Registered", "Success")
            for e in self.staff_entries:
                e.delete(0, END)
        except Exception as e:
            self.conn.rollback()
            Messagebox.show_error(str(e), "DB Error")

    # ─────────────────────────── MISC ────────────────────────────────
    def logout(self):
        self.order_cart.clear()
        for w in self.root.winfo_children():
            w.destroy()
        self.build_login_screen()

    def on_closing(self):
        if hasattr(self, 'conn'):
            self.conn.close()
        self.root.destroy()


if __name__ == "__main__":
    app_root = tb.Window(themename="cyborg")
    RestroCoreApp(app_root)
    app_root.mainloop()
