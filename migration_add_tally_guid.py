# migration_add_tally_guid.py
import os
import sqlite3
from datetime import datetime

def migrate_database():
    """Migration script to add tally_guid fields and update schema"""
    
    # Database file
    db_file = 'inventory.db'
    
    # Backup existing database
    if os.path.exists(db_file):
        print("Backing up existing database...")
        import shutil
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"inventory_backup_{timestamp}.db"
        shutil.copy2(db_file, backup_name)
        print(f"Backup created: {backup_name}")
    
    try:
        # Connect to database
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        
        print("Starting database migration...")
        
        # 1. Add tally_guid to Item table
        print("1. Adding tally_guid to Item table...")
        try:
            cursor.execute("ALTER TABLE item ADD COLUMN tally_guid VARCHAR(100)")
            print("   ✓ Added tally_guid to Item table")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                print("   ✓ tally_guid already exists in Item table")
            else:
                raise e
        
        # 2. Add tally_guid to Supplier table
        print("2. Adding tally_guid to Supplier table...")
        try:
            cursor.execute("ALTER TABLE supplier ADD COLUMN tally_guid VARCHAR(100)")
            print("   ✓ Added tally_guid to Supplier table")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                print("   ✓ tally_guid already exists in Supplier table")
            else:
                raise e
        
        # 3. Add tally_guid to Customer table
        print("3. Adding tally_guid to Customer table...")
        try:
            cursor.execute("ALTER TABLE customer ADD COLUMN tally_guid VARCHAR(100)")
            print("   ✓ Added tally_guid to Customer table")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                print("   ✓ tally_guid already exists in Customer table")
            else:
                raise e
        
        # 4. Check if User table has email and phone columns
        print("4. Checking User table structure...")
        cursor.execute("PRAGMA table_info(user)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'email' not in columns:
            print("   Adding email to User table...")
            cursor.execute("ALTER TABLE user ADD COLUMN email VARCHAR(120)")
            print("   ✓ Added email to User table")
        else:
            print("   ✓ email already exists in User table")
        
        if 'phone' not in columns:
            print("   Adding phone to User table...")
            cursor.execute("ALTER TABLE user ADD COLUMN phone VARCHAR(20)")
            print("   ✓ Added phone to User table")
        else:
            print("   ✓ phone already exists in User table")
        
        # 5. Create TallySyncLog table if it doesn't exist
        print("5. Checking TallySyncLog table...")
        cursor.execute("""
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
        """)
        print("   ✓ TallySyncLog table ensured")
        
        # 6. Create SystemLog table if it doesn't exist
        print("6. Checking SystemLog table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS system_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                action VARCHAR(100),
                description TEXT,
                ip_address VARCHAR(50),
                created_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES user (id)
            )
        """)
        print("   ✓ SystemLog table ensured")
        
        # 7. Create BackupLog table if it doesn't exist
        print("7. Checking BackupLog table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS backup_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename VARCHAR(200),
                backup_type VARCHAR(50),
                size VARCHAR(50),
                created_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                status VARCHAR(20) DEFAULT 'completed'
            )
        """)
        print("   ✓ BackupLog table ensured")
        
        # 8. Update existing records with sample tally_guid values
        print("8. Updating existing records with tally_guid...")
        
        # Update items
        cursor.execute("SELECT id, sku FROM item WHERE tally_guid IS NULL")
        items = cursor.fetchall()
        for item_id, sku in items:
            cursor.execute("UPDATE item SET tally_guid = ? WHERE id = ?", (f"TALLY_{sku}", item_id))
        print(f"   ✓ Updated {len(items)} items with tally_guid")
        
        # Update suppliers
        cursor.execute("SELECT id, name FROM supplier WHERE tally_guid IS NULL")
        suppliers = cursor.fetchall()
        for supplier_id, name in suppliers:
            cursor.execute("UPDATE supplier SET tally_guid = ? WHERE id = ?", 
                          (f"TALLY_SUP_{supplier_id}", supplier_id))
        print(f"   ✓ Updated {len(suppliers)} suppliers with tally_guid")
        
        # Update customers
        cursor.execute("SELECT id, name FROM customer WHERE tally_guid IS NULL")
        customers = cursor.fetchall()
        for customer_id, name in customers:
            cursor.execute("UPDATE customer SET tally_guid = ? WHERE id = ?", 
                          (f"TALLY_CUST_{customer_id}", customer_id))
        print(f"   ✓ Updated {len(customers)} customers with tally_guid")
        
        # 9. Update user records with email and phone if missing
        print("9. Updating user records...")
        cursor.execute("SELECT id, username FROM user WHERE email IS NULL")
        users = cursor.fetchall()
        for user_id, username in users:
            if username == 'admin':
                cursor.execute("UPDATE user SET email = 'admin@inventory.com', phone = '+91-9876543210' WHERE id = ?", (user_id,))
            elif username == 'manager':
                cursor.execute("UPDATE user SET email = 'manager@inventory.com', phone = '+91-9876543212' WHERE id = ?", (user_id,))
            else:
                cursor.execute("UPDATE user SET email = ?, phone = '+91-0000000000' WHERE id = ?", 
                              (f"{username}@inventory.com", user_id))
        print(f"   ✓ Updated {len(users)} users with email and phone")
        
        # Commit changes
        conn.commit()
        print("\n✅ Database migration completed successfully!")
        
        # Display migration summary
        print("\n📊 Migration Summary:")
        print(f"   - Items updated: {len(items)}")
        print(f"   - Suppliers updated: {len(suppliers)}")
        print(f"   - Customers updated: {len(customers)}")
        print(f"   - Users updated: {len(users)}")
        print(f"   - Backup created: {backup_name}")
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        conn.rollback()
        raise e
    finally:
        conn.close()

def verify_migration():
    """Verify that migration was successful"""
    print("\n🔍 Verifying migration...")
    
    try:
        conn = sqlite3.connect('inventory.db')
        cursor = conn.cursor()
        
        # Check tally_guid columns
        tables_to_check = ['item', 'supplier', 'customer']
        for table in tables_to_check:
            cursor.execute(f"PRAGMA table_info({table})")
            columns = [column[1] for column in cursor.fetchall()]
            if 'tally_guid' in columns:
                print(f"   ✓ {table} has tally_guid column")
            else:
                print(f"   ❌ {table} missing tally_guid column")
        
        # Check user columns
        cursor.execute("PRAGMA table_info(user)")
        user_columns = [column[1] for column in cursor.fetchall()]
        for column in ['email', 'phone']:
            if column in user_columns:
                print(f"   ✓ user has {column} column")
            else:
                print(f"   ❌ user missing {column} column")
        
        # Check log tables
        log_tables = ['tally_sync_log', 'system_log', 'backup_log']
        for table in log_tables:
            cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'")
            if cursor.fetchone():
                print(f"   ✓ {table} table exists")
            else:
                print(f"   ❌ {table} table missing")
        
        print("\n✅ Migration verification completed!")
        
    except Exception as e:
        print(f"❌ Verification failed: {e}")
    finally:
        conn.close()

if __name__ == '__main__':
    print("=" * 60)
    print("    INVENTORY SYSTEM DATABASE MIGRATION")
    print("=" * 60)
    
    migrate_database()
    verify_migration()
    
    print("\n" + "=" * 60)
    print("Next steps:")
    print("1. Run the application: python app.py")
    print("2. Test Tally import functionality")
    print("3. Verify all data is intact")
    print("=" * 60)