"""
RestroCore Management System
Requires: pip install ttkbootstrap psycopg2-binary
"""

import tkinter as tk
from tkinter import messagebox
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.tableview import Tableview
from datetime import datetime
import psycopg2
import psycopg2.pool

# ═══════════════════════════════════════════════════════════
#  DATABASE MANAGER
# ═══════════════════════════════════════════════════════════
class DB:
    _pool = None

    @classmethod
    def init(cls, **kw):
        cls._pool = psycopg2.pool.ThreadedConnectionPool(1, 10, **kw)

    @classmethod
    def _conn(cls):
        return cls._pool.getconn()

    @classmethod
    def _release(cls, c):
        cls._pool.putconn(c)

    @classmethod
    def run(cls, sql, params=None, fetch=False):
        conn = cls._conn()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, params or ())
                result = cur.fetchall() if fetch else None
            conn.commit()
            return result
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cls._release(conn)

    @classmethod
    def call(cls, func, params):
        ph = ",".join(["%s"] * len(params))
        cls.run(f"SELECT {func}({ph})", params)


# ═══════════════════════════════════════════════════════════
#  LOGIN DIALOG
# ═══════════════════════════════════════════════════════════
class LoginDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("RestroCore - Login")
        self.geometry("380x320")
        self.resizable(False, False)
        self.grab_set()
        self.employee = None
        self._demo    = False
        self._build()

    def _build(self):
        self.configure(bg="#0f1923")
        ttk.Label(self, text="RestroCore", font=("Georgia", 22, "bold"),
                  bootstyle="warning").pack(pady=(28, 4))
        ttk.Label(self, text="Employee Login", font=("Helvetica", 10),
                  bootstyle="secondary").pack()

        frm = ttk.Frame(self)
        frm.pack(padx=40, pady=20, fill=X)

        ttk.Label(frm, text="Username").pack(anchor=W)
        self._user = ttk.Entry(frm, bootstyle="warning")
        self._user.pack(fill=X, pady=(2, 10))
        self._user.focus()

        ttk.Label(frm, text="Password").pack(anchor=W)
        self._pw = ttk.Entry(frm, show="*", bootstyle="warning")
        self._pw.pack(fill=X, pady=(2, 16))
        self._pw.bind("<Return>", lambda _: self._login())

        ttk.Button(frm, text="Login", bootstyle="warning",
                   command=self._login).pack(fill=X, pady=2)
        ttk.Button(frm, text="Skip (Demo Mode)", bootstyle="secondary-outline",
                   command=self._demo_mode).pack(fill=X, pady=2)

    def _login(self):
        u, p = self._user.get().strip(), self._pw.get().strip()
        try:
            rows = DB.run(
                "SELECT employee_id, name, role FROM employees "
                "WHERE username=%s AND password=%s", (u, p), fetch=True)
            if rows:
                self.employee = rows[0]
                self.destroy()
            else:
                messagebox.showerror("Login Failed", "Invalid username or password.", parent=self)
        except Exception as e:
            messagebox.showerror("DB Error", str(e), parent=self)

    def _demo_mode(self):
        self._demo = True
        self.destroy()


# ═══════════════════════════════════════════════════════════
#  CONNECTION DIALOG
# ═══════════════════════════════════════════════════════════
class ConnectDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Connect to PostgreSQL")
        self.geometry("400x310")
        self.resizable(False, False)
        self.grab_set()
        self.result = None
        self._build()

    def _build(self):
        self.configure(bg="#0f1923")
        ttk.Label(self, text="Database Connection",
                  font=("Helvetica", 13, "bold"),
                  bootstyle="info").pack(pady=(20, 10))

        frm = ttk.Frame(self)
        frm.pack(padx=30, fill=X)

        self._fields = {}
        for label, default in [("Host","localhost"), ("Port","5432"),
                               ("Database","restrocore"),
                               ("Username","postgres"), ("Password","")]:
            row = ttk.Frame(frm)
            row.pack(fill=X, pady=3)
            ttk.Label(row, text=label, width=11, anchor=W).pack(side=LEFT)
            e = ttk.Entry(row, show="*" if label == "Password" else "", bootstyle="info")
            e.insert(0, default)
            e.pack(side=LEFT, fill=X, expand=YES)
            self._fields[label] = e

        ttk.Button(self, text="Connect", bootstyle="info", width=18,
                   command=self._connect).pack(pady=(14, 4))
        ttk.Button(self, text="Demo (no DB)", bootstyle="secondary-outline", width=18,
                   command=self._demo).pack()

    def _connect(self):
        f = self._fields
        self.result = dict(
            host=f["Host"].get(), port=int(f["Port"].get()),
            dbname=f["Database"].get(),
            user=f["Username"].get(), password=f["Password"].get()
        )
        self.destroy()

    def _demo(self):
        self.result = "demo"
        self.destroy()


