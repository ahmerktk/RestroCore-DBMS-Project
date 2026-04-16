import tkinter as tk
from tkinter import messagebox
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from db_manager import DatabaseManager

class RestroCoreApp(ttk.Window):
    def __init__(self):
        super().__init__(themename="darkly")
        self.title("RestroCore Management System")
        self.geometry("900x600")

        # Tabs
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=BOTH, expand=YES, padx=10, pady=10)

        self.tab_orders = ttk.Frame(self.notebook)
        self.tab_employees = ttk.Frame(self.notebook)
        
        self.notebook.add(self.tab_orders, text="Orders & Billing")
        self.notebook.add(self.tab_employees, text="Manage Employees")

        self.setup_orders_ui()
        self.setup_employees_ui()

    def setup_orders_ui(self):
        # Using pack padding instead of widget-level padding to avoid TclError
        container = ttk.LabelFrame(self.tab_orders, text="Place New Order")
        container.pack(fill=X, padx=15, pady=15)

        ttk.Label(container, text="Table Number:").pack(side=LEFT, padx=5)
        self.table_input = ttk.Entry(container, bootstyle="info")
        self.table_input.pack(side=LEFT, padx=5, pady=5)
        
        ttk.Button(container, text="Place Order", command=self.place_order, bootstyle="success").pack(side=LEFT, padx=5, pady=5)

    def setup_employees_ui(self):
        form = ttk.LabelFrame(self.tab_employees, text="Add New Employee")
        form.pack(fill=X, padx=15, pady=15)
        
        self.emp_name = ttk.Entry(form)
        self.emp_name.pack(fill=X, padx=5, pady=5)
        self.emp_name.insert(0, "Employee Name")
        
        self.emp_role = ttk.Entry(form)
        self.emp_role.pack(fill=X, padx=5, pady=5)
        self.emp_role.insert(0, "Role")

        ttk.Button(form, text="Add Employee", command=self.add_employee, bootstyle="primary").pack(pady=10)

    def place_order(self):
        table_num = self.table_input.get()
        db = DatabaseManager()
        try:
            db.execute_query("INSERT INTO orders (table_number) VALUES (%s)", (table_num,))
            messagebox.showinfo("Success", f"Order initiated for Table {table_num}")
        except Exception as e:
            messagebox.showerror("Error", str(e))
        finally:
            db.release()

    def add_employee(self):
        name = self.emp_name.get()
        role = self.emp_role.get()
        db = DatabaseManager()
        try:
            db.execute_query("INSERT INTO employees (name, role) VALUES (%s, %s)", (name, role))
            messagebox.showinfo("Success", f"Employee {name} added!")
        except Exception as e:
            messagebox.showerror("Error", str(e))
        finally:
            db.release()

if __name__ == "__main__":
    app = RestroCoreApp()
    app.mainloop()