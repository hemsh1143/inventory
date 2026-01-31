# reset_database.py
import os
from app import app, db
from database import User, Item, Supplier, Customer, Employee
from werkzeug.security import generate_password_hash

def reset_database():
    with app.app_context():
        try:
            # Delete existing database
            if os.path.exists('inventory.db'):
                os.remove('inventory.db')
                print("Old database removed")
            
            # Create all tables
            db.create_all()
            print("New database created")
            
            # Create default admin user
            admin = User(
                username='admin',
                password=generate_password_hash('admin123'),
                role='admin',
                email='admin@inventory.com',
                phone='+91-9876543210'
            )
            db.session.add(admin)
            
            # Create manager user
            manager = User(
                username='manager',
                password=generate_password_hash('manager123'),
                role='manager',
                email='manager@inventory.com',
                phone='+91-9876543212'
            )
            db.session.add(manager)
            
            # Create default employee
            employee = Employee(
                name='Rajesh Kumar',
                role='Manager',
                department='Operations',
                hourly_rate=500.0,
                phone='+91-9876543211',
                email='rajesh@company.com',
                address='Mumbai, Maharashtra'
            )
            db.session.add(employee)
            
            # Create sample items
            items = [
                Item(name="Laptop Dell Inspiron", sku="LAP001", category="Electronics", current_stock=10, min_stock_level=2, cost_price=45000, selling_price=55000),
                Item(name="Wireless Mouse", sku="MOU001", category="Electronics", current_stock=50, min_stock_level=10, cost_price=450, selling_price=899),
                Item(name="Mechanical Keyboard", sku="KEY001", category="Electronics", current_stock=30, min_stock_level=5, cost_price=1200, selling_price=2499),
                Item(name="27-inch Monitor", sku="MON001", category="Electronics", current_stock=15, min_stock_level=3, cost_price=15000, selling_price=18999),
            ]
            for item in items:
                db.session.add(item)
            
            # Create sample supplier
            supplier = Supplier(
                name="Tech Solutions India Pvt. Ltd.", 
                contact_person="Amit Sharma", 
                phone="+91-1122334455",
                email="amit@techsolutions.com",
                address="Delhi, India",
                gst_number="07AABCU9603R1ZM"
            )
            db.session.add(supplier)
            
            # Create sample customer
            customer = Customer(
                name="ABC Corporation India", 
                phone="+91-9988776655", 
                email="purchase@abccorp.in",
                address="Bangalore, Karnataka",
                gst_number="29AABCA1234A1Z5",
                credit_limit=500000
            )
            db.session.add(customer)
            
            db.session.commit()
            print("Database reset completed successfully!")
            print("Default users created:")
            print("  Admin: admin / admin123")
            print("  Manager: manager / manager123")
            
        except Exception as e:
            print(f"Error resetting database: {e}")
            import traceback
            traceback.print_exc()

if __name__ == '__main__':
    reset_database()