# ═══════════════════════════════════════════════════════════
#  MAIN APPLICATION
# ═══════════════════════════════════════════════════════════
class RestroCoreApp(ttk.Window):
    DEMO = False

    def __init__(self):
        super().__init__(themename="darkly")
        self.withdraw()  # Hide main window during login sequence
        self.title("RestroCore Management System")
        self.geometry("1150x720")
        self.minsize(950, 600)
        self._current_employee = None

        self._init_db()
        if not self.DEMO:
            self._do_login()

        self._build_ui()
        self._on_tab_change()
        self.deiconify()  # Reveal the main UI cleanly

    # ── startup ────────────────────────────────────────────
    def _init_db(self):
        dlg = ConnectDialog(self)
        self.wait_window(dlg)
        if dlg.result == "demo":
            self.DEMO = True
            return
        if dlg.result is None:
            self.destroy(); exit()
        try:
            DB.init(**dlg.result)
        except Exception as e:
            messagebox.showerror("Connection Error", str(e))
            self.DEMO = True

    def _do_login(self):
        dlg = LoginDialog(self)
        self.wait_window(dlg)
        if dlg._demo:
            self.DEMO = True
            return
        if dlg.employee is None:
            self.destroy(); exit()
        self._current_employee = dlg.employee

    def q(self, sql, params=None, fetch=False):
        if self.DEMO:
            return [] if fetch else None
        return DB.run(sql, params, fetch)

    # ── top bar + notebook ─────────────────────────────────
    def _build_ui(self):
        bar = ttk.Frame(self, bootstyle="dark")
        bar.pack(fill=X)
        ttk.Label(bar, text="RestroCore",
                  font=("Georgia", 15, "bold"),
                  bootstyle="warning").pack(side=LEFT, padx=18, pady=7)

        if self._current_employee:
            eid, name, role = self._current_employee
            ttk.Label(bar, text=f"  Logged in: {name}  |  {role}  |  ID #{eid}",
                      font=("Helvetica", 9), bootstyle="secondary").pack(side=LEFT, padx=8)

        self._clk = ttk.Label(bar, font=("Courier", 9), bootstyle="secondary")
        self._clk.pack(side=RIGHT, padx=16)
        self._tick()

        self.nb = ttk.Notebook(self)
        self.nb.pack(fill=BOTH, expand=YES, padx=10, pady=6)

        self._t_dash  = ttk.Frame(self.nb)
        self._t_order = ttk.Frame(self.nb)
        self._t_menu  = ttk.Frame(self.nb)
        self._t_emp   = ttk.Frame(self.nb)
        self._t_supp  = ttk.Frame(self.nb)
        self._t_stock = ttk.Frame(self.nb)

        self.nb.add(self._t_dash,  text="  Dashboard  ")
        self.nb.add(self._t_order, text="  Orders & Billing  ")
        self.nb.add(self._t_menu,  text="  Menu & Stock  ")
        self.nb.add(self._t_emp,   text="  Employees  ")
        self.nb.add(self._t_supp,  text="  Suppliers  ")
        self.nb.add(self._t_stock, text="  Supply Orders  ")

        self._build_dashboard()
        self._build_orders()
        self._build_menu()
        self._build_employees()
        self._build_suppliers()
        self._build_supply_orders()

        self.nb.bind("<<NotebookTabChanged>>", lambda _: self._on_tab_change())

    def _tick(self):
        self._clk.config(text=datetime.now().strftime("  %a %d %b %Y   %H:%M:%S  "))
        self.after(1000, self._tick)

    def _on_tab_change(self):
        idx = self.nb.index(self.nb.select()) if self.nb.tabs() else 0
        [self._refresh_dashboard, self._refresh_orders, self._refresh_menu,
         self._refresh_employees, self._refresh_suppliers,
         self._refresh_supply_orders][idx]()

    # ═══════════════════════════════════════════════════════
    #  DASHBOARD
    # ═══════════════════════════════════════════════════════
    def _build_dashboard(self):
        top = ttk.Frame(self._t_dash)
        top.pack(fill=X, padx=20, pady=14)

        self._sv = {}
        for key, label, style in [
            ("orders",    "Total Orders",      "info"),
            ("revenue",   "Total Revenue",      "success"),
            ("employees", "Employees",          "warning"),
            ("low_stock", "Low Stock (<10)",    "danger"),
        ]:
            c = ttk.LabelFrame(top, text=label, bootstyle=style)
            c.pack(side=LEFT, fill=BOTH, expand=YES, padx=8)
            v = tk.StringVar(value="--")
            self._sv[key] = v
            ttk.Label(c, textvariable=v, font=("Georgia", 26, "bold"), bootstyle=style).pack(pady=12, padx=18)

        ttk.Separator(self._t_dash).pack(fill=X, padx=20, pady=4)
        ttk.Label(self._t_dash, text="Supplier Inventory  (view_supplier_inventory)",
                  font=("Helvetica", 11, "bold")).pack(anchor=W, padx=20)

        cols = [{"text":"Supplier"},{"text":"Item"},{"text":"Stock Level"},{"text":"Price (Rs.)"}]
        self._dash_inv = Tableview(self._t_dash, coldata=cols, rowdata=[],
                                   paginate=True, pagesize=8, bootstyle="info", stripecolor=("#1e2a38",""))
        self._dash_inv.pack(fill=BOTH, expand=YES, padx=20, pady=6)

    def _refresh_dashboard(self):
        r_ord = self.q("SELECT COUNT(*) FROM orders", fetch=True)
        r_rev = self.q("SELECT COALESCE(SUM(total_amount),0) FROM orders", fetch=True)
        r_emp = self.q("SELECT COUNT(*) FROM employees", fetch=True)
        r_low = self.q("SELECT COUNT(*) FROM menu_items WHERE stock_level < 10", fetch=True)

        self._sv["orders"].set(r_ord[0][0] if r_ord else "--")
        self._sv["revenue"].set(f"Rs.{r_rev[0][0]:.0f}" if r_rev else "--")
        self._sv["employees"].set(r_emp[0][0] if r_emp else "--")
        self._sv["low_stock"].set(r_low[0][0] if r_low else "--")

        try:
            rows = self.q("SELECT supplier_name, item_name, stock_level, price "
                          "FROM view_supplier_inventory ORDER BY supplier_name", fetch=True) or []
            self._dash_inv.delete_rows()
            for r in rows:
                self._dash_inv.insert_row("end", [r[0], r[1], r[2], f"{r[3]:.2f}"])
            self._dash_inv.load_table_data()
        except Exception:
            pass # Fails gracefully if view doesn't exist yet in DB

    # ═══════════════════════════════════════════════════════
    #  ORDERS
    # ═══════════════════════════════════════════════════════
    def _build_orders(self):
        pane = ttk.PanedWindow(self._t_order, orient=HORIZONTAL)
        pane.pack(fill=BOTH, expand=YES, padx=10, pady=10)

        left = ttk.Frame(pane, width=310)
        pane.add(left, weight=1)

        frm = ttk.LabelFrame(left, text="1. Create Order", bootstyle="info")
        frm.pack(fill=X, pady=6)
        ttk.Label(frm, text="Table Number").pack(anchor=W, padx=8, pady=(6,0))
        self._o_table = ttk.Entry(frm, bootstyle="info")
        self._o_table.pack(fill=X, padx=8, pady=3)
        ttk.Button(frm, text="Create Order for Table", bootstyle="info", command=self._create_order).pack(fill=X, padx=8, pady=6)

        ttk.Separator(left).pack(fill=X, pady=4)

        frm2 = ttk.LabelFrame(left, text="2. Add Item to Order", bootstyle="warning")
        frm2.pack(fill=X, pady=4)

        ttk.Label(frm2, text="Order ID").pack(anchor=W, padx=8, pady=(6,0))
        self._o_oid = ttk.Entry(frm2, bootstyle="warning")
        self._o_oid.pack(fill=X, padx=8, pady=3)

        ttk.Label(frm2, text="Menu Item").pack(anchor=W, padx=8)
        self._o_item_var = tk.StringVar()
        self._o_item_cb  = ttk.Combobox(frm2, textvariable=self._o_item_var, bootstyle="warning", state="readonly")
        self._o_item_cb.pack(fill=X, padx=8, pady=3)

        ttk.Label(frm2, text="Quantity").pack(anchor=W, padx=8)
        self._o_qty = ttk.Spinbox(frm2, from_=1, to=99, bootstyle="warning")
        self._o_qty.set(1)
        self._o_qty.pack(fill=X, padx=8, pady=3)

        ttk.Button(frm2, text="Add Item", bootstyle="warning", command=self._add_item_to_order).pack(fill=X, padx=8, pady=6)
        ttk.Button(left, text="Print Bill for Selected Order", bootstyle="success", command=self._print_bill).pack(fill=X, padx=8, pady=8)

        right = ttk.Frame(pane)
        pane.add(right, weight=3)

        hdr = ttk.Frame(right)
        hdr.pack(fill=X, pady=4)
        ttk.Label(hdr, text="orders  table", font=("Helvetica", 12, "bold")).pack(side=LEFT, padx=6)
        ttk.Button(hdr, text="Refresh", bootstyle="secondary-outline", command=self._refresh_orders).pack(side=RIGHT, padx=6)

        ocols = [{"text":"order_id","stretch":False}, {"text":"table_number"}, {"text":"order_time"}, {"text":"total_amount"}]
        self._ord_tv = Tableview(right, coldata=ocols, rowdata=[], paginate=True, pagesize=8, bootstyle="info", stripecolor=("#1e2a38",""))
        self._ord_tv.pack(fill=BOTH, expand=YES, padx=6)
        self._ord_tv.view.bind("<<TreeviewSelect>>", self._load_order_items)

        ttk.Label(right, text="order_items  for selected order", font=("Helvetica", 10, "bold")).pack(anchor=W, padx=8, pady=(8,2))

        icols = [{"text":"order_item_id","stretch":False}, {"text":"item_name"}, {"text":"quantity"}, {"text":"unit_price"}, {"text":"subtotal"}]
        self._ord_items_tv = Tableview(right, coldata=icols, rowdata=[], pagesize=5, paginate=False, bootstyle="warning", stripecolor=("#1e2a38",""))
        self._ord_items_tv.pack(fill=X, padx=6, pady=4)

    def _refresh_orders(self):
        items = self.q("SELECT item_id, name, price, stock_level FROM menu_items ORDER BY name", fetch=True) or []
        self._menu_map = {}
        cb_vals = []
        for r in items:
            label = f"{r[1]}  |  Rs.{r[2]:.2f}  |  Stock:{r[3]}"
            self._menu_map[label] = (r[0], r[2])
            cb_vals.append(label)
        self._o_item_cb["values"] = cb_vals

        rows = self.q("SELECT order_id, table_number, order_time, total_amount FROM orders ORDER BY order_id DESC", fetch=True) or []
        self._ord_tv.delete_rows()
        for r in rows:
            self._ord_tv.insert_row("end", [r[0], r[1], str(r[2])[:16], f"Rs.{r[3]:.2f}"])
        self._ord_tv.load_table_data()

    def _create_order(self):
        t = self._o_table.get().strip()
        if not t.isdigit():
            messagebox.showwarning("Table Number", "Enter a valid integer table number."); return
        try:
            rows = self.q("INSERT INTO orders (table_number) VALUES (%s) RETURNING order_id", (int(t),), fetch=True)
            oid = rows[0][0] if rows else "?"
            messagebox.showinfo("Order Created", f"Order #{oid} created for Table {t}.")
            self._o_oid.delete(0, END)
            self._o_oid.insert(0, str(oid))
            self._refresh_orders()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _add_item_to_order(self):
        oid_str = self._o_oid.get().strip()
        sel     = self._o_item_var.get()
        qty     = int(self._o_qty.get())

        if not oid_str.isdigit() or not sel or sel not in self._menu_map:
            messagebox.showwarning("Input Error", "Check Order ID and Menu Item."); return

        oid = int(oid_str)
        iid, _ = self._menu_map[sel]

        try:
            DB.call("add_order_item", (oid, iid, qty))
            messagebox.showinfo("Added", f"Item added to Order #{oid}.")
            self._refresh_orders()
            self._refresh_menu()
            self._refresh_dashboard()
        except Exception as e:
            messagebox.showerror("DB Error", str(e))

    def _load_order_items(self, _=None):
        sel = self._ord_tv.get_rows(selected=True)
        if not sel: return
        oid = sel[0].values[0]
        rows = self.q("""
            SELECT oi.order_item_id, m.name, oi.quantity, m.price, (oi.quantity * m.price)
            FROM order_items oi JOIN menu_items m ON oi.item_id = m.item_id
            WHERE oi.order_id = %s ORDER BY oi.order_item_id""", (oid,), fetch=True) or []
        self._ord_items_tv.delete_rows()
        for r in rows:
            self._ord_items_tv.insert_row("end", [r[0], r[1], r[2], f"Rs.{r[3]:.2f}", f"Rs.{r[4]:.2f}"])
        self._ord_items_tv.load_table_data()

    def _print_bill(self):
        sel = self._ord_tv.get_rows(selected=True)
        if not sel:
            messagebox.showwarning("Select", "Select an order row first."); return
        oid   = sel[0].values[0]
        order = self.q("SELECT table_number, order_time, total_amount FROM orders WHERE order_id=%s", (oid,), fetch=True)
        items = self.q("""
            SELECT m.name, oi.quantity, m.price, (oi.quantity * m.price)
            FROM order_items oi JOIN menu_items m ON oi.item_id=m.item_id
            WHERE oi.order_id=%s""", (oid,), fetch=True) or []
        if not order: return
        o = order[0]
        lines = [
            "=" * 40, "        RESTROCORE RESTAURANT", "=" * 40,
            f"  Order #  : {oid}", f"  Table    : {o[0]}", f"  Time     : {str(o[1])[:16]}",
            "-" * 40, f"  {'Item':<22} {'Qty':>3}  {'Total':>8}", "-" * 40,
        ]
        for name, qty, price, sub in items:
            lines.append(f"  {name:<22} {qty:>3}  Rs.{sub:>6.2f}")
        lines += [
            "-" * 40, f"  {'TOTAL':>30}  Rs.{o[2]:>6.2f}", "=" * 40,
            "     Thank you for dining with us!", "=" * 40,
        ]
        win = tk.Toplevel(self)
        win.title(f"Bill - Order #{oid}")
        win.geometry("430x440")
        txt = tk.Text(win, font=("Courier", 10), bg="#0d1117", fg="#e6edf3", bd=0)
        txt.pack(fill=BOTH, expand=YES, padx=10, pady=10)
        txt.insert("1.0", "\n".join(lines))
        txt.config(state="disabled")

    # ═══════════════════════════════════════════════════════
    #  MENU & STOCK
    # ═══════════════════════════════════════════════════════
    def _build_menu(self):
        pane = ttk.PanedWindow(self._t_menu, orient=HORIZONTAL)
        pane.pack(fill=BOTH, expand=YES, padx=10, pady=10)
        left = ttk.Frame(pane, width=280)
        pane.add(left, weight=1)

        frm = ttk.LabelFrame(left, text="Add Menu Item", bootstyle="danger")
        frm.pack(fill=X, pady=6)
        ttk.Label(frm, text="Item Name").pack(anchor=W, padx=8, pady=(6,0))
        self._m_name = ttk.Entry(frm, bootstyle="danger")
        self._m_name.pack(fill=X, padx=8, pady=2)

        ttk.Label(frm, text="Price (Rs.)").pack(anchor=W, padx=8)
        self._m_price = ttk.Entry(frm, bootstyle="danger")
        self._m_price.pack(fill=X, padx=8, pady=2)

        ttk.Label(frm, text="Stock Level").pack(anchor=W, padx=8)
        self._m_stock = ttk.Spinbox(frm, from_=0, to=9999, bootstyle="danger")
        self._m_stock.set(0)
        self._m_stock.pack(fill=X, padx=8, pady=2)

        ttk.Label(frm, text="Supplier").pack(anchor=W, padx=8)
        self._m_sup_var = tk.StringVar()
        self._m_sup_cb  = ttk.Combobox(frm, textvariable=self._m_sup_var, bootstyle="danger", state="readonly")
        self._m_sup_cb.pack(fill=X, padx=8, pady=2)

        ttk.Label(frm, text="Image Path (optional)").pack(anchor=W, padx=8)
        self._m_img = ttk.Entry(frm, bootstyle="secondary")
        self._m_img.pack(fill=X, padx=8, pady=2)

        ttk.Button(frm, text="Add Item", bootstyle="danger", command=self._add_menu_item).pack(fill=X, padx=8, pady=6)

        efrm = ttk.LabelFrame(left, text="Update Stock (selected row)", bootstyle="warning")
        efrm.pack(fill=X, pady=8)
        ttk.Label(efrm, text="New Stock Level").pack(anchor=W, padx=8, pady=(6,0))
        self._m_new_stock = ttk.Spinbox(efrm, from_=0, to=9999, bootstyle="warning")
        self._m_new_stock.set(0)
        self._m_new_stock.pack(fill=X, padx=8, pady=3)
        ttk.Button(efrm, text="Update Stock", bootstyle="warning", command=self._update_stock).pack(fill=X, padx=8, pady=5)

        right = ttk.Frame(pane)
        pane.add(right, weight=3)

        hdr = ttk.Frame(right)
        hdr.pack(fill=X, pady=4)
        ttk.Label(hdr, text="menu_items  table", font=("Helvetica", 12, "bold")).pack(side=LEFT, padx=6)
        ttk.Button(hdr, text="Refresh", bootstyle="secondary-outline", command=self._refresh_menu).pack(side=RIGHT, padx=6)

        self._low_only = tk.BooleanVar(value=False)
        ttk.Checkbutton(hdr, text="Low Stock Only (<10)", variable=self._low_only, bootstyle="danger-round-toggle",
                        command=self._refresh_menu).pack(side=RIGHT, padx=6)

        mcols = [{"text":"item_id","stretch":False}, {"text":"name"}, {"text":"price"}, {"text":"stock_level"}, {"text":"supplier"}, {"text":"image_path"}]
        self._menu_tv = Tableview(right, coldata=mcols, rowdata=[], paginate=True, pagesize=14, bootstyle="danger", stripecolor=("#1e2a38",""))
        self._menu_tv.pack(fill=BOTH, expand=YES, padx=6, pady=4)

    def _refresh_menu(self, _=None):
        sups = self.q("SELECT supplier_id, name FROM suppliers ORDER BY name", fetch=True) or []
        self._sup_map_menu = {f"{r[1]} (ID:{r[0]})": r[0] for r in sups}
        self._m_sup_cb["values"] = list(self._sup_map_menu.keys())

        where = "WHERE m.stock_level < 10" if self._low_only.get() else ""
        rows = self.q(f"""
            SELECT m.item_id, m.name, m.price, m.stock_level, COALESCE(s.name, '--'), COALESCE(m.image_path, '--')
            FROM menu_items m LEFT JOIN suppliers s ON m.supplier_id = s.supplier_id
            {where} ORDER BY m.name""", fetch=True) or []

        self._menu_tv.delete_rows()
        for r in rows:
            self._menu_tv.insert_row("end", [r[0], r[1], f"Rs.{r[2]:.2f}", r[3], r[4], r[5]])
        self._menu_tv.load_table_data()

    def _add_menu_item(self):
        name  = self._m_name.get().strip()
        price = self._m_price.get().strip()
        stock = int(self._m_stock.get())
        sup   = self._m_sup_var.get()
        img   = self._m_img.get().strip() or None

        if not name or not price:
            messagebox.showwarning("Required", "Name and Price are required."); return
        try:
            price = float(price)
        except ValueError:
            messagebox.showwarning("Price", "Price must be a number."); return

        sid = self._sup_map_menu.get(sup) if sup else None
        self.q("INSERT INTO menu_items (name, price, stock_level, supplier_id, image_path) VALUES (%s,%s,%s,%s,%s)", (name, price, stock, sid, img))
        messagebox.showinfo("Added", f"'{name}' added to menu.")
        self._m_name.delete(0, END); self._m_price.delete(0, END); self._m_img.delete(0, END)
        self._refresh_menu()

    def _update_stock(self):
        sel = self._menu_tv.get_rows(selected=True)
        if not sel:
            messagebox.showwarning("Select", "Select a menu item row."); return
        iid   = sel[0].values[0]
        stock = int(self._m_new_stock.get())
        self.q("UPDATE menu_items SET stock_level=%s WHERE item_id=%s", (stock, iid))
        self._refresh_menu()

    # ═══════════════════════════════════════════════════════
    #  EMPLOYEES
    # ═══════════════════════════════════════════════════════
    def _build_employees(self):
        pane = ttk.PanedWindow(self._t_emp, orient=HORIZONTAL)
        pane.pack(fill=BOTH, expand=YES, padx=10, pady=10)
        left = ttk.Frame(pane, width=290)
        pane.add(left, weight=1)

        frm = ttk.LabelFrame(left, text="Add Employee", bootstyle="warning")
        frm.pack(fill=X, pady=6)

        self._e_fields = {}
        for label, show in [("Name",""),("Role",""),("Username",""),("Password","*")]:
            ttk.Label(frm, text=label).pack(anchor=W, padx=8, pady=(4,0))
            e = ttk.Entry(frm, show=show, bootstyle="warning")
            e.pack(fill=X, padx=8, pady=2)
            self._e_fields[label] = e

        ttk.Button(frm, text="Add Employee", bootstyle="warning", command=self._add_employee).pack(fill=X, padx=8, pady=6)

        efrm = ttk.LabelFrame(left, text="Edit Selected", bootstyle="secondary")
        efrm.pack(fill=X, pady=6)
        ttk.Label(efrm, text="New Role").pack(anchor=W, padx=8, pady=(6,0))
        self._e_new_role = ttk.Entry(efrm, bootstyle="secondary")
        self._e_new_role.pack(fill=X, padx=8, pady=3)
        ttk.Button(efrm, text="Update Role", bootstyle="secondary", command=self._update_role).pack(fill=X, padx=8, pady=3)
        ttk.Button(efrm, text="Delete Employee", bootstyle="danger-outline", command=self._delete_employee).pack(fill=X, padx=8, pady=3)

        right = ttk.Frame(pane)
        pane.add(right, weight=3)

        hdr = ttk.Frame(right)
        hdr.pack(fill=X, pady=4)
        ttk.Label(hdr, text="employees  table", font=("Helvetica", 12, "bold")).pack(side=LEFT, padx=6)
        ttk.Button(hdr, text="Refresh", bootstyle="secondary-outline", command=self._refresh_employees).pack(side=RIGHT, padx=6)

        ecols = [{"text":"employee_id","stretch":False}, {"text":"name"}, {"text":"role"}, {"text":"username"}, {"text":"password"}]
        self._emp_tv = Tableview(right, coldata=ecols, rowdata=[], paginate=True, pagesize=14, bootstyle="warning", stripecolor=("#1e2a38",""))
        self._emp_tv.pack(fill=BOTH, expand=YES, padx=6, pady=4)

    def _refresh_employees(self, _=None):
        rows = self.q("SELECT employee_id, name, role, username, password FROM employees ORDER BY employee_id ASC", fetch=True) or []
        self._emp_tv.delete_rows()
        for r in rows:
            self._emp_tv.insert_row("end", [r[0], r[1], r[2], r[3] or "--", "********" if r[4] else "--"])
        self._emp_tv.load_table_data()

    def _add_employee(self):
        name = self._e_fields["Name"].get().strip()
        role = self._e_fields["Role"].get().strip()
        un   = self._e_fields["Username"].get().strip() or None
        pw   = self._e_fields["Password"].get().strip() or None
        if not name or not role:
            messagebox.showwarning("Required", "Name and Role are required."); return
        try:
            self.q("INSERT INTO employees (name, role, username, password) VALUES (%s,%s,%s,%s)", (name, role, un, pw))
            messagebox.showinfo("Added", f"Employee '{name}' added.")
            for e in self._e_fields.values(): e.delete(0, END)
            self._refresh_employees()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _update_role(self):
        sel = self._emp_tv.get_rows(selected=True)
        if not sel: return
        eid  = sel[0].values[0]
        role = self._e_new_role.get().strip()
        if role:
            self.q("UPDATE employees SET role=%s WHERE employee_id=%s", (role, eid))
            self._refresh_employees()

    def _delete_employee(self):
        sel = self._emp_tv.get_rows(selected=True)
        if not sel: return
        eid = sel[0].values[0]
        if messagebox.askyesno("Confirm", f"Delete employee ID {eid}?"):
            self.q("DELETE FROM employees WHERE employee_id=%s", (eid,))
            self._refresh_employees()

    # ═══════════════════════════════════════════════════════
    #  SUPPLIERS (COMPLETED)
    # ═══════════════════════════════════════════════════════
    def _build_suppliers(self):
        pane = ttk.PanedWindow(self._t_supp, orient=HORIZONTAL)
        pane.pack(fill=BOTH, expand=YES, padx=10, pady=10)

        left = ttk.Frame(pane, width=280)
        pane.add(left, weight=1)

        frm = ttk.LabelFrame(left, text="Add Supplier", bootstyle="success")
        frm.pack(fill=X, pady=6)

        self._s_fields = {}
        for label in ["Supplier Name", "Contact Email", "Phone Number"]:
            ttk.Label(frm, text=label).pack(anchor=W, padx=8, pady=(4,0))
            e = ttk.Entry(frm, bootstyle="success")
            e.pack(fill=X, padx=8, pady=2)
            self._s_fields[label] = e

        # This is where your code originally got cut off!
        ttk.Button(frm, text="Add Supplier", bootstyle="success",
                   command=self._add_supplier).pack(fill=X, padx=8, pady=6)

        right = ttk.Frame(pane)
        pane.add(right, weight=3)

        hdr = ttk.Frame(right)
        hdr.pack(fill=X, pady=4)
        ttk.Label(hdr, text="suppliers  table", font=("Helvetica", 12, "bold")).pack(side=LEFT, padx=6)
        ttk.Button(hdr, text="Refresh", bootstyle="secondary-outline", command=self._refresh_suppliers).pack(side=RIGHT, padx=6)

        scols = [{"text":"supplier_id","stretch":False}, {"text":"name"}, {"text":"contact_email"}, {"text":"phone_number"}]
        self._supp_tv = Tableview(right, coldata=scols, rowdata=[], paginate=True, pagesize=14, bootstyle="success", stripecolor=("#1e2a38",""))
        self._supp_tv.pack(fill=BOTH, expand=YES, padx=6, pady=4)

    def _refresh_suppliers(self):
        rows = self.q("SELECT supplier_id, name, contact_email, phone_number FROM suppliers ORDER BY supplier_id", fetch=True) or []
        self._supp_tv.delete_rows()
        for r in rows:
            self._supp_tv.insert_row("end", r)
        self._supp_tv.load_table_data()

    def _add_supplier(self):
        name = self._s_fields["Supplier Name"].get().strip()
        email = self._s_fields["Contact Email"].get().strip()
        phone = self._s_fields["Phone Number"].get().strip()

        if not name:
            messagebox.showwarning("Required", "Supplier Name is required."); return
        try:
            self.q("INSERT INTO suppliers (name, contact_email, phone_number) VALUES (%s, %s, %s)", (name, email, phone))
            messagebox.showinfo("Success", f"Supplier '{name}' added.")
            for e in self._s_fields.values(): e.delete(0, 'end')
            self._refresh_suppliers()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ═══════════════════════════════════════════════════════
    #  SUPPLY ORDERS (COMPLETED)
    # ═══════════════════════════════════════════════════════
    def _build_supply_orders(self):
        pane = ttk.PanedWindow(self._t_stock, orient=HORIZONTAL)
        pane.pack(fill=BOTH, expand=YES, padx=10, pady=10)

        left = ttk.Frame(pane, width=310)
        pane.add(left, weight=1)

        frm = ttk.LabelFrame(left, text="1. Create Supply Order", bootstyle="primary")
        frm.pack(fill=X, pady=6)
        ttk.Label(frm, text="Supplier").pack(anchor=W, padx=8, pady=(6,0))
        self._so_sup_var = tk.StringVar()
        self._so_sup_cb  = ttk.Combobox(frm, textvariable=self._so_sup_var, bootstyle="primary", state="readonly")
        self._so_sup_cb.pack(fill=X, padx=8, pady=3)
        ttk.Button(frm, text="Create Supply Order", bootstyle="primary", command=self._create_supply_order).pack(fill=X, padx=8, pady=6)

        ttk.Separator(left).pack(fill=X, pady=4)

        frm2 = ttk.LabelFrame(left, text="2. Receive Items", bootstyle="info")
        frm2.pack(fill=X, pady=4)
        ttk.Label(frm2, text="Supply Order ID").pack(anchor=W, padx=8, pady=(6,0))
        self._so_oid = ttk.Entry(frm2, bootstyle="info")
        self._so_oid.pack(fill=X, padx=8, pady=3)

        ttk.Label(frm2, text="Menu Item to Restock").pack(anchor=W, padx=8)
        self._so_item_var = tk.StringVar()
        self._so_item_cb  = ttk.Combobox(frm2, textvariable=self._so_item_var, bootstyle="info", state="readonly")
        self._so_item_cb.pack(fill=X, padx=8, pady=3)

        ttk.Label(frm2, text="Quantity Received").pack(anchor=W, padx=8)
        self._so_qty = ttk.Spinbox(frm2, from_=1, to=999, bootstyle="info")
        self._so_qty.set(10)
        self._so_qty.pack(fill=X, padx=8, pady=3)
        ttk.Button(frm2, text="Add & Update Inventory", bootstyle="info", command=self._add_supply_item).pack(fill=X, padx=8, pady=6)

        right = ttk.Frame(pane)
        pane.add(right, weight=3)

        hdr = ttk.Frame(right)
        hdr.pack(fill=X, pady=4)
        ttk.Label(hdr, text="supply_orders & items", font=("Helvetica", 12, "bold")).pack(side=LEFT, padx=6)
        ttk.Button(hdr, text="Refresh", bootstyle="secondary-outline", command=self._refresh_supply_orders).pack(side=RIGHT, padx=6)

        ocols = [{"text":"supply_order_id","stretch":False}, {"text":"supplier_id"}, {"text":"order_date"}]
        self._so_tv = Tableview(right, coldata=ocols, rowdata=[], paginate=True, pagesize=10, bootstyle="primary", stripecolor=("#1e2a38",""))
        self._so_tv.pack(fill=BOTH, expand=YES, padx=6, pady=4)

    def _refresh_supply_orders(self):
        sups = self.q("SELECT supplier_id, name FROM suppliers ORDER BY name", fetch=True) or []
        self._sup_map_stock = {f"{r[1]} (ID:{r[0]})": r[0] for r in sups}
        self._so_sup_cb["values"] = list(self._sup_map_stock.keys())

        items = self.q("SELECT item_id, name FROM menu_items ORDER BY name", fetch=True) or []
        self._item_map_stock = {r[1]: r[0] for r in items}
        self._so_item_cb["values"] = list(self._item_map_stock.keys())

        rows = self.q("SELECT supply_order_id, supplier_id, order_date FROM supply_orders ORDER BY supply_order_id DESC", fetch=True) or []
        self._so_tv.delete_rows()
        for r in rows:
            self._so_tv.insert_row("end", [r[0], r[1] or "--", str(r[2])[:16]])
        self._so_tv.load_table_data()

    def _create_supply_order(self):
        sup = self._so_sup_var.get()
        if not sup:
            messagebox.showwarning("Select", "Select a supplier first."); return
        sid = self._sup_map_stock[sup]
        try:
            rows = self.q("INSERT INTO supply_orders (supplier_id) VALUES (%s) RETURNING supply_order_id", (sid,), fetch=True)
            oid = rows[0][0]
            messagebox.showinfo("Created", f"Supply Order #{oid} created.")
            self._so_oid.delete(0, END)
            self._so_oid.insert(0, str(oid))
            self._refresh_supply_orders()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _add_supply_item(self):
        so_id = self._so_oid.get().strip()
        item_sel = self._so_item_var.get()
        qty = int(self._so_qty.get())

        if not so_id.isdigit() or not item_sel:
            messagebox.showwarning("Input Error", "Check Supply Order ID and Item."); return

        iid = self._item_map_stock[item_sel]
        try:
            self.q("INSERT INTO supply_order_items (supply_order_id, item_id, quantity) VALUES (%s, %s, %s)", (int(so_id), iid, qty))
            messagebox.showinfo("Restocked", "Inventory updated automatically via trg_restock_inventory.")
            self._refresh_supply_orders()
            self._refresh_menu() # Refresh menu to reflect new stock levels immediately
        except Exception as e:
            messagebox.showerror("Trigger Error", str(e))

# Starts the App
if __name__ == "__main__":
    app = RestroCoreApp()
    app.mainloop()