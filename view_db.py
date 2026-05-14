import sqlite3
import os

DATABASE = "shopDB.sqlite"

def connect_db():
    return sqlite3.connect(DATABASE)

def print_table(title, headers, rows):
    print(f"\n--- {title} ---")
    if not rows:
        print("No data.")
        return

    # Простой форматированный вывод
    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, val in enumerate(row):
            val_str = str(val)
            if len(val_str) > col_widths[i]:
                col_widths[i] = len(val_str)
    
    # Header
    header_str = " | ".join(f"{h:<{w}}" for h, w in zip(headers, col_widths))
    print("-" * len(header_str))
    print(header_str)
    print("-" * len(header_str))
    
    # Rows
    for row in rows:
        row_str = " | ".join(f"{str(v):<{w}}" for v, w in zip(row, col_widths))
        print(row_str)

def view_data():
    if not os.path.exists(DATABASE):
        print(f"Database {DATABASE} not found!")
        return

    conn = connect_db()
    cur = conn.cursor()

    while True:
        print("\n=== SAINT'S SMS SERVICE DATABASE VIEWER ===")
        print("1. Users (Last 10)")
        print("2. Sales (Last 10)")
        print("3. Topups (Last 10)")
        print("4. Payment Data (Pending/Failed)")
        print("5. Custom SQL Query")
        print("0. Exit")
        
        choice = input("\nSelect option: ")
        
        try:
            if choice == '1':
                rows = cur.execute("SELECT user_id, username, firstName, balance, regDate FROM UserList ORDER BY rowid DESC LIMIT 10").fetchall()
                print_table("Users", ["ID", "Username", "Name", "Balance ($)", "Date"], rows)
                
            elif choice == '2':
                rows = cur.execute("SELECT id, user_id, item_name, amount, date FROM Sales ORDER BY id DESC LIMIT 10").fetchall()
                print_table("Sales", ["ID", "User ID", "Item", "Cost ($)", "Date"], rows)
                
            elif choice == '3':
                rows = cur.execute("SELECT user_id, amount_usd, amount_rub, date FROM Topups ORDER BY id DESC LIMIT 10").fetchall()
                print_table("Topups", ["User ID", "Amount ($)", "Amount (RUB - old)", "Date"], rows)
                
            elif choice == '4':
                rows = cur.execute("SELECT user_id, invoice_id, amount, status, date FROM PaymentData ORDER BY id DESC LIMIT 10").fetchall()
                print_table("Payment Attempts", ["User ID", "Invoice", "Amount", "Status", "Date"], rows)
                
            elif choice == '5':
                query = input("Enter SQL: ")
                try:
                    rows = cur.execute(query).fetchall()
                    # Пытаемся получить заголовки
                    headers = [description[0] for description in cur.description]
                    print_table("Custom Query", headers, rows)
                except Exception as e:
                    print(f"Error: {e}")
                    
            elif choice == '0':
                break
        except Exception as e:
            print(f"Error executing query: {e}")

    conn.close()

if __name__ == "__main__":
    view_data()