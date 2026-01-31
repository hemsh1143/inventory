# app.py - COMPLETE WORKING VERSION
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import random
import os
import pandas as pd
from io import BytesIO
import shutil
from functools import wraps

# Import database after initializing app to avoid circular imports
from database import db, User, Item, Supplier, Customer, Employee, PurchaseOrder, PurchaseItem, SalesOrder, SaleItem, AccountsPayable, AccountsReceivable, WorkerTask, StockAlert, TallySyncLog, SystemLog, BackupLog
from tally_integration import TallyIntegration

app = Flask(__name__)
app.config['SECRET_KEY'] = 'inventory-system-secret-key-2024'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///inventory.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize extensions
db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('Administrator access required!', 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

def log_activity(action, description):
    try:
        log = SystemLog(
            user_id=current_user.id if current_user.is_authenticated else None,
            action=action,
            description=description,
            ip_address=request.remote_addr
        )
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        print(f"Error logging activity: {e}")

def format_currency(amount):
    return f"₹{amount:,.2f}"

def generate_po_number():
    return f"PO{datetime.now().strftime('%Y%m%d')}{random.randint(1000, 9999)}"

def generate_invoice_number():
    return f"INV{datetime.now().strftime('%Y%m%d')}{random.randint(1000, 9999)}"

def update_stock_alert(item_id):
    try:
        item = Item.query.get(item_id)
        if item:
            # Remove existing unresolved alerts for this item
            StockAlert.query.filter_by(item_id=item_id, resolved=False).delete()
            
            if item.current_stock <= 0:
                alert = StockAlert(
                    item_id=item_id,
                    alert_type='out_of_stock',
                    message=f'OUT OF STOCK: {item.name} needs immediate restocking'
                )
                db.session.add(alert)
            elif item.current_stock <= item.min_stock_level:
                alert = StockAlert(
                    item_id=item_id,
                    alert_type='low_stock',
                    message=f'Low stock alert: {item.name} has only {item.current_stock} units left'
                )
                db.session.add(alert)
            
            db.session.commit()
    except Exception as e:
        print(f"Error updating stock alert: {e}")
        db.session.rollback()

# Routes
@app.route('/')
@login_required
def dashboard():
    try:
        stats = {
            'total_items': Item.query.count(),
            'low_stock': StockAlert.query.filter_by(resolved=False).count(),
            'total_payable': db.session.query(db.func.sum(AccountsPayable.amount)).filter_by(status='pending').scalar() or 0,
            'total_receivable': db.session.query(db.func.sum(AccountsReceivable.amount)).filter_by(status='pending').scalar() or 0,
            'pending_tasks': WorkerTask.query.filter_by(status='pending').count(),
            'total_sales_today': db.session.query(db.func.sum(SalesOrder.total_amount)).filter(
                db.func.date(SalesOrder.sale_date) == datetime.now().date()
            ).scalar() or 0
        }
        
        recent_alerts = StockAlert.query.filter_by(resolved=False).order_by(StockAlert.created_date.desc()).limit(5).all()
        pending_tasks = WorkerTask.query.filter_by(status='pending').order_by(WorkerTask.due_date).limit(5).all()
        recent_sales = SalesOrder.query.order_by(SalesOrder.sale_date.desc()).limit(5).all()
        
        return render_template('dashboard.html', stats=stats, alerts=recent_alerts, tasks=pending_tasks, recent_sales=recent_sales, format_currency=format_currency)
    except Exception as e:
        flash(f'Error loading dashboard: {str(e)}', 'danger')
        return render_template('dashboard.html', stats={}, alerts=[], tasks=[], recent_sales=[], format_currency=format_currency)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if not username or not password:
            flash('Please enter both username and password', 'warning')
            return render_template('login.html')
        
        user = User.query.filter_by(username=username, is_active=True).first()
        
        if user and check_password_hash(user.password, password):
            login_user(user)
            log_activity('LOGIN', f'User {username} logged in')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('dashboard'))
        else:
            flash('Invalid credentials or account disabled', 'danger')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    log_activity('LOGOUT', f'User {current_user.username} logged out')
    logout_user()
    return redirect(url_for('login'))

# Items Management
@app.route('/items')
@login_required
def items():
    try:
        all_items = Item.query.all()
        return render_template('items.html', items=all_items, format_currency=format_currency)
    except Exception as e:
        flash(f'Error loading items: {str(e)}', 'danger')
        return render_template('items.html', items=[], format_currency=format_currency)

