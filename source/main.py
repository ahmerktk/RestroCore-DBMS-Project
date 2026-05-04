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

# Database configuration
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

    # ─────────────────────────── LOGIN ───────────────────────────
    def build_login_screen(self):
        # Clear any existing widgets
        for w in self.root.winfo_children():
            w.destroy()

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
        
        try:
            self.cursor.execute(
                "SELECT employee_id, name, role FROM employees "
                "WHERE username=%s AND password=%s", (username, password))
            user = self.cursor.fetchone()
            
            if user:
                self.current_user = {"id": user[0], "name": user[1], "role": user[2]}
                self.root.unbind('<Return>')
                self.build_main_dashboard()
            else:
                Messagebox.show_error("Invalid username or password.", "Login Failed")
        except Exception as e:
            Messagebox.show_error(f"Login Error: {e}", "Error")

    # ─────────────────────────── DASHBOARD ───────────────────────────
    def build_main_dashboard(self):
        # Clear login screen
        for w in self.root.winfo_children():
            w.destroy()

        # Header bar
        header = tb.Frame(self.root, bootstyle=DARK, padding=15)
        header.pack(fill=X)
        tb.Label(header,
                 text=f"👤 {self.current_user['name']} | Role: {self.current_user['role']}",
                 font=("Helvetica", 12), bootstyle=INVERSE).pack(side=LEFT)
        
        tb.Button(header, text="Logout", bootstyle=(DANGER, OUTLINE),
                  command=self.logout).pack(side=RIGHT)

        # Tabs
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

        # Initialize UI Components
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
        self.img_label.pack(expand=True, fill=BOTH, pady=(0, 20), padx=10)

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

        # Only rebuild cards if the Order Tab UI is ready
        if hasattr(self, '_order_tab_ready'):
            self.build_food_cards()

    def on_menu_select(self, event):
        sel = self.tree_menu.selection()
        if not sel: return
        
        item_id = str(self.tree_menu.item(sel[0])['values'][0])
        img_path = self.menu_image_map.get(item_id)
        
        if HAS_PIL and img_path and os.path.exists(img_path):
            try:
                img = Image.open(img_path).resize((280, 280), Image.Resampling.LANCZOS)
                self.placeholder_img = ImageTk.PhotoImage(img)
                self.img_label.config(image=self.placeholder_img, text="")
                return
            except Exception: pass
        
        self.img_label.config(image='', text="No Image Available")

    # ─────────────────────────── ORDER TAB ───────────────────────────
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

        # Right Cart Panel
        right_panel = tb.Frame(main, width=300)
        right_panel.pack(side=RIGHT, fill=Y, padx=(10, 0))
        right_panel.pack_propagate(False)

        tb.Label(right_panel, text="🛒  Cart", font=("Helvetica", 12, "bold")).pack(anchor=W, pady=(0, 4))

        cart_cols = ('name', 'qty', 'sub')
        self.tree_cart = tb.Treeview(right_panel, columns=cart_cols, show='headings', bootstyle=SUCCESS, height=16)
        self.tree_cart.heading('name', text='Item'); self.tree_cart.heading('qty', text='Qty'); self.tree_cart.heading('sub', text='Subtotal')
        self.tree_cart.column('name', width=140); self.tree_cart.column('qty', width=50, anchor=CENTER); self.tree_cart.column('sub', width=90, anchor=E)
        self.tree_cart.pack(fill=BOTH, expand=True)

        tb.Button(right_panel, text="✕ Remove Selected", bootstyle=(DANGER, OUTLINE), command=self.remove_cart_item).pack(fill=X, pady=(6, 2))

        self.lbl_total = tb.Label(right_panel, text="Total: $0.00", font=("Helvetica", 12, "bold"), bootstyle=WARNING)
        self.lbl_total.pack(anchor=E, pady=4)

        tb.Button(right_panel, text="✔  Place Order", bootstyle=SUCCESS, command=self.place_order_from_cart).pack(fill=X, pady=(4, 0))

        # Left Grid Panel
        left_panel = tb.Frame(main)
        left_panel.pack(side=LEFT, fill=BOTH, expand=True)

        self.cards_canvas = tb.Canvas(left_panel, highlightthickness=0)
        vsb = tb.Scrollbar(left_panel, orient=VERTICAL, command=self.cards_canvas.yview)
        self.cards_canvas.configure(yscrollcommand=vsb.set)
        
        vsb.pack(side=RIGHT, fill=Y)
        self.cards_canvas.pack(side=LEFT, fill=BOTH, expand=True)

        self.cards_inner = tb.Frame(self.cards_canvas)
        self._canvas_win = self.cards_canvas.create_window((0, 0), window=self.cards_inner, anchor=NW)

        self.cards_inner.bind("<Configure>", lambda e: self.cards_canvas.configure(scrollregion=self.cards_canvas.bbox("all")))
        self.cards_canvas.bind("<Configure>", lambda e: self.cards_canvas.itemconfig(self._canvas_win, width=e.width))

        self._order_tab_ready = True
        self.build_food_cards()

    def build_food_cards(self):
        if not hasattr(self, 'cards_inner'): return
        for w in self.cards_inner.winfo_children(): w.destroy()
        self.thumb_refs.clear()

        search = self.search_var.get().lower()
        items = [(iid, d) for iid, d in self.menu_data.items() if search in d['name'].lower()]

        COLS = 3
        for idx, (item_id, data) in enumerate(items):
            r, c = divmod(idx, COLS)
            card = tb.Frame(self.cards_inner, bootstyle=SECONDARY, padding=10)
            card.grid(row=r, column=c, padx=8, pady=8, sticky=NSEW)
            self.cards_inner.columnconfigure(c, weight=1)

            # Image logic
            img_lbl = tb.Label(card, text="🍽", font=("Helvetica", 32))
            if HAS_PIL and data['image_path'] and os.path.exists(data['image_path']):
                try:
                    p_img = Image.open(data['image_path']).resize((100, 100), Image.Resampling.LANCZOS)
                    photo = ImageTk.PhotoImage(p_img)
                    self.thumb_refs[item_id] = photo
                    img_lbl.config(image=photo, text="")
                except: pass
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
        for i in self.tree_cart.get_children(): self.tree_cart.delete(i)
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

    def place_order_from_cart(self):
        table = self.ent_table.get().strip()
        if not table.isdigit() or not self.order_cart:
            Messagebox.show_warning("Invalid table or empty cart", "Warning")
            return
        
        try:
            self.cursor.execute("INSERT INTO orders (table_number, employee_id) VALUES (%s, %s) RETURNING order_id", 
                               (table, self.current_user['id']))
            order_id = self.cursor.fetchone()[0]
            for row in self.order_cart:
                self.cursor.execute("INSERT INTO order_items (order_id, item_id, quantity) VALUES (%s, %s, %s)",
                                   (order_id, row['item_id'], row['quantity']))
            self.conn.commit()
            Messagebox.show_info(f"Order #{order_id} placed!", "Success")
            self.order_cart.clear()
            self.refresh_cart_view()
        except Exception as e:
            self.conn.rollback()
            Messagebox.show_error(str(e), "Error")

    # ─────────────────────────── BILLING TAB ───────────────────────────
    def setup_billing_tab(self):
        top = tb.Frame(self.tab_billing)
        top.pack(fill=X, pady=10)
        tb.Label(top, text="Table #:").pack(side=LEFT, padx=10)
        self.ent_bill_table = tb.Entry(top, width=10)
        self.ent_bill_table.pack(side=LEFT, padx=5)
        tb.Button(top, text="Generate Bill", command=self.generate_bill).pack(side=LEFT, padx=10)

        self.txt_bill = tb.Text(self.tab_billing, height=18, width=70, font=("Courier", 10))
        self.txt_bill.pack(pady=10)
        self.btn_pay = tb.Button(self.tab_billing, text="Mark as Paid", state=DISABLED, command=self.checkout)
        self.btn_pay.pack()

    def generate_bill(self):
        table = self.ent_bill_table.get()
        if not table.isdigit(): return
        
        self.cursor.execute("SELECT order_id, total_amount FROM orders WHERE table_number=%s AND status='Pending'", (table,))
        order = self.cursor.fetchone()
        
        self.txt_bill.config(state=NORMAL)
        self.txt_bill.delete(1.0, END)
        
        if order:
            self.active_bill_id = order[0]
            self.txt_bill.insert(END, f"Order ID: {order[0]}\nTable: {table}\nTotal Due: ${order[1]}\n")
            self.btn_pay.config(state=NORMAL)
        else:
            self.txt_bill.insert(END, "No pending orders.")
            self.btn_pay.config(state=DISABLED)
        self.txt_bill.config(state=DISABLED)

    def checkout(self):
        self.cursor.execute("UPDATE orders SET status='Paid' WHERE order_id=%s", (self.active_bill_id,))
        self.conn.commit()
        Messagebox.show_info("Payment Complete", "Success")
        self.generate_bill()

    # ─────────────────────────── STAFF TAB ───────────────────────────
    def setup_staff_tab(self):
        form = tb.Frame(self.tab_staff)
        form.pack(pady=20)
        self.staff_entries = []
        labels = ["Full Name:", "Position:", "Username:", "Password:"]
        for i, lbl in enumerate(labels):
            tb.Label(form, text=lbl).grid(row=i, column=0, sticky=E, padx=5, pady=5)
            e = tb.Entry(form, width=25, show="*" if "Password" in lbl else "")
            e.grid(row=i, column=1, padx=5, pady=5)
            self.staff_entries.append(e)
        tb.Button(form, text="Add Staff", command=self.add_staff).grid(row=4, columnspan=2, pady=10)

    def add_staff(self):
        vals = [e.get() for e in self.staff_entries]
        if all(vals):
            self.cursor.execute("INSERT INTO employees (name, role, username, password) VALUES (%s,%s,%s,%s)", vals)
            self.conn.commit()
            Messagebox.show_info("Staff Added", "Success")

    # ─────────────────────────── LOGOUT & CLOSING ────────────────────
    def logout(self):
        # Reset state
        self.order_cart = []
        self.thumb_refs = {}
        if hasattr(self, '_order_tab_ready'):
            del self._order_tab_ready
        
        # Destroy all current UI
        for w in self.root.winfo_children():
            w.destroy()
        
        # Rebuild login
        self.build_login_screen()

    def on_closing(self):
        if hasattr(self, 'conn'):
            self.conn.close()
        self.root.destroy()

if __name__ == "__main__":
    app_root = tb.Window(themename="cyborg")
    RestroCoreApp(app_root)
    app_root.mainloop()

try:
    app_root.mainloop()
except KeyboardInterrupt:
    print("Program stopped by user.")
    # Perform any cleanup here if necessary