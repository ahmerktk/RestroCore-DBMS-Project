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
        for w in self.root.winfo_children():
            w.destroy()

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

        right_panel = tb.Frame(main, width=300)
        right_panel.pack(side=RIGHT, fill=Y, padx=(10, 0))
        right_panel.pack_propagate(False)

        tb.Label(right_panel, text="🛒  Cart", font=("Helvetica", 12, "bold")).pack(anchor=W, pady=(0, 4))

        cart_cols = ('name', 'qty', 'sub')
        self.tree_cart = tb.Treeview(right_panel, columns=cart_cols, show='headings', bootstyle=SUCCESS, height=16)
        self.tree_cart.heading('name', text='Item')
        self.tree_cart.heading('qty', text='Qty')
        self.tree_cart.heading('sub', text='Subtotal')
        self.tree_cart.column('name', width=140)
        self.tree_cart.column('qty', width=50, anchor=CENTER)
        self.tree_cart.column('sub', width=90, anchor=E)
        self.tree_cart.pack(fill=BOTH, expand=True)

        tb.Button(right_panel, text="✕ Remove Selected", bootstyle=(DANGER, OUTLINE), command=self.remove_cart_item).pack(fill=X, pady=(6, 2))

        self.lbl_total = tb.Label(right_panel, text="Total: $0.00", font=("Helvetica", 12, "bold"), bootstyle=WARNING)
        self.lbl_total.pack(anchor=E, pady=4)

        tb.Button(right_panel, text="✔  Place Order", bootstyle=SUCCESS, command=self.place_order_from_cart).pack(fill=X, pady=(4, 0))

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
            self.cursor.execute(
                "INSERT INTO orders (table_number, employee_id) VALUES (%s, %s) RETURNING order_id",
                (table, self.current_user['id']))
            order_id = self.cursor.fetchone()[0]
            for row in self.order_cart:
                self.cursor.execute(
                    "INSERT INTO order_items (order_id, item_id, quantity) VALUES (%s, %s, %s)",
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
        import tkinter as tk

        # ── Top search bar ──
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

        # ── Receipt card with scrollable canvas ──
        card_outer = tb.Frame(self.tab_billing, bootstyle=SECONDARY, padding=2)
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

        # --- ADD TRY/EXCEPT WITH ROLLBACK HERE ---
        try:
            self.cursor.execute(
                "SELECT order_id, total_amount, created_at "
                "FROM orders WHERE table_number=%s AND status='Pending'",
                (table,)
            )
            order = self.cursor.fetchone()
        except psycopg2.Error as e:
            self.conn.rollback()  # <--- CRITICAL: Clears the aborted transaction state
            Messagebox.show_error(f"Database error while generating bill:\n{e}", "Database Error")
            return
        # -----------------------------------------

        self._clear_receipt()
        
        # ... (rest of your generate_bill code) ...

        # ── Color palette ──
        BG   = "#1e1e2e"   # dark background
        CARD = "#252538"   # slightly lighter card rows
        ACC  = "#7c6af7"   # violet accent
        GRN  = "#50fa7b"   # green for prices
        WHT  = "#cdd6f4"   # soft white text
        DIM  = "#6272a4"   # muted labels
        RED  = "#ff5555"   # error red
        ALT  = "#23233a"   # alternating row bg

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

        # ── Restaurant header ──
        lbl(outer, "R E S T R O C O R E", fg=ACC,
            font=("Courier", 20, "bold")).pack()
        lbl(outer, "━━━  Fine Dining & Beyond  ━━━",
            fg=DIM, font=("Courier", 10)).pack(pady=(2, 0))
        lbl(outer, " ", bg=BG).pack()

        # ── Order meta ──
        meta = tk.Frame(outer, bg=BG)
        meta.pack(fill=X)
        lbl(meta, f"Order  #  {order_id}", fg=WHT,
            font=("Courier", 10, "bold")).pack(side=LEFT)
        lbl(meta, date_str, fg=DIM, font=("Courier", 9)).pack(side=RIGHT)

        lbl(outer, f"Table :  {table}",
            fg=WHT, font=("Courier", 10)).pack(anchor="w", pady=(4, 0))
        lbl(outer, f"Server :  {self.current_user['name']}",
            fg=WHT, font=("Courier", 10)).pack(anchor="w")

        # ── Accent divider ──
        tk.Frame(outer, bg=ACC, height=2).pack(fill=X, pady=12)

        # ── Column header row ──
        hdr = tk.Frame(outer, bg=CARD, pady=7, padx=8)
        hdr.pack(fill=X)
        tk.Label(hdr, text="ITEM", bg=CARD, fg=ACC,
                 font=("Courier", 10, "bold"), width=28, anchor="w").grid(row=0, column=0, padx=(4,0))
        tk.Label(hdr, text="QTY", bg=CARD, fg=ACC,
                 font=("Courier", 10, "bold"), width=6, anchor="center").grid(row=0, column=1)
        tk.Label(hdr, text="UNIT", bg=CARD, fg=ACC,
                 font=("Courier", 10, "bold"), width=10, anchor="e").grid(row=0, column=2)
        tk.Label(hdr, text="SUBTOTAL", bg=CARD, fg=ACC,
                 font=("Courier", 10, "bold"), width=12, anchor="e").grid(row=0, column=3, padx=(0,4))

        # ── Fetch line items ──
        self.cursor.execute("""
            SELECT mi.name, oi.quantity, mi.price
            FROM order_items oi
            JOIN menu_items mi ON oi.item_id = mi.item_id
            WHERE oi.order_id = %s
            ORDER BY mi.name
        """, (order_id,))
        items = self.cursor.fetchall()

        running = 0.0
        for i, (name, qty, unit_price) in enumerate(items):
            unit_price = float(unit_price)
            sub = unit_price * qty
            running += sub
            row_bg = BG if i % 2 == 0 else ALT
            row_f = tk.Frame(outer, bg=row_bg, pady=5, padx=8)
            row_f.pack(fill=X)
            tk.Label(row_f, text=name[:30], bg=row_bg, fg=WHT,
                     font=("Courier", 10), width=28, anchor="w").grid(row=0, column=0, padx=(4,0))
            tk.Label(row_f, text=f"× {qty}", bg=row_bg, fg=DIM,
                     font=("Courier", 10), width=6, anchor="center").grid(row=0, column=1)
            tk.Label(row_f, text=f"${unit_price:.2f}", bg=row_bg, fg=DIM,
                     font=("Courier", 10), width=10, anchor="e").grid(row=0, column=2)
            tk.Label(row_f, text=f"${sub:.2f}", bg=row_bg, fg=GRN,
                     font=("Courier", 10, "bold"), width=12, anchor="e").grid(row=0, column=3, padx=(0,4))

        # ── Muted divider ──
        tk.Frame(outer, bg=DIM, height=1).pack(fill=X, pady=12)

        # ── Summary block (subtotal / tax / total) ──
        TAX_RATE = 0.08
        tax_amt  = running * TAX_RATE
        grand    = running + tax_amt

        summary = tk.Frame(outer, bg=BG)
        summary.pack(anchor="e", padx=8)

        def srow(r, label, value, fg_val=WHT, bold=False):
            f = ("Courier", 10, "bold") if bold else ("Courier", 10)
            tk.Label(summary, text=label, bg=BG, fg=DIM,
                     font=f, anchor="e", width=20).grid(row=r, column=0, sticky="e", pady=2)
            tk.Label(summary, text=value, bg=BG, fg=fg_val,
                     font=f, anchor="e", width=12).grid(row=r, column=1, sticky="e", pady=2)

        srow(0, "Subtotal :", f"${running:.2f}")
        srow(1, f"Tax  ({int(TAX_RATE*100)}%) :", f"${tax_amt:.2f}")

        # ── Grand total highlight bar ──
        total_frame = tk.Frame(outer, bg=ACC, pady=12, padx=20)
        total_frame.pack(fill=X, pady=(10, 0))
        tk.Label(total_frame, text="TOTAL  DUE", bg=ACC, fg="#ffffff",
                 font=("Courier", 14, "bold")).pack(side=LEFT)
        tk.Label(total_frame, text=f"  ${grand:.2f}", bg=ACC, fg="#ffffff",
                 font=("Courier", 18, "bold")).pack(side=RIGHT)

        # ── Footer ──
        lbl(outer, " ", bg=BG).pack()
        tk.Frame(outer, bg=DIM, height=1).pack(fill=X)
        lbl(outer, "Thank you for dining with us!  🍽️",
            fg=DIM, font=("Courier", 10, "italic")).pack(pady=(8, 2))
        lbl(outer, "Please come again  •  RestroCore POS  v1.0",
            fg=DIM, font=("Courier", 8)).pack()
        lbl(outer, " ", bg=BG).pack()

        self.btn_pay.config(state=NORMAL)

    def checkout(self):
        self.cursor.execute(
            "UPDATE orders SET status='Paid' WHERE order_id=%s",
            (self.active_bill_id,))
        self.conn.commit()
        Messagebox.show_info("Payment Complete!  Thank you 🎉", "Success")
        self._show_receipt_placeholder()
        self.btn_pay.config(state=DISABLED)

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
            self.cursor.execute(
                "INSERT INTO employees (name, role, username, password) VALUES (%s,%s,%s,%s)", vals)
            self.conn.commit()
            Messagebox.show_info("Staff Added", "Success")

    # ─────────────────────────── LOGOUT & CLOSING ────────────────────
    def logout(self):
        self.order_cart = []
        self.thumb_refs = {}
        if hasattr(self, '_order_tab_ready'):
            del self._order_tab_ready

        for w in self.root.winfo_children():
            w.destroy()

        self.build_login_screen()

    def on_closing(self):
        if hasattr(self, 'conn'):
            self.conn.close()
        self.root.destroy()


if __name__ == "__main__":
    app_root = tb.Window(themename="cyborg")
    app = RestroCoreApp(app_root)
    
    try:
        # Start the application loop inside the protected block
        app_root.mainloop()
    except KeyboardInterrupt:
        print("\nProgram stopped by user via terminal (Ctrl+C).")
    finally:
        # Emergency cleanup if closed via terminal instead of the 'X' button
        if hasattr(app, 'conn') and app.conn:
            app.conn.close()
            print("Database connection safely closed.")
        try:
            app_root.destroy()
        except tb.TclError:
            pass # Window was already destroyed
