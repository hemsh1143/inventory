# database.py
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), default='user')
    email = db.Column(db.String(120))
    phone = db.Column(db.String(20))
    created_date = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)

    def set_password(self, password):
        self.password = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password, password)

class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    sku = db.Column(db.String(50), unique=True, nullable=False)
    category = db.Column(db.String(50))
    current_stock = db.Column(db.Float, default=0)
    min_stock_level = db.Column(db.Float, default=5)
    cost_price = db.Column(db.Float, nullable=False)
    selling_price = db.Column(db.Float, nullable=False)
    created_date = db.Column(db.DateTime, default=datetime.utcnow)
    tally_synced = db.Column(db.Boolean, default=False)
    tally_guid = db.Column(db.String(100))

class Supplier(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    contact_person = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    email = db.Column(db.String(100))
    address = db.Column(db.Text)
    gst_number = db.Column(db.String(50))
    tally_synced = db.Column(db.Boolean, default=False)
    tally_guid = db.Column(db.String(100))

class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20))
    email = db.Column(db.String(100))
    address = db.Column(db.Text)
    gst_number = db.Column(db.String(50))
    credit_limit = db.Column(db.Float, default=0)
    tally_synced = db.Column(db.Boolean, default=False)
    tally_guid = db.Column(db.String(100))

class Employee(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(50))
    department = db.Column(db.String(50))
    hourly_rate = db.Column(db.Float, default=0)
    phone = db.Column(db.String(20))
    email = db.Column(db.String(100))
    address = db.Column(db.Text)
    join_date = db.Column(db.DateTime, default=datetime.utcnow)

class PurchaseOrder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey('supplier.id'), nullable=False)
    po_number = db.Column(db.String(100), unique=True, nullable=False)
    order_date = db.Column(db.DateTime, default=datetime.utcnow)
    total_amount = db.Column(db.Float, default=0)
    status = db.Column(db.String(20), default='pending')
    tally_synced = db.Column(db.Boolean, default=False)
    tally_voucher_no = db.Column(db.String(100))
    
    supplier = db.relationship('Supplier', backref='purchase_orders')
    items = db.relationship('PurchaseItem', backref='purchase_order', cascade='all, delete-orphan')

class PurchaseItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    purchase_order_id = db.Column(db.Integer, db.ForeignKey('purchase_order.id'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('item.id'), nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    unit_cost = db.Column(db.Float, nullable=False)
    total_cost = db.Column(db.Float, nullable=False)
    
    item = db.relationship('Item', backref='purchase_items')

class SalesOrder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=False)
    employee_id = db.Column(db.Integer, db.ForeignKey('employee.id'), nullable=False)
    invoice_number = db.Column(db.String(100), unique=True, nullable=False)
    sale_date = db.Column(db.DateTime, default=datetime.utcnow)
    total_amount = db.Column(db.Float, default=0)
    gst_amount = db.Column(db.Float, default=0)
    discount = db.Column(db.Float, default=0)
    status = db.Column(db.String(20), default='pending')
    tally_synced = db.Column(db.Boolean, default=False)
    tally_voucher_no = db.Column(db.String(100))
    
    customer = db.relationship('Customer', backref='sales_orders')
    employee = db.relationship('Employee', backref='sales')
    items = db.relationship('SaleItem', backref='sales_order', cascade='all, delete-orphan')

class SaleItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sales_order_id = db.Column(db.Integer, db.ForeignKey('sales_order.id'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('item.id'), nullable=False)
    employee_id = db.Column(db.Integer, db.ForeignKey('employee.id'), nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    unit_price = db.Column(db.Float, nullable=False)
    total_price = db.Column(db.Float, nullable=False)
    
    item = db.relationship('Item', backref='sale_items')
    employee = db.relationship('Employee', backref='sale_items')

class AccountsPayable(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    purchase_order_id = db.Column(db.Integer, db.ForeignKey('purchase_order.id'), nullable=False)
    supplier_id = db.Column(db.Integer, db.ForeignKey('supplier.id'), nullable=False)
    due_date = db.Column(db.DateTime)
    amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='pending')
    paid_date = db.Column(db.DateTime)
    
    purchase_order = db.relationship('PurchaseOrder', backref='payable_entry')
    supplier = db.relationship('Supplier', backref='payables')

class AccountsReceivable(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sales_order_id = db.Column(db.Integer, db.ForeignKey('sales_order.id'), nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=False)
    due_date = db.Column(db.DateTime)
    amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='pending')
    paid_date = db.Column(db.DateTime)
    
    sales_order = db.relationship('SalesOrder', backref='receivable_entry')
    customer = db.relationship('Customer', backref='receivables')

class WorkerTask(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employee.id'), nullable=False)
    task_type = db.Column(db.String(50))
    description = db.Column(db.Text)
    assigned_date = db.Column(db.DateTime, default=datetime.utcnow)
    due_date = db.Column(db.DateTime)
    status = db.Column(db.String(20), default='pending')
    priority = db.Column(db.String(20), default='medium')
    
    employee = db.relationship('Employee', backref='tasks')

class StockAlert(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('item.id'), nullable=False)
    alert_type = db.Column(db.String(20))
    message = db.Column(db.Text)
    created_date = db.Column(db.DateTime, default=datetime.utcnow)
    resolved = db.Column(db.Boolean, default=False)
    
    item = db.relationship('Item', backref='alerts')

class TallySyncLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sync_type = db.Column(db.String(50), nullable=False)
    record_id = db.Column(db.Integer, nullable=False)
    record_type = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(20), default='pending')
    message = db.Column(db.Text)
    created_date = db.Column(db.DateTime, default=datetime.utcnow)
    synced_date = db.Column(db.DateTime)

class SystemLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    action = db.Column(db.String(100))
    description = db.Column(db.Text)
    ip_address = db.Column(db.String(50))
    created_date = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref='logs')

class BackupLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(200))
    backup_type = db.Column(db.String(50))
    size = db.Column(db.String(50))
    created_date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='completed')