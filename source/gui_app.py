import ttkbootstrap as tb
from ttkbootstrap.constants import *
from ttkbootstrap.dialogs import Messagebox
import psycopg2
import os

# Image handling with fallback
try:
    from PIL import Image, ImageTk
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

# Database Connection Configuration
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
        self.root.geometry("1150x800")
        self.root.position_center()
        
        self.current_user = None
        self.placeholder_img = None
        self.menu_image_map = {}

        # Database Connection
        try:
            self.conn = psycopg2.connect(**DB_CONFIG)
            self.cursor = self.conn.cursor()
        except Exception as e:
            Messagebox.show_error(f"Database Connection Failed:\n{e}", "Database Error")
            self.root.destroy()
            return

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.build_login_screen()

    # ================= LOGIN SCREEN =================
    def build_login_screen(self):
        self.login_frame = tb.Frame(self.root, padding=40)
        self.login_frame.pack(expand=True)

        tb.Label(self.login_frame, text="RestroCore", font=("Helvetica", 36, "bold"), bootstyle=INFO).pack(pady=10)
        tb.Label(self.login_frame, text="Restaurant Management System", font=("Helvetica", 12)).pack(pady=5)

        self.ent_user = tb.Entry(self.login_frame, font=("Helvetica", 12), width=30)
        self.ent_user.insert(0, "alice_mgr") # Default for testing
        self.ent_user.pack(pady=10)

        self.ent_pass = tb.Entry(self.login_frame, font=("Helvetica", 12), width=30, show="*")
        self.ent_pass.insert(0, "password123")
        self.ent_pass.pack(pady=10)

        btn_login = tb.Button(self.login_frame, text="Login", bootstyle=SUCCESS, width=28, command=self.attempt_login)
        btn_login.pack(pady=20)

        # Keyboard Shortcut: Enter to login
        self.root.bind('<Return>', lambda event: self.attempt_login())

    def attempt_login(self):
        username = self.ent_user.get()
        password = self.ent_pass.get()

        self.cursor.execute("SELECT employee_id, name, role FROM employees WHERE username = %s AND password = %s", (username, password))
        user = self.cursor.fetchone()

        if user:
            self.current_user = {"id": user[0], "name": user[1], "role": user[2]}
            self.root.unbind('<Return>') 
            self.login_frame.destroy()
            self.build_main_dashboard()
        else:
            Messagebox.show_error("Invalid username or password.", "Login Failed")

    # ================= MAIN DASHBOARD =================
    def build_main_dashboard(self):
        # Header Bar
        header = tb.Frame(self.root, bootstyle=DARK, padding=15)
        header.pack(fill=X)
        
        tb.Label(header, text=f"👤 {self.current_user['name']} | Role: {self.current_user['role']}", 
                 font=("Helvetica", 12), bootstyle=INVERSE).pack(side=LEFT)
        
        tb.Button(header, text="Logout", bootstyle=(DANGER, OUTLINE), command=self.logout).pack(side=RIGHT)

        # Tabbed Navigation
        self.tab_control = tb.Notebook(self.root, bootstyle=INFO)
        self.tab_control.pack(expand=True, fill=BOTH, padx=20, pady=20)
        
        # Initialize Frames
        self.tab_menu = tb.Frame(self.tab_control, padding=10)
        self.tab_orders = tb.Frame(self.tab_control, padding=10)
        self.tab_billing = tb.Frame(self.tab_control, padding=10)
        
        # Add Tabs
        self.tab_control.add(self.tab_menu, text='📋 Menu & Inventory')
        self.tab_control.add(self.tab_orders, text='🍔 Place Order')
        self.tab_control.add(self.tab_billing, text='💳 Billing')
        
        if self.current_user['role'].lower() == 'manager':
            self.tab_staff = tb.Frame(self.tab_control, padding=10)
            self.tab_control.add(self.tab_staff, text='👥 Staff Management')
            self.setup_staff_tab()
        
        # Setup Content
        self.setup_menu_tab()
        self.setup_order_tab()
        self.setup_billing_tab()

    # ================= MENU TAB (WITH IMAGES) =================
    def setup_menu_tab(self):
        container = tb.Frame(self.tab_menu)
        container.pack(fill=BOTH, expand=True)

        # Left Column: Table
        left_frame = tb.Frame(container)
        left_frame.pack(side=LEFT, fill=BOTH, expand=True)

        columns = ('id', 'name', 'price', 'stock')
        self.tree_menu = tb.Treeview(left_frame, columns=columns, show='headings', bootstyle=PRIMARY)
        for col in columns:
            self.tree_menu.heading(col, text=col.capitalize())
        
        self.tree_menu.column('id', width=50, anchor=CENTER)
        self.tree_menu.column('name', width=250)
        self.tree_menu.pack(fill=BOTH, expand=True)
        self.tree_menu.bind('<<TreeviewSelect>>', self.on_menu_select)

        tb.Button(left_frame, text="↻ Refresh List", bootstyle=INFO, command=self.load_menu_data).pack(pady=10)

        # FIX: Removed 'padding=10' from LabelFrame constructor
        self.preview_frame = tb.LabelFrame(container, text=" Item Preview ")
        self.preview_frame.pack(side=RIGHT, fill=Y, padx=10, pady=20)

        # CHANGE: Pacman image in the middle-top, with bottom space
        self.img_label = tb.Label(self.preview_frame, text="Select an item\nto view image", 
                                  font=("Helvetica", 10))
        self.img_label.pack(side=TOP, expand=True, fill=BOTH, anchor=N, pady=(0, 20))

        self.load_menu_data()

    def load_menu_data(self):
        for i in self.tree_menu.get_children(): self.tree_menu.delete(i)
        self.cursor.execute("SELECT item_id, name, price, stock_level, image_path FROM menu_items ORDER BY item_id")
        rows = self.cursor.fetchall()
        for row in rows:
            self.menu_image_map[str(row[0])] = row[4]
            self.tree_menu.insert('', END, values=row[:4])

    def on_menu_select(self, event):
        selected = self.tree_menu.selection()
        if not selected: return
        
        item_id = str(self.tree_menu.item(selected[0])['values'][0])
        img_path = self.menu_image_map.get(item_id)

        if HAS_PIL and img_path and os.path.exists(img_path):
            try:
                img = Image.open(img_path).resize((280, 280), Image.Resampling.LANCZOS)
                self.placeholder_img = ImageTk.PhotoImage(img)
                self.img_label.config(image=self.placeholder_img, text="")
            except:
                self.img_label.config(image='', text="Image Format Error")
        else:
            self.img_label.config(image='', text="No Image Available")

    # ================= ORDER TAB =================
    def setup_order_tab(self):
        form = tb.Frame(self.tab_orders)
        form.pack(pady=30)

        labels = [("Table Number:", "t"), ("Menu Item ID:", "i"), ("Quantity:", "q")]
        self.order_vars = {}

        for i, (txt, key) in enumerate(labels):
            tb.Label(form, text=txt, font=("Helvetica", 11)).grid(row=i, column=0, padx=10, pady=10, sticky=E)
            ent = tb.Entry(form, width=25)
            ent.grid(row=i, column=1, pady=10)
            self.order_vars[key] = ent

        tb.Button(form, text="Add to Order", bootstyle=SUCCESS, width=20, command=self.place_order).grid(row=3, columnspan=2, pady=20)

    def place_order(self):
        t, i, q = self.order_vars['t'].get(), self.order_vars['i'].get(), self.order_vars['q'].get()
        if not (t.isdigit() and i.isdigit() and q.isdigit()):
            Messagebox.show_warning("Please use numbers only.", "Input Error")
            return

        try:
            self.cursor.execute("SELECT order_id FROM orders WHERE table_number = %s AND status = 'Pending'", (t,))
            existing = self.cursor.fetchone()
            order_id = existing[0] if existing else None

            if not order_id:
                self.cursor.execute("INSERT INTO orders (table_number, employee_id) VALUES (%s, %s) RETURNING order_id", (t, self.current_user['id']))
                order_id = self.cursor.fetchone()[0]

            self.cursor.execute("INSERT INTO order_items (order_id, item_id, quantity) VALUES (%s, %s, %s)", (order_id, i, q))
            self.conn.commit()
            Messagebox.show_info(f"Added to Order #{order_id}", "Success")
            self.load_menu_data()
        except Exception as e:
            self.conn.rollback()
            Messagebox.show_error(f"Check stock or ID: {e}", "Order Failed")

    # ================= BILLING TAB =================
    def setup_billing_tab(self):
        top = tb.Frame(self.tab_billing)
        top.pack(fill=X, pady=10)

        tb.Label(top, text="Table #:", font=("Helvetica", 12)).pack(side=LEFT, padx=10)
        self.ent_bill_table = tb.Entry(top, width=10)
        self.ent_bill_table.pack(side=LEFT, padx=5)
        tb.Button(top, text="Generate Receipt", bootstyle=INFO, command=self.generate_bill).pack(side=LEFT, padx=10)

        self.txt_bill = tb.Text(self.tab_billing, height=20, width=80, font=("Courier", 10))
        self.txt_bill.pack(pady=10)
        self.txt_bill.config(state=DISABLED)

        self.btn_pay = tb.Button(self.tab_billing, text="Complete Payment", bootstyle=SUCCESS, state=DISABLED, command=self.checkout)
        self.btn_pay.pack(pady=10)
        self.active_bill_id = None

    def generate_bill(self):
        table = self.ent_bill_table.get()
        if not table.isdigit(): return

        self.cursor.execute("SELECT order_id, total_amount FROM orders WHERE table_number = %s AND status = 'Pending'", (table,))
        order = self.cursor.fetchone()

        self.txt_bill.config(state=NORMAL)
        self.txt_bill.delete(1.0, END)

        if not order:
            self.txt_bill.insert(END, f"\n   No pending orders for Table {table}.")
            self.btn_pay.config(state=DISABLED)
        else:
            self.active_bill_id, total = order[0], order[1]
            self.cursor.execute("SELECT m.name, oi.quantity, m.price, (oi.quantity * m.price) FROM order_items oi JOIN menu_items m ON oi.item_id = m.item_id WHERE oi.order_id = %s", (self.active_bill_id,))
            items = self.cursor.fetchall()

            res = f"{'RESTROCORE BILLING':^60}\n"
            res += f" Table: {table:<10} | Order ID: {self.active_bill_id}\n"
            res += "-"*60 + "\n"
            res += f" {'Item':<25} {'Qty':<8} {'Price':<10} {'Sub'}\n"
            res += "-"*60 + "\n"
            for item in items:
                res += f" {item[0][:24]:<25} {item[1]:<8} ${item[2]:<9} ${item[3]}\n"
            res += "-"*60 + "\n"
            res += f" {'TOTAL DUE:':<44} ${total}\n"
            res += "="*60 + "\n"

            self.txt_bill.insert(END, res)
            self.btn_pay.config(state=NORMAL)
        self.txt_bill.config(state=DISABLED)

    def checkout(self):
        try:
            self.cursor.execute("UPDATE orders SET status = 'Paid' WHERE order_id = %s", (self.active_bill_id,))
            self.conn.commit()
            Messagebox.show_info("Table Cleared.", "Success")
            self.generate_bill()
        except Exception as e:
            self.conn.rollback()
            Messagebox.show_error(str(e), "Error")

    # ================= STAFF TAB =================
    def setup_staff_tab(self):
        form = tb.Frame(self.tab_staff)
        form.pack(pady=20)
        
        self.staff_entries = []
        labels = ["Full Name:", "Position:", "Username:", "Password:"]
        
        for i, label in enumerate(labels):
            tb.Label(form, text=label).grid(row=i, column=0, padx=5, pady=8, sticky=E)
            e = tb.Entry(form, width=30)
            if "Password" in label: e.config(show="*")
            e.grid(row=i, column=1, padx=5, pady=8)
            self.staff_entries.append(e)

        tb.Button(form, text="Register Employee", bootstyle=PRIMARY, command=self.add_staff).grid(row=4, columnspan=2, pady=20)

    def add_staff(self):
        vals = [e.get() for e in self.staff_entries]
        if not all(vals): return
        try:
            self.cursor.execute("INSERT INTO employees (name, role, username, password) VALUES (%s,%s,%s,%s)", vals)
            self.conn.commit()
            Messagebox.show_info("Staff Registered", "Success")
            for e in self.staff_entries: e.delete(0, END)
        except Exception as e:
            self.conn.rollback()
            Messagebox.show_error(str(e), "DB Error")

    def logout(self):
        for widget in self.root.winfo_children(): widget.destroy()
        self.build_login_screen()

    def on_closing(self):
        if hasattr(self, 'conn'): self.conn.close()
        self.root.destroy()

if __name__ == "__main__":
    app_root = tb.Window(themename="cyborg")
    app = RestroCoreApp(app_root)
    app_root.mainloop()