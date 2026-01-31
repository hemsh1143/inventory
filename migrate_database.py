# migrate_database.py - UPDATED VERSION
import os
import sqlite3
from datetime import datetime
from werkzeug.security import generate_password_hash

def create_database_schema():
    """Create the complete database schema with all required tables and columns"""
    
    conn = sqlite3.connect('inventory.db')
    cursor = conn.cursor()
    
    print("Creating database schema...")
    
    # User table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username VARCHAR(80) UNIQUE NOT NULL,
            password VARCHAR(120) NOT NULL,
            role VARCHAR(20) DEFAULT 'user',
            email VARCHAR(120),
            phone VARCHAR(20),
            created_date DATETIME DEFAULT CURRENT_TIMESTAMP,
            is_active BOOLEAN DEFAULT TRUE
        )
    ''')
    
    # Item table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS item (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name VARCHAR(100) NOT NULL,
            sku VARCHAR(50) UNIQUE NOT NULL,
            category VARCHAR(50),
            current_stock FLOAT DEFAULT 0,
            min_stock_level FLOAT DEFAULT 5,
            cost_price FLOAT NOT NULL,
            selling_price FLOAT NOT NULL,
            created_date DATETIME DEFAULT CURRENT_TIMESTAMP,
            tally_synced BOOLEAN DEFAULT FALSE,
            tally_guid VARCHAR(100)
        )
    ''')
    
    # Supplier table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS supplier (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name VARCHAR(100) NOT NULL,
            contact_person VARCHAR(100),
            phone VARCHAR(20),
            email VARCHAR(100),
            address TEXT,
            gst_number VARCHAR(50),
            tally_synced BOOLEAN DEFAULT FALSE,
            tally_guid VARCHAR(100)
        )
    ''')
    
    # Customer table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS customer (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name VARCHAR(100) NOT NULL,
            phone VARCHAR(20),
            email VARCHAR(100),
            address TEXT,
            gst_number VARCHAR(50),
            credit_limit FLOAT DEFAULT 0,
            tally_synced BOOLEAN DEFAULT FALSE,
            tally_guid VARCHAR(100)
        )
    ''')
    
    # Employee table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS employee (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name VARCHAR(100) NOT NULL,
            role VARCHAR(50),
            department VARCHAR(50),
            hourly_rate FLOAT DEFAULT 0,
            phone VARCHAR(20),
            email VARCHAR(100),
            address TEXT,
            join_date DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # PurchaseOrder table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS purchase_order (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            supplier_id INTEGER NOT NULL,
            po_number VARCHAR(100) UNIQUE NOT NULL,
            order_date DATETIME DEFAULT CURRENT_TIMESTAMP,
            total_amount FLOAT DEFAULT 0,
            status VARCHAR(20) DEFAULT 'pending',
            tally_synced BOOLEAN DEFAULT FALSE,
            tally_voucher_no VARCHAR(100),
            FOREIGN KEY (supplier_id) REFERENCES supplier (id)
        )
    ''')
    
    # PurchaseItem table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS purchase_item (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            purchase_order_id INTEGER NOT NULL,
            item_id INTEGER NOT NULL,
            quantity FLOAT NOT NULL,
            unit_cost FLOAT NOT NULL,
            total_cost FLOAT NOT NULL,
            FOREIGN KEY (purchase_order_id) REFERENCES purchase_order (id),
            FOREIGN KEY (item_id) REFERENCES item (id)
        )
    ''')
    
    # SalesOrder table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sales_order (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            employee_id INTEGER NOT NULL,
            invoice_number VARCHAR(100) UNIQUE NOT NULL,
            sale_date DATETIME DEFAULT CURRENT_TIMESTAMP,
            total_amount FLOAT DEFAULT 0,
            gst_amount FLOAT DEFAULT 0,
            discount FLOAT DEFAULT 0,
            status VARCHAR(20) DEFAULT 'pending',
            tally_synced BOOLEAN DEFAULT FALSE,
            tally_voucher_no VARCHAR(100),
            FOREIGN KEY (customer_id) REFERENCES customer (id),
            FOREIGN KEY (employee_id) REFERENCES employee (id)
        )
    ''')
    
    # SaleItem table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sale_item (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sales_order_id INTEGER NOT NULL,
            item_id INTEGER NOT NULL,
            employee_id INTEGER NOT NULL,
            quantity FLOAT NOT NULL,
            unit_price FLOAT NOT NULL,
            total_price FLOAT NOT NULL,
            FOREIGN KEY (sales_order_id) REFERENCES sales_order (id),
            FOREIGN KEY (item_id) REFERENCES item (id),
            FOREIGN KEY (employee_id) REFERENCES employee (id)
        )
    ''')
    
    # AccountsPayable table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS accounts_payable (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            purchase_order_id INTEGER NOT NULL,
            supplier_id INTEGER NOT NULL,
            due_date DATETIME,
            amount FLOAT NOT NULL,
            status VARCHAR(20) DEFAULT 'pending',
            paid_date DATETIME,
            FOREIGN KEY (purchase_order_id) REFERENCES purchase_order (id),
            FOREIGN KEY (supplier_id) REFERENCES supplier (id)
        )
    ''')
    
    # AccountsReceivable table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS accounts_receivable (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sales_order_id INTEGER NOT NULL,
            customer_id INTEGER NOT NULL,
            due_date DATETIME,
            amount FLOAT NOT NULL,
            status VARCHAR(20) DEFAULT 'pending',
            paid_date DATETIME,
            FOREIGN KEY (sales_order_id) REFERENCES sales_order (id),
            FOREIGN KEY (customer_id) REFERENCES customer (id)
        )
    ''')
    
    # WorkerTask table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS worker_task (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL,
            task_type VARCHAR(50),
            description TEXT,
            assigned_date DATETIME DEFAULT CURRENT_TIMESTAMP,
            due_date DATETIME,
            status VARCHAR(20) DEFAULT 'pending',
            priority VARCHAR(20) DEFAULT 'medium',
            FOREIGN KEY (employee_id) REFERENCES employee (id)
        )
    ''')
    
    # StockAlert table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS stock_alert (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER NOT NULL,
            alert_type VARCHAR(20),
            message TEXT,
            created_date DATETIME DEFAULT CURRENT_TIMESTAMP,
            resolved BOOLEAN DEFAULT FALSE,
            FOREIGN KEY (item_id) REFERENCES item (id)
        )
    ''')
    
    # TallySyncLog table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tally_sync_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sync_type VARCHAR(50) NOT NULL,
            record_id INTEGER NOT NULL,
            record_type VARCHAR(50) NOT NULL,
            status VARCHAR(20) DEFAULT 'pending',
            message TEXT,
            created_date DATETIME DEFAULT CURRENT_TIMESTAMP,
            synced_date DATETIME
        )
    ''')
    
    # SystemLog table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS system_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action VARCHAR(100),
            description TEXT,
            ip_address VARCHAR(50),
            created_date DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES user (id)
        )
    ''')
    
    # BackupLog table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS backup_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename VARCHAR(200),
            backup_type VARCHAR(50),
            size VARCHAR(50),
            created_date DATETIME DEFAULT CURRENT_TIMESTAMP,
            status VARCHAR(20) DEFAULT 'completed'
        )
    ''')
    
    conn.commit()
    conn.close()
    print("Database schema created successfully!")

def create_default_data():
    """Create default users and sample data"""
    conn = sqlite3.connect('inventory.db')
    cursor = conn.cursor()
    
    print("Creating default data...")
    
    # Create default admin user
    cursor.execute("SELECT id FROM user WHERE username = 'admin'")
    if not cursor.fetchone():
        cursor.execute('''
            INSERT INTO user (username, password, role, email, phone, is_active)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            'admin',
            generate_password_hash('admin123'),
            'admin',
            'admin@inventory.com',
            '+91-9876543210',
            True
        ))
        print("Admin user created")
    
    # Create default manager user
    cursor.execute("SELECT id FROM user WHERE username = 'manager'")
    if not cursor.fetchone():
        cursor.execute('''
            INSERT INTO user (username, password, role, email, phone, is_active)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            'manager',
            generate_password_hash('manager123'),
            'manager',
            'manager@inventory.com',
            '+91-9876543212',
            True
        ))
        print("Manager user created")
    
    # Create default employee
    cursor.execute("SELECT id FROM employee")
    if not cursor.fetchone():
        cursor.execute('''
            INSERT INTO employee (name, role, department, hourly_rate, phone, email, address)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            'Rajesh Kumar',
            'Manager',
            'Operations',
            500.0,
            '+91-9876543211',
            'rajesh@company.com',
            'Mumbai, Maharashtra'
        ))
        print("Default employee created")
    
    # Create sample items if none exist
    cursor.execute("SELECT id FROM item")
    if not cursor.fetchone():
        sample_items = [
            ('Laptop Dell Inspiron', 'LAP001', 'Electronics', 10, 2, 45000, 55000, False, 'TALLY_LAP001'),
            ('Wireless Mouse', 'MOU001', 'Electronics', 50, 10, 450, 899, False, 'TALLY_MOU001'),
            ('Mechanical Keyboard', 'KEY001', 'Electronics', 30, 5, 1200, 2499, False, 'TALLY_KEY001'),
            ('27-inch Monitor', 'MON001', 'Electronics', 15, 3, 15000, 18999, False, 'TALLY_MON001'),
        ]
        
        cursor.executemany('''
            INSERT INTO item (name, sku, category, current_stock, min_stock_level, cost_price, selling_price, tally_synced, tally_guid)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', sample_items)
        print("Sample items created")
    
    # Create sample supplier
    cursor.execute("SELECT id FROM supplier")
    if not cursor.fetchone():
        cursor.execute('''
            INSERT INTO supplier (name, contact_person, phone, email, address, gst_number, tally_synced, tally_guid)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            'Tech Solutions India Pvt. Ltd.',
            'Amit Sharma',
            '+91-1122334455',
            'amit@techsolutions.com',
            'Delhi, India',
            '07AABCU9603R1ZM',
            False,
            'TALLY_SUP_001'
        ))
        print("Sample supplier created")
    
    # Create sample customer
    cursor.execute("SELECT id FROM customer")
    if not cursor.fetchone():
        cursor.execute('''
            INSERT INTO customer (name, phone, email, address, gst_number, credit_limit, tally_synced, tally_guid)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            'ABC Corporation India',
            '+91-9988776655',
            'purchase@abccorp.in',
            'Bangalore, Karnataka',
            '29AABCA1234A1Z5',
            500000,
            False,
            'TALLY_CUST_001'
        ))
        print("Sample customer created")
    
    conn.commit()
    conn.close()
    print("Default data creation completed!")

def migrate_database():
    """Main migration function"""
    try:
        # Backup existing database
        if os.path.exists('inventory.db'):
            print("Backing up existing database...")
            import shutil
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"inventory_backup_{timestamp}.db"
            shutil.copy2('inventory.db', backup_name)
            print(f"Backup created: {backup_name}")
        
        # Create schema and default data
        create_database_schema()
        create_default_data()
        
        print("Database migration completed successfully!")
        
    except Exception as e:
        print(f"Error during migration: {e}")
        raise e

if __name__ == '__main__':
    print("Starting database migration...")
    migrate_database()