@app.route('/add_item', methods=['POST'])
@login_required
def add_item():
    try:
        name = request.form.get('name')
        sku = request.form.get('sku')
        category = request.form.get('category')
        current_stock = float(request.form.get('current_stock', 0))
        min_stock_level = float(request.form.get('min_stock_level', 5))
        cost_price = float(request.form.get('cost_price', 0))
        selling_price = float(request.form.get('selling_price', 0))
        
        if not name or not sku:
            flash('Name and SKU are required', 'warning')
            return redirect(url_for('items'))
        
        # Check if SKU already exists
        if Item.query.filter_by(sku=sku).first():
            flash('SKU already exists', 'warning')
            return redirect(url_for('items'))
        
        item = Item(
            name=name, sku=sku, category=category, current_stock=current_stock,
            min_stock_level=min_stock_level, cost_price=cost_price, selling_price=selling_price
        )
        
        db.session.add(item)
        db.session.commit()
        
        update_stock_alert(item.id)
        log_activity('ADD_ITEM', f'Added item: {name} (SKU: {sku})')
        flash('Item added successfully', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error adding item: {str(e)}', 'danger')
    
    return redirect(url_for('items'))

@app.route('/edit_item/<int:item_id>', methods=['POST'])
@login_required
def edit_item(item_id):
    try:
        item = Item.query.get(item_id)
        if item:
            item.name = request.form.get('name')
            item.sku = request.form.get('sku')
            item.category = request.form.get('category')
            item.current_stock = float(request.form.get('current_stock', 0))
            item.min_stock_level = float(request.form.get('min_stock_level', 5))
            item.cost_price = float(request.form.get('cost_price', 0))
            item.selling_price = float(request.form.get('selling_price', 0))
            
            db.session.commit()
            update_stock_alert(item.id)
            log_activity('EDIT_ITEM', f'Edited item: {item.name} (ID: {item_id})')
            flash('Item updated successfully', 'success')
        else:
            flash('Item not found', 'warning')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating item: {str(e)}', 'danger')
    
    return redirect(url_for('items'))

@app.route('/delete_item/<int:item_id>')
@login_required
def delete_item(item_id):
    try:
        item = Item.query.get(item_id)
        if item:
            item_name = item.name
            db.session.delete(item)
            db.session.commit()
            log_activity('DELETE_ITEM', f'Deleted item: {item_name} (ID: {item_id})')
            flash('Item deleted successfully', 'success')
        else:
            flash('Item not found', 'warning')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting item: {str(e)}', 'danger')
    
    return redirect(url_for('items'))

# Purchase Management
@app.route('/purchase')
@login_required
def purchase():
    try:
        purchases = PurchaseOrder.query.all()
        suppliers = Supplier.query.all()
        items = Item.query.all()
        return render_template('purchase.html', purchases=purchases, suppliers=suppliers, items=items, format_currency=format_currency)
    except Exception as e:
        flash(f'Error loading purchases: {str(e)}', 'danger')
        return render_template('purchase.html', purchases=[], suppliers=[], items=[], format_currency=format_currency)

@app.route('/create_purchase', methods=['POST'])
@login_required
def create_purchase():
    try:
        supplier_id = request.form.get('supplier_id')
        items = request.form.getlist('item_id[]')
        quantities = request.form.getlist('quantity[]')
        unit_costs = request.form.getlist('unit_cost[]')
        
        if not supplier_id:
            flash('Supplier is required', 'warning')
            return redirect(url_for('purchase'))
        
        po = PurchaseOrder(
            supplier_id=supplier_id,
            po_number=generate_po_number(),
            status='pending'
        )
        db.session.add(po)
        db.session.flush()
        
        total_amount = 0
        for i in range(len(items)):
            if items[i] and quantities[i] and unit_costs[i]:
                quantity = float(quantities[i])
                unit_cost = float(unit_costs[i])
                total_cost = quantity * unit_cost
                
                purchase_item = PurchaseItem(
                    purchase_order_id=po.id,
                    item_id=items[i],
                    quantity=quantity,
                    unit_cost=unit_cost,
                    total_cost=total_cost
                )
                db.session.add(purchase_item)
                total_amount += total_cost
        
        po.total_amount = total_amount
        db.session.commit()
        log_activity('CREATE_PURCHASE', f'Created purchase order: {po.po_number}')
        flash('Purchase order created successfully', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error creating purchase: {str(e)}', 'danger')
    
    return redirect(url_for('purchase'))

@app.route('/receive_purchase/<int:po_id>')
@login_required
def receive_purchase(po_id):
    try:
        po = PurchaseOrder.query.get(po_id)
        if po and po.status == 'pending':
            po.status = 'received'
            
            # Update stock
            for purchase_item in po.items:
                item = Item.query.get(purchase_item.item_id)
                if item:
                    item.current_stock += purchase_item.quantity
                    update_stock_alert(purchase_item.item_id)
            
            # Create payable entry
            payable = AccountsPayable(
                purchase_order_id=po.id,
                supplier_id=po.supplier_id,
                due_date=datetime.now() + timedelta(days=30),
                amount=po.total_amount,
                status='pending'
            )
            db.session.add(payable)
            
            db.session.commit()
            log_activity('RECEIVE_PURCHASE', f'Received purchase order: {po.po_number}')
            flash('Purchase order received and stock updated', 'success')
        else:
            flash('Purchase order not found or already received', 'warning')
    except Exception as e:
        db.session.rollback()
        flash(f'Error receiving purchase: {str(e)}', 'danger')
    
    return redirect(url_for('purchase'))

# Sales Management
@app.route('/sales')
@login_required
def sales():
    try:
        sales_orders = SalesOrder.query.all()
        customers = Customer.query.all()
        items = Item.query.all()
        employees = Employee.query.all()
        return render_template('sales.html', sales=sales_orders, customers=customers, items=items, employees=employees, format_currency=format_currency)
    except Exception as e:
        flash(f'Error loading sales: {str(e)}', 'danger')
        return render_template('sales.html', sales=[], customers=[], items=[], employees=[], format_currency=format_currency)

@app.route('/create_sale', methods=['POST'])
@login_required
def create_sale():
    try:
        customer_id = request.form.get('customer_id')
        employee_id = request.form.get('employee_id')
        items = request.form.getlist('item_id[]')
        quantities = request.form.getlist('quantity[]')
        assigned_employees = request.form.getlist('assigned_employee[]')
        discount = float(request.form.get('discount', 0))
        
        if not customer_id or not employee_id:
            flash('Customer and employee are required', 'warning')
            return redirect(url_for('sales'))
        
        # Check stock availability first
        for i in range(len(items)):
            if items[i] and quantities[i]:
                item = Item.query.get(items[i])
                quantity = float(quantities[i])
                if item and item.current_stock < quantity:
                    flash(f'Insufficient stock for {item.name}. Available: {item.current_stock}', 'warning')
                    return redirect(url_for('sales'))
        
        sale = SalesOrder(
            customer_id=customer_id,
            employee_id=employee_id,
            invoice_number=generate_invoice_number(),
            status='pending',
            discount=discount
        )
        db.session.add(sale)
        db.session.flush()
        
        total_amount = 0
        for i in range(len(items)):
            if items[i] and quantities[i] and assigned_employees[i]:
                item = Item.query.get(items[i])
                if item:
                    quantity = float(quantities[i])
                    unit_price = item.selling_price
                    total_price = quantity * unit_price
                    
                    sale_item = SaleItem(
                        sales_order_id=sale.id,
                        item_id=items[i],
                        employee_id=assigned_employees[i],
                        quantity=quantity,
                        unit_price=unit_price,
                        total_price=total_price
                    )
                    db.session.add(sale_item)
                    total_amount += total_price
        
        # Apply discount and calculate GST (18%)
        sale.total_amount = total_amount - discount
        sale.gst_amount = sale.total_amount * 0.18
        sale.total_amount += sale.gst_amount
        
        db.session.commit()
        log_activity('CREATE_SALE', f'Created sales order: {sale.invoice_number}')
        flash('Sales order created successfully', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error creating sale: {str(e)}', 'danger')
    
    return redirect(url_for('sales'))

@app.route('/complete_sale/<int:sale_id>')
@login_required
def complete_sale(sale_id):
    try:
        sale = SalesOrder.query.get(sale_id)
        if sale and sale.status == 'pending':
            sale.status = 'completed'
            
            # Update stock
            for sale_item in sale.items:
                item = Item.query.get(sale_item.item_id)
                if item:
                    item.current_stock -= sale_item.quantity
                    update_stock_alert(sale_item.item_id)
            
            # Create receivable entry
            receivable = AccountsReceivable(
                sales_order_id=sale.id,
                customer_id=sale.customer_id,
                due_date=datetime.now() + timedelta(days=30),
                amount=sale.total_amount,
                status='pending'
            )
            db.session.add(receivable)
            
            db.session.commit()
            log_activity('COMPLETE_SALE', f'Completed sales order: {sale.invoice_number}')
            flash('Sale completed and stock updated', 'success')
        else:
            flash('Sale not found or already completed', 'warning')
    except Exception as e:
        db.session.rollback()
        flash(f'Error completing sale: {str(e)}', 'danger')
    
    return redirect(url_for('sales'))

# Accounts Payable
@app.route('/payable')
@login_required
def payable():
    try:
        payables = AccountsPayable.query.all()
        return render_template('payable.html', payables=payables, format_currency=format_currency)
    except Exception as e:
        flash(f'Error loading payables: {str(e)}', 'danger')
        return render_template('payable.html', payables=[], format_currency=format_currency)

@app.route('/mark_paid/<int:payable_id>')
@login_required
def mark_paid(payable_id):
    try:
        payable = AccountsPayable.query.get(payable_id)
        if payable and payable.status == 'pending':
            payable.status = 'paid'
            payable.paid_date = datetime.now()
            db.session.commit()
            log_activity('MARK_PAID', f'Marked payable as paid: {payable.id}')
            flash('Payment marked as paid', 'success')
        else:
            flash('Payable not found or already paid', 'warning')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating payment: {str(e)}', 'danger')
    
    return redirect(url_for('payable'))

# Accounts Receivable
@app.route('/receivable')
@login_required
def receivable():
    try:
        receivables = AccountsReceivable.query.all()
        return render_template('receivable.html', receivables=receivables, format_currency=format_currency)
    except Exception as e:
        flash(f'Error loading receivables: {str(e)}', 'danger')
        return render_template('receivable.html', receivables=[], format_currency=format_currency)

@app.route('/mark_received/<int:receivable_id>')
@login_required
def mark_received(receivable_id):
    try:
        receivable = AccountsReceivable.query.get(receivable_id)
        if receivable and receivable.status == 'pending':
            receivable.status = 'paid'
            receivable.paid_date = datetime.now()
            db.session.commit()
            log_activity('MARK_RECEIVED', f'Marked receivable as paid: {receivable.id}')
            flash('Payment marked as received', 'success')
        else:
            flash('Receivable not found or already paid', 'warning')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating receipt: {str(e)}', 'danger')
    
    return redirect(url_for('receivable'))

# Suppliers Management
@app.route('/suppliers')
@login_required
def suppliers():
    try:
        all_suppliers = Supplier.query.all()
        return render_template('suppliers.html', suppliers=all_suppliers)
    except Exception as e:
        flash(f'Error loading suppliers: {str(e)}', 'danger')
        return render_template('suppliers.html', suppliers=[])

@app.route('/add_supplier', methods=['POST'])
@login_required
def add_supplier():
    try:
        name = request.form.get('name')
        contact_person = request.form.get('contact_person')
        phone = request.form.get('phone')
        email = request.form.get('email')
        address = request.form.get('address')
        gst_number = request.form.get('gst_number')
        
        if not name:
            flash('Supplier name is required', 'warning')
            return redirect(url_for('suppliers'))
        
        supplier = Supplier(
            name=name,
            contact_person=contact_person,
            phone=phone,
            email=email,
            address=address,
            gst_number=gst_number
        )
        
        db.session.add(supplier)
        db.session.commit()
        log_activity('ADD_SUPPLIER', f'Added supplier: {name}')
        flash('Supplier added successfully', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error adding supplier: {str(e)}', 'danger')
    
    return redirect(url_for('suppliers'))

@app.route('/edit_supplier/<int:supplier_id>', methods=['POST'])
@login_required
def edit_supplier(supplier_id):
    try:
        supplier = Supplier.query.get(supplier_id)
        if supplier:
            supplier.name = request.form.get('name')
            supplier.contact_person = request.form.get('contact_person')
            supplier.phone = request.form.get('phone')
            supplier.email = request.form.get('email')
            supplier.address = request.form.get('address')
            supplier.gst_number = request.form.get('gst_number')
            
            db.session.commit()
            log_activity('EDIT_SUPPLIER', f'Edited supplier: {supplier.name}')
            flash('Supplier updated successfully', 'success')
        else:
            flash('Supplier not found', 'warning')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating supplier: {str(e)}', 'danger')
    
    return redirect(url_for('suppliers'))

@app.route('/delete_supplier/<int:supplier_id>')
@login_required
def delete_supplier(supplier_id):
    try:
        supplier = Supplier.query.get(supplier_id)
        if supplier:
            supplier_name = supplier.name
            db.session.delete(supplier)
            db.session.commit()
            log_activity('DELETE_SUPPLIER', f'Deleted supplier: {supplier_name}')
            flash('Supplier deleted successfully', 'success')
        else:
            flash('Supplier not found', 'warning')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting supplier: {str(e)}', 'danger')
    
    return redirect(url_for('suppliers'))

# Customers Management
@app.route('/customers')
@login_required
def customers():
    try:
        all_customers = Customer.query.all()
        return render_template('customers.html', customers=all_customers, format_currency=format_currency)
    except Exception as e:
        flash(f'Error loading customers: {str(e)}', 'danger')
        return render_template('customers.html', customers=[], format_currency=format_currency)

@app.route('/add_customer', methods=['POST'])
@login_required
def add_customer():
    try:
        name = request.form.get('name')
        phone = request.form.get('phone')
        email = request.form.get('email')
        address = request.form.get('address')
        gst_number = request.form.get('gst_number')
        credit_limit = float(request.form.get('credit_limit', 0))
        
        if not name:
            flash('Customer name is required', 'warning')
            return redirect(url_for('customers'))
        
        customer = Customer(
            name=name,
            phone=phone,
            email=email,
            address=address,
            gst_number=gst_number,
            credit_limit=credit_limit
        )
        
        db.session.add(customer)
        db.session.commit()
        log_activity('ADD_CUSTOMER', f'Added customer: {name}')
        flash('Customer added successfully', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error adding customer: {str(e)}', 'danger')
    
    return redirect(url_for('customers'))

@app.route('/edit_customer/<int:customer_id>', methods=['POST'])
@login_required
def edit_customer(customer_id):
    try:
        customer = Customer.query.get(customer_id)
        if customer:
            customer.name = request.form.get('name')
            customer.phone = request.form.get('phone')
            customer.email = request.form.get('email')
            customer.address = request.form.get('address')
            customer.gst_number = request.form.get('gst_number')
            customer.credit_limit = float(request.form.get('credit_limit', 0))
            
            db.session.commit()
            log_activity('EDIT_CUSTOMER', f'Edited customer: {customer.name}')
            flash('Customer updated successfully', 'success')
        else:
            flash('Customer not found', 'warning')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating customer: {str(e)}', 'danger')
    
    return redirect(url_for('customers'))

@app.route('/delete_customer/<int:customer_id>')
@login_required
def delete_customer(customer_id):
    try:
        customer = Customer.query.get(customer_id)
        if customer:
            customer_name = customer.name
            db.session.delete(customer)
            db.session.commit()
            log_activity('DELETE_CUSTOMER', f'Deleted customer: {customer_name}')
            flash('Customer deleted successfully', 'success')
        else:
            flash('Customer not found', 'warning')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting customer: {str(e)}', 'danger')
    
    return redirect(url_for('customers'))

# Workers Management
@app.route('/workers')
@login_required
def workers():
    try:
        all_workers = Employee.query.all()
        return render_template('workers.html', workers=all_workers, format_currency=format_currency)
    except Exception as e:
        flash(f'Error loading workers: {str(e)}', 'danger')
        return render_template('workers.html', workers=[], format_currency=format_currency)

@app.route('/add_worker', methods=['POST'])
@login_required
def add_worker():
    try:
        name = request.form.get('name')
        role = request.form.get('role')
        department = request.form.get('department')
        hourly_rate = float(request.form.get('hourly_rate', 0))
        phone = request.form.get('phone')
        email = request.form.get('email')
        address = request.form.get('address')
        
        if not name:
            flash('Worker name is required', 'warning')
            return redirect(url_for('workers'))
        
        worker = Employee(
            name=name,
            role=role,
            department=department,
            hourly_rate=hourly_rate,
            phone=phone,
            email=email,
            address=address
        )
        
        db.session.add(worker)
        db.session.commit()
        log_activity('ADD_WORKER', f'Added worker: {name}')
        flash('Worker added successfully', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error adding worker: {str(e)}', 'danger')
    
    return redirect(url_for('workers'))

@app.route('/edit_worker/<int:worker_id>', methods=['POST'])
@login_required
def edit_worker(worker_id):
    try:
        worker = Employee.query.get(worker_id)
        if worker:
            worker.name = request.form.get('name')
            worker.role = request.form.get('role')
            worker.department = request.form.get('department')
            worker.hourly_rate = float(request.form.get('hourly_rate', 0))
            worker.phone = request.form.get('phone')
            worker.email = request.form.get('email')
            worker.address = request.form.get('address')
            
            db.session.commit()
            log_activity('EDIT_WORKER', f'Edited worker: {worker.name}')
            flash('Worker updated successfully', 'success')
        else:
            flash('Worker not found', 'warning')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating worker: {str(e)}', 'danger')
    
    return redirect(url_for('workers'))

@app.route('/delete_worker/<int:worker_id>')
@login_required
def delete_worker(worker_id):
    try:
        worker = Employee.query.get(worker_id)
        if worker:
            worker_name = worker.name
            db.session.delete(worker)
            db.session.commit()
            log_activity('DELETE_WORKER', f'Deleted worker: {worker_name}')
            flash('Worker deleted successfully', 'success')
        else:
            flash('Worker not found', 'warning')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting worker: {str(e)}', 'danger')
    
    return redirect(url_for('workers'))

# Tasks Management
@app.route('/tasks')
@login_required
def tasks():
    try:
        tasks_list = WorkerTask.query.all()
        employees = Employee.query.all()
        return render_template('tasks.html', tasks=tasks_list, employees=employees)
    except Exception as e:
        flash(f'Error loading tasks: {str(e)}', 'danger')
        return render_template('tasks.html', tasks=[], employees=[])

@app.route('/add_task', methods=['POST'])
@login_required
def add_task():
    try:
        employee_id = request.form.get('employee_id')
        task_type = request.form.get('task_type')
        description = request.form.get('description')
        due_date_str = request.form.get('due_date')
        priority = request.form.get('priority')
        
        if not employee_id or not task_type:
            flash('Employee and task type are required', 'warning')
            return redirect(url_for('tasks'))
        
        due_date = None
        if due_date_str:
            due_date = datetime.strptime(due_date_str, '%Y-%m-%d')
        
        task = WorkerTask(
            employee_id=employee_id,
            task_type=task_type,
            description=description,
            due_date=due_date,
            priority=priority
        )
        
        db.session.add(task)
        db.session.commit()
        log_activity('ADD_TASK', f'Added task for employee ID: {employee_id}')
        flash('Task added successfully', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error adding task: {str(e)}', 'danger')
    
    return redirect(url_for('tasks'))

@app.route('/update_task_status/<int:task_id>/<status>')
@login_required
def update_task_status(task_id, status):
    try:
        task = WorkerTask.query.get(task_id)
        if task:
            task.status = status
            db.session.commit()
            log_activity('UPDATE_TASK_STATUS', f'Updated task {task_id} to {status}')
            flash('Task status updated', 'success')
        else:
            flash('Task not found', 'warning')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating task: {str(e)}', 'danger')
    
    return redirect(url_for('tasks'))

@app.route('/delete_task/<int:task_id>')
@login_required
def delete_task(task_id):
    try:
        task = WorkerTask.query.get(task_id)
        if task:
            db.session.delete(task)
            db.session.commit()
            log_activity('DELETE_TASK', f'Deleted task ID: {task_id}')
            flash('Task deleted successfully', 'success')
        else:
            flash('Task not found', 'warning')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting task: {str(e)}', 'danger')
    
    return redirect(url_for('tasks'))

# Reports
@app.route('/reports')
@login_required
def reports():
    try:
        stock_status = Item.query.all()
        payable_report = AccountsPayable.query.all()
        receivable_report = AccountsReceivable.query.all()
        sales_report = SalesOrder.query.order_by(SalesOrder.sale_date.desc()).limit(10).all()
        tasks_report = WorkerTask.query.order_by(WorkerTask.assigned_date.desc()).limit(10).all()
        
        # Calculate totals
        total_items = Item.query.count()
        low_stock_count = StockAlert.query.filter_by(resolved=False).count()
        total_payable = db.session.query(db.func.sum(AccountsPayable.amount)).filter_by(status='pending').scalar() or 0
        total_receivable = db.session.query(db.func.sum(AccountsReceivable.amount)).filter_by(status='pending').scalar() or 0
        
        return render_template('reports.html', 
                             stock_status=stock_status,
                             payable_report=payable_report,
                             receivable_report=receivable_report,
                             sales_report=sales_report,
                             tasks_report=tasks_report,
                             total_items=total_items,
                             low_stock_count=low_stock_count,
                             total_payable=total_payable,
                             total_receivable=total_receivable,
                             format_currency=format_currency)
    except Exception as e:
        flash(f'Error loading reports: {str(e)}', 'danger')
        return render_template('reports.html', 
                             stock_status=[], 
                             payable_report=[], 
                             receivable_report=[],
                             sales_report=[],
                             tasks_report=[],
                             total_items=0,
                             low_stock_count=0,
                             total_payable=0,
                             total_receivable=0,
                             format_currency=format_currency)

# Export to Excel
@app.route('/export_excel/<report_type>')
@login_required
def export_excel(report_type):
    try:
        if report_type == 'stock':
            data = Item.query.all()
            df_data = []
            for item in data:
                df_data.append({
                    'Name': item.name,
                    'SKU': item.sku,
                    'Category': item.category or '',
                    'Current Stock': item.current_stock,
                    'Min Stock Level': item.min_stock_level,
                    'Cost Price': item.cost_price,
                    'Selling Price': item.selling_price,
                    'Status': 'Out of Stock' if item.current_stock <= 0 else 'Low Stock' if item.current_stock <= item.min_stock_level else 'Adequate'
                })
            df = pd.DataFrame(df_data)
            filename = f'stock_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
            
        elif report_type == 'sales':
            data = SalesOrder.query.all()
            df_data = []
            for sale in data:
                df_data.append({
                    'Invoice Number': sale.invoice_number,
                    'Customer': sale.customer.name if sale.customer else '',
                    'Sales Person': sale.employee.name if sale.employee else '',
                    'Date': sale.sale_date.strftime('%Y-%m-%d') if sale.sale_date else '',
                    'Total Amount': sale.total_amount,
                    'GST Amount': sale.gst_amount,
                    'Discount': sale.discount,
                    'Status': sale.status
                })
            df = pd.DataFrame(df_data)
            filename = f'sales_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
            
        elif report_type == 'payable':
            data = AccountsPayable.query.all()
            df_data = []
            for payable in data:
                df_data.append({
                    'Supplier': payable.supplier.name if payable.supplier else '',
                    'PO Number': payable.purchase_order.po_number if payable.purchase_order else '',
                    'Amount': payable.amount,
                    'Due Date': payable.due_date.strftime('%Y-%m-%d') if payable.due_date else '',
                    'Status': payable.status
                })
            df = pd.DataFrame(df_data)
            filename = f'payable_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
            
        elif report_type == 'receivable':
            data = AccountsReceivable.query.all()
            df_data = []
            for receivable in data:
                df_data.append({
                    'Customer': receivable.customer.name if receivable.customer else '',
                    'Invoice Number': receivable.sales_order.invoice_number if receivable.sales_order else '',
                    'Amount': receivable.amount,
                    'Due Date': receivable.due_date.strftime('%Y-%m-%d') if receivable.due_date else '',
                    'Status': receivable.status
                })
            df = pd.DataFrame(df_data)
            filename = f'receivable_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
            
        else:
            flash('Invalid report type', 'warning')
            return redirect(url_for('reports'))
        
        # Create Excel file in memory
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Report')
        
        output.seek(0)
        
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        flash(f'Error exporting to Excel: {str(e)}', 'danger')
        return redirect(url_for('reports'))

# Tally Integration Routes
@app.route('/tally_sync')
@login_required
def tally_sync():
    try:
        # Get sync statistics
        total_items = Item.query.count()
        synced_items = Item.query.filter_by(tally_synced=True).count()
        
        total_suppliers = Supplier.query.count()
        synced_suppliers = Supplier.query.filter_by(tally_synced=True).count()
        
        total_customers = Customer.query.count()
        synced_customers = Customer.query.filter_by(tally_synced=True).count()
        
        total_purchases = PurchaseOrder.query.count()
        synced_purchases = PurchaseOrder.query.filter_by(tally_synced=True).count()
        
        total_sales = SalesOrder.query.count()
        synced_sales = SalesOrder.query.filter_by(tally_synced=True).count()
        
        sync_logs = TallySyncLog.query.order_by(TallySyncLog.created_date.desc()).limit(50).all()
        
        stats = {
            'items': {'total': total_items, 'synced': synced_items},
            'suppliers': {'total': total_suppliers, 'synced': synced_suppliers},
            'customers': {'total': total_customers, 'synced': synced_customers},
            'purchases': {'total': total_purchases, 'synced': synced_purchases},
            'sales': {'total': total_sales, 'synced': synced_sales}
        }
        
        return render_template('tally_sync.html', stats=stats, logs=sync_logs)
    except Exception as e:
        flash(f'Error loading Tally sync page: {str(e)}', 'danger')
        return render_template('tally_sync.html', stats={}, logs=[])

@app.route('/sync_item_to_tally/<int:item_id>')
@login_required
def sync_item_to_tally(item_id):
    try:
        item = Item.query.get(item_id)
        if item:
            # Simulate Tally sync
            item.tally_synced = True
            log = TallySyncLog(
                sync_type='ITEM',
                record_id=item.id,
                record_type='Item',
                status='success',
                message='Item synced successfully (simulated)',
                synced_date=datetime.now()
            )
            db.session.add(log)
            db.session.commit()
            log_activity('SYNC_ITEM_TALLY', f'Synced item to Tally: {item.name}')
            flash('Item synced to Tally successfully (simulated)', 'success')
        else:
            flash('Item not found', 'warning')
    except Exception as e:
        db.session.rollback()
        flash(f'Error syncing item to Tally: {str(e)}', 'danger')
    
    return redirect(url_for('items'))

@app.route('/bulk_sync_to_tally')
@login_required
def bulk_sync_to_tally():
    try:
        # Simulate bulk sync
        items = Item.query.filter_by(tally_synced=False).all()
        for item in items:
            item.tally_synced = True
        
        log = TallySyncLog(
            sync_type='BULK',
            record_id=0,
            record_type='All',
            status='success',
            message=f'Bulk sync completed: {len(items)} items synced (simulated)',
            synced_date=datetime.now()
        )
        db.session.add(log)
        db.session.commit()
        log_activity('BULK_SYNC_TALLY', f'Bulk synced {len(items)} items to Tally')
        flash(f'Bulk sync completed: {len(items)} records synced successfully (simulated)', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error during bulk sync: {str(e)}', 'danger')
    
    return redirect(url_for('tally_sync'))

# Tally Import Routes
@app.route('/import_items_from_tally')
@login_required
def import_items_from_tally():
    """Import items from Tally"""
    try:
        tally = TallyIntegration()
        success, message = tally.import_items_from_tally()
        
        if success:
            flash(f'Items imported successfully: {message}', 'success')
        else:
            flash(f'Failed to import items: {message}', 'danger')
            
    except Exception as e:
        flash(f'Error importing items: {str(e)}', 'danger')
    
    return redirect(url_for('tally_sync'))

@app.route('/import_suppliers_from_tally')
@login_required
def import_suppliers_from_tally():
    """Import suppliers from Tally"""
    try:
        tally = TallyIntegration()
        success, message = tally.import_suppliers_from_tally()
        
        if success:
            flash(f'Suppliers imported successfully: {message}', 'success')
        else:
            flash(f'Failed to import suppliers: {message}', 'danger')
            
    except Exception as e:
        flash(f'Error importing suppliers: {str(e)}', 'danger')
    
    return redirect(url_for('tally_sync'))

@app.route('/import_customers_from_tally')
@login_required
def import_customers_from_tally():
    """Import customers from Tally"""
    try:
        tally = TallyIntegration()
        customers_data, message = tally.get_parties_from_tally('customer')
        
        imported_count = 0
        updated_count = 0
        
        for customer_data in customers_data:
            # Check if customer already exists by name or Tally GUID
            existing_customer = Customer.query.filter(
                (Customer.name == customer_data['name']) | 
                (Customer.tally_guid == customer_data['tally_guid'])
            ).first()
            
            if existing_customer:
                # Update existing customer
                existing_customer.phone = customer_data['phone']
                existing_customer.email = customer_data['email']
                existing_customer.address = customer_data['address']
                existing_customer.gst_number = customer_data['gst_number']
                existing_customer.tally_synced = True
                updated_count += 1
            else:
                # Create new customer
                new_customer = Customer(
                    name=customer_data['name'],
                    phone=customer_data['phone'],
                    email=customer_data['email'],
                    address=customer_data['address'],
                    gst_number=customer_data['gst_number'],
                    credit_limit=customer_data.get('credit_limit', 0),
                    tally_synced=True,
                    tally_guid=customer_data['tally_guid']
                )
                db.session.add(new_customer)
                imported_count += 1
        
        db.session.commit()
        
        log_activity('IMPORT_CUSTOMERS', f'Imported {imported_count} customers from Tally')
        flash(f'Successfully imported {imported_count} new customers and updated {updated_count} customers from Tally', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error importing customers: {str(e)}', 'danger')
    
    return redirect(url_for('tally_sync'))

@app.route('/bulk_import_from_tally')
@login_required
def bulk_import_from_tally():
    """Import all data (items, suppliers, customers) from Tally"""
    try:
        tally = TallyIntegration()
        
        # Import items
        items_success, items_message = tally.import_items_from_tally()
        
        # Import suppliers
        suppliers_success, suppliers_message = tally.import_suppliers_from_tally()
        
        # Import customers
        customers_data, customers_message = tally.get_parties_from_tally('customer')
        customers_imported = 0
        customers_updated = 0
        
        for customer_data in customers_data:
            existing_customer = Customer.query.filter(
                (Customer.name == customer_data['name']) | 
                (Customer.tally_guid == customer_data['tally_guid'])
            ).first()
            
            if existing_customer:
                existing_customer.phone = customer_data['phone']
                existing_customer.email = customer_data['email']
                existing_customer.address = customer_data['address']
                existing_customer.gst_number = customer_data['gst_number']
                existing_customer.tally_synced = True
                customers_updated += 1
            else:
                new_customer = Customer(
                    name=customer_data['name'],
                    phone=customer_data['phone'],
                    email=customer_data['email'],
                    address=customer_data['address'],
                    gst_number=customer_data['gst_number'],
                    credit_limit=customer_data.get('credit_limit', 0),
                    tally_synced=True,
                    tally_guid=customer_data['tally_guid']
                )
                db.session.add(new_customer)
                customers_imported += 1
        
        db.session.commit()
        
        log_activity('BULK_IMPORT_TALLY', 'Bulk import from Tally completed')
        flash(f'Bulk import completed! Items: {items_message}, Suppliers: {suppliers_message}, Customers: Imported {customers_imported}, Updated {customers_updated}', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error during bulk import: {str(e)}', 'danger')
    
    return redirect(url_for('tally_sync'))

# ADMINISTRATOR ROUTES

# User Management
@app.route('/admin/users')
@login_required
@admin_required
def admin_users():
    try:
        users = User.query.all()
        return render_template('admin_users.html', users=users)
    except Exception as e:
        flash(f'Error loading users: {str(e)}', 'danger')
        return render_template('admin_users.html', users=[])

@app.route('/admin/add_user', methods=['POST'])
@login_required
@admin_required
def admin_add_user():
    try:
        username = request.form.get('username')
        password = request.form.get('password')
        role = request.form.get('role')
        email = request.form.get('email')
        phone = request.form.get('phone')
        
        if not username or not password:
            flash('Username and password are required', 'warning')
            return redirect(url_for('admin_users'))
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists', 'warning')
            return redirect(url_for('admin_users'))
        
        user = User(
            username=username,
            password=generate_password_hash(password),
            role=role,
            email=email,
            phone=phone
        )
        
        db.session.add(user)
        db.session.commit()
        log_activity('ADD_USER', f'Added user: {username}')
        flash('User added successfully', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error adding user: {str(e)}', 'danger')
    
    return redirect(url_for('admin_users'))

@app.route('/admin/edit_user/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def admin_edit_user(user_id):
    try:
        user = User.query.get(user_id)
        if user:
            user.username = request.form.get('username')
            user.role = request.form.get('role')
            user.email = request.form.get('email')
            user.phone = request.form.get('phone')
            user.is_active = request.form.get('is_active') == 'on'
            
            # Only update password if provided
            new_password = request.form.get('password')
            if new_password:
                user.password = generate_password_hash(new_password)
            
            db.session.commit()
            log_activity('EDIT_USER', f'Edited user: {user.username}')
            flash('User updated successfully', 'success')
        else:
            flash('User not found', 'warning')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating user: {str(e)}', 'danger')
    
    return redirect(url_for('admin_users'))

@app.route('/admin/delete_user/<int:user_id>')
@login_required
@admin_required
def admin_delete_user(user_id):
    try:
        user = User.query.get(user_id)
        if user and user.id != current_user.id:  # Prevent self-deletion
            username = user.username
            db.session.delete(user)
            db.session.commit()
            log_activity('DELETE_USER', f'Deleted user: {username}')
            flash('User deleted successfully', 'success')
        elif user.id == current_user.id:
            flash('You cannot delete your own account', 'warning')
        else:
            flash('User not found', 'warning')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting user: {str(e)}', 'danger')
    
    return redirect(url_for('admin_users'))

# Change Password
@app.route('/change_password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        try:
            current_password = request.form.get('current_password')
            new_password = request.form.get('new_password')
            confirm_password = request.form.get('confirm_password')
            
            if not check_password_hash(current_user.password, current_password):
                flash('Current password is incorrect', 'danger')
                return render_template('change_password.html')
            
            if new_password != confirm_password:
                flash('New passwords do not match', 'danger')
                return render_template('change_password.html')
            
            current_user.password = generate_password_hash(new_password)
            db.session.commit()
            log_activity('CHANGE_PASSWORD', 'User changed password')
            flash('Password changed successfully', 'success')
            return redirect(url_for('dashboard'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error changing password: {str(e)}', 'danger')
    
    return render_template('change_password.html')

# System Logs
@app.route('/admin/logs')
@login_required
@admin_required
def admin_logs():
    try:
        logs = SystemLog.query.order_by(SystemLog.created_date.desc()).limit(100).all()
        return render_template('admin_logs.html', logs=logs)
    except Exception as e:
        flash(f'Error loading logs: {str(e)}', 'danger')
        return render_template('admin_logs.html', logs=[])

# Backup Management
@app.route('/admin/backup')
@login_required
@admin_required
def admin_backup():
    try:
        backups = BackupLog.query.order_by(BackupLog.created_date.desc()).limit(10).all()
        return render_template('admin_backup.html', backups=backups)
    except Exception as e:
        flash(f'Error loading backup page: {str(e)}', 'danger')
        return render_template('admin_backup.html', backups=[])

@app.route('/admin/create_backup')
@login_required
@admin_required
def admin_create_backup():
    try:
        # Create backup directory if not exists
        if not os.path.exists('backups'):
            os.makedirs('backups')
        
        # Copy database file
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f'inventory_backup_{timestamp}.db'
        shutil.copy2('inventory.db', f'backups/{backup_filename}')
        
        # Log backup
        backup_log = BackupLog(
            filename=backup_filename,
            backup_type='manual',
            size=f"{os.path.getsize(f'backups/{backup_filename}') / 1024:.2f} KB",
            status='completed'
        )
        db.session.add(backup_log)
        db.session.commit()
        
        log_activity('CREATE_BACKUP', f'Created backup: {backup_filename}')
        flash('Backup created successfully', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error creating backup: {str(e)}', 'danger')
    
    return redirect(url_for('admin_backup'))

# System Maintenance
@app.route('/admin/maintenance')
@login_required
@admin_required
def admin_maintenance():
    return render_template('admin_maintenance.html')

@app.route('/admin/clear_old_logs')
@login_required
@admin_required
def admin_clear_old_logs():
    try:
        # Delete logs older than 30 days
        cutoff_date = datetime.now() - timedelta(days=30)
        deleted_count = SystemLog.query.filter(SystemLog.created_date < cutoff_date).delete()
        db.session.commit()
        
        log_activity('CLEAR_LOGS', f'Cleared {deleted_count} old logs')
        flash(f'Cleared {deleted_count} old logs', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error clearing logs: {str(e)}', 'danger')
    
    return redirect(url_for('admin_maintenance'))

@app.route('/admin/clear_stock_alerts')
@login_required
@admin_required
def admin_clear_stock_alerts():
    try:
        # Delete resolved stock alerts
        deleted_count = StockAlert.query.filter_by(resolved=True).delete()
        db.session.commit()
        
        log_activity('CLEAR_ALERTS', f'Cleared {deleted_count} resolved stock alerts')
        flash(f'Cleared {deleted_count} resolved stock alerts', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error clearing stock alerts: {str(e)}', 'danger')
    
    return redirect(url_for('admin_maintenance'))

# Initialize database
def init_db():
    with app.app_context():
        try:
            # Create all tables
            db.create_all()
            
            # Create default admin user
            if not User.query.filter_by(username='admin').first():
                admin = User(
                    username='admin',
                    password=generate_password_hash('admin123'),
                    role='admin',
                    email='admin@inventory.com',
                    phone='+91-9876543210'
                )
                db.session.add(admin)
                print("Admin user created")
            
            # Create default employee
            if not Employee.query.first():
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
                print("Default employee created")
            
            # Create sample data if no items exist
            if not Item.query.first():
                print("Creating sample data...")
                # Sample items
                items = [
                    Item(name="Laptop Dell Inspiron", sku="LAP001", category="Electronics", current_stock=10, min_stock_level=2, cost_price=45000, selling_price=55000),
                    Item(name="Wireless Mouse", sku="MOU001", category="Electronics", current_stock=50, min_stock_level=10, cost_price=450, selling_price=899),
                    Item(name="Mechanical Keyboard", sku="KEY001", category="Electronics", current_stock=30, min_stock_level=5, cost_price=1200, selling_price=2499),
                    Item(name="27-inch Monitor", sku="MON001", category="Electronics", current_stock=15, min_stock_level=3, cost_price=15000, selling_price=18999),
                ]
                for item in items:
                    db.session.add(item)
                
                # Sample supplier
                supplier = Supplier(
                    name="Tech Solutions India Pvt. Ltd.", 
                    contact_person="Amit Sharma", 
                    phone="+91-1122334455",
                    email="amit@techsolutions.com",
                    address="Delhi, India",
                    gst_number="07AABCU9603R1ZM"
                )
                db.session.add(supplier)
                
                # Sample customer
                customer = Customer(
                    name="ABC Corporation India", 
                    phone="+91-9988776655", 
                    email="purchase@abccorp.in",
                    address="Bangalore, Karnataka",
                    gst_number="29AABCA1234A1Z5",
                    credit_limit=500000
                )
                db.session.add(customer)

                # Sample user
                user = User(
                    username='manager',
                    password=generate_password_hash('manager123'),
                    role='manager',
                    email='manager@inventory.com',
                    phone='+91-9876543212'
                )
                db.session.add(user)
                
                db.session.commit()
                print("Sample data created")
            
            print("Database initialized successfully!")
        except Exception as e:
            print(f"Error initializing database: {e}")
            import traceback
            traceback.print_exc()
            db.session.rollback()

# Error handlers
@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('500.html'), 500

if __name__ == '__main__':
    # Initialize the database
    print("Initializing database...")
    init_db()
    
    print("Inventory Management System with Indian Rupees is running on http://localhost:5000")
    print("Default Admin Login: admin / admin123")
    print("Default Manager Login: manager / manager123")
    
    # Run the application
    app.run(debug=True, host='0.0.0.0', port=5000)