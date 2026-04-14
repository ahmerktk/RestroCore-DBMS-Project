# RestroCore-DBMS-Project
# 🍽️ RestroCore

RestroCore is a comprehensive Restaurant Management System designed to streamline order processing, inventory tracking, and supply chain management. This project serves as a practical implementation of advanced Relational Database Management System (RDBMS) concepts, featuring automated business logic, triggers, and relational data structures.

## 🚀 Key Features

* **Automated Inventory Management:** Triggers automatically update stock levels upon every sale or supply restock.
* **Intelligent Reporting:** Complex SQL joins provide real-time insights into sales performance and supplier inventory.
* **Procedural Business Logic:** Custom functions handle complex order calculations and stock validation.
* **Robust Schema:** Normalized database design ensuring data integrity across Employees, Menu, Suppliers, and Order tables.

## 🛠️ Technical Stack

* **Database:** PostgreSQL
* **Backend/Logic:** Python
* **GUI:** Flask
* **Tools:** pgAdmin 4, Git

## 📂 Project Structure

```text
/RestroCore
│
├── /database
│   ├── schema.sql           # Database initialization and DDL
│   └── functions.sql        # Triggers and stored procedures
├── /src
│   ├── main.py              # Application entry point
│   └── db_manager.py        # Database connectivity and logic
├── /docs
│   └── er_diagram.png       # Entity-Relationship diagram
└── requirements.txt         # Dependencies
