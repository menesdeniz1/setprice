import sqlite3

def migrate():
    conn = sqlite3.connect('data/setprice.sqlite')
    cursor = conn.cursor()
    
    columns_to_add = [
        ("ticker", "VARCHAR"),
        ("value_score", "FLOAT"),
        ("satisfaction_score", "FLOAT"),
        ("decision_signal", "VARCHAR DEFAULT 'WAIT'"),
        ("benchmark_price", "FLOAT")
    ]
    
    for col_name, col_type in columns_to_add:
        try:
            cursor.execute(f"ALTER TABLE library_products ADD COLUMN {col_name} {col_type}")
            print(f"Added column {col_name}")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                print(f"Column {col_name} already exists")
            else:
                print(f"Error adding {col_name}: {e}")
                
    # Create unique index for ticker
    try:
        cursor.execute("CREATE UNIQUE INDEX ix_library_products_ticker ON library_products (ticker)")
        print("Created index for ticker")
    except sqlite3.OperationalError as e:
        print(f"Index error: {e}")
        
    conn.commit()
    conn.close()

if __name__ == '__main__':
    migrate()
