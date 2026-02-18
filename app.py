from flask import Flask, render_template, redirect, url_for, flash, request, session, jsonify, abort, make_response
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import os
import uuid
from functools import wraps
import csv
import io
from sqlalchemy.exc import OperationalError

from config import Config
from models import db, User, Food, Order, OrderItem, Cart, ServiceRequest, Coupon, Newsletter
from forms import RegistrationForm, LoginForm, FoodForm, CheckoutForm, ProfileForm, ServiceRequestForm, CouponForm, AdminUserForm

# Initialize Flask app
app = Flask(__name__)
app.config.from_object(Config)

# Initialize extensions
db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please login to access this page.'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Helper functions
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def save_image(file):
    """Save uploaded image with unique filename"""
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        # Generate unique filename
        unique_filename = f"{uuid.uuid4().hex}_{filename}"
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        file.save(file_path)
        return unique_filename
    return None

def get_cart_count():
    """Get number of items in user's cart"""
    if current_user.is_authenticated:
        return Cart.query.filter_by(user_id=current_user.id).count()
    return 0

def calculate_cart_total():
    """Calculate total price of items in cart"""
    if current_user.is_authenticated:
        cart_items = Cart.query.filter_by(user_id=current_user.id).all()
        total = 0
        for item in cart_items:
            total += item.food.price * item.quantity
        return total
    return 0

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

# Error handlers
@app.errorhandler(404)
def page_not_found(e):
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('errors/500.html'), 500

# Context processors
@app.context_processor
def utility_processor():
    data = {
        'cart_count': get_cart_count(),
        'cart_total': calculate_cart_total(),
        'now': datetime.utcnow()
    }
    if current_user.is_authenticated and current_user.is_admin:
        data['pending_services_count'] = ServiceRequest.query.filter_by(status='pending').count()
    return data

@app.template_filter('status_badge')
def status_badge_filter(status):
    """Jinja filter to get a Bootstrap badge class for an order status."""
    if status == 'pending':
        return 'primary'
    elif status == 'confirmed':
        return 'info'
    elif status == 'preparing':
        return 'warning'
    elif status == 'delivered':
        return 'success'
    return 'danger' # for 'cancelled'

# Routes - Main Pages
@app.route('/')
def index():
    """Homepage"""
    if current_user.is_authenticated and current_user.is_admin:
        return redirect(url_for('admin_dashboard'))
        
    featured_foods = Food.query.filter_by(is_available=True).limit(8).all()
    categories = db.session.query(Food.category).distinct().all()
    
    # Fetch active coupon
    active_coupon = Coupon.query.filter(
        Coupon.active == True, 
        Coupon.valid_to >= datetime.utcnow()
    ).order_by(Coupon.created_at.desc()).first()
    
    return render_template('index.html', 
                         featured_foods=featured_foods,
                         categories=[cat[0] for cat in categories],
                         active_coupon=active_coupon)

@app.route('/menu')
def menu():
    """Menu page with all food items"""
    page = request.args.get('page', 1, type=int)
    category = request.args.get('category', 'all')
    search_query = request.args.get('search')
    
    query = Food.query.filter_by(is_available=True)
    
    if category != 'all':
        query = query.filter_by(category=category)
    
    if search_query:
        query = query.filter(Food.name.ilike(f'%{search_query}%') | Food.description.ilike(f'%{search_query}%'))
    
    foods = query.paginate(page=page, per_page=app.config['ITEMS_PER_PAGE'])
    
    categories = db.session.query(Food.category).distinct().all()
    
    return render_template('menu.html', 
                         foods=foods,
                         categories=[cat[0] for cat in categories],
                         current_category=category,
                         search_query=search_query)

@app.route('/food/<int:food_id>')
def food_details(food_id):
    """Food details page"""
    food = Food.query.get_or_404(food_id)
    related_foods = Food.query.filter_by(category=food.category, is_available=True)\
                              .filter(Food.id != food_id)\
                              .limit(4).all()
    return render_template('food_details.html', food=food, related_foods=related_foods)

# Authentication routes
@app.route('/register', methods=['GET', 'POST'])
def register():
    """User registration"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    form = RegistrationForm()
    
    if form.validate_on_submit():
        # Check if user exists
        if User.query.filter_by(email=form.email.data).first():
            flash('Email already registered!', 'danger')
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'message': 'Email already registered!'})
            return render_template('auth/register.html', form=form)
        
        # Create new user
        user = User(
            name=form.name.data,
            email=form.email.data,
            phone=form.phone.data,
            password=generate_password_hash(form.password.data)
        )
        
        db.session.add(user)
        db.session.commit()
        
        flash('Registration successful! Please login.', 'success')
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': True, 'message': 'Registration successful! Redirecting to login...'})
        return redirect(url_for('login'))
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        if form.errors:
            # Return the first error found
            error_msg = list(form.errors.values())[0][0]
            return jsonify({'success': False, 'message': error_msg})
        return jsonify({'success': False, 'message': 'Invalid form data'})
    
    return render_template('auth/register.html', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    """User login"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    form = LoginForm()
    
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        
        if user and check_password_hash(user.password, form.password.data):
            login_user(user, remember=form.remember.data)
            flash(f'Welcome back, {user.name}!', 'success')
            
            # Redirect to next page or home
            next_page = request.args.get('next')
            if not next_page:
                # Redirect admins to dashboard, users to home
                redirect_url = url_for('admin_dashboard') if user.is_admin else url_for('index')
            else:
                redirect_url = next_page
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': True, 'redirect': redirect_url})
            return redirect(redirect_url)
        else:
            flash('Invalid email or password!', 'danger')
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'message': 'Invalid email or password!'})
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' and form.errors:
        return jsonify({'success': False, 'message': 'Invalid form data'})
        
    return render_template('auth/login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    """User logout"""
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

# Cart routes
@app.route('/cart')
@login_required
def cart():
    """View shopping cart"""
    cart_items = Cart.query.filter_by(user_id=current_user.id).all()
    subtotal = calculate_cart_total()
    delivery_charge = 50 if subtotal < 200 else 0
    total = subtotal + delivery_charge
    
    # Get random recommended foods (fetching first 4 available items)
    recommended_foods = Food.query.filter_by(is_available=True).limit(4).all()
    
    return render_template('cart.html', 
                         cart_items=cart_items,
                         subtotal=subtotal,
                         delivery_charge=delivery_charge,
                         total=total,
                         recommended_foods=recommended_foods)

@app.route('/add-to-cart/<int:food_id>', methods=['POST'])
def add_to_cart(food_id):
    """Add item to cart"""
    if not current_user.is_authenticated:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'error': 'login_required', 'message': 'Please login to add items to cart'}), 401
        return redirect(url_for('login'))

    food = Food.query.get_or_404(food_id)
    
    if not food.is_available:
        return jsonify({'error': 'Food item not available'}), 400
    
    # Get data from JSON (if available)
    data = request.get_json() if request.is_json else {}
    quantity = int(data.get('quantity', 1))
    instructions = data.get('instructions', '')
    
    # Check if item already in cart
    cart_item = Cart.query.filter_by(user_id=current_user.id, food_id=food_id).first()
    
    if cart_item:
        cart_item.quantity += quantity
        if instructions:
            # Append new instructions if existing ones exist
            if cart_item.special_instructions:
                cart_item.special_instructions += f"; {instructions}"
            else:
                cart_item.special_instructions = instructions
    else:
        cart_item = Cart(user_id=current_user.id, food_id=food_id, quantity=quantity, special_instructions=instructions)
        db.session.add(cart_item)
    
    db.session.commit()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            'success': True,
            'cart_count': get_cart_count(),
            'message': f'{food.name} added to cart!'
        })
    
    flash(f'{food.name} added to cart!', 'success')
    return redirect(url_for('menu'))

@app.route('/update-cart/<int:item_id>', methods=['POST'])
@login_required
def update_cart(item_id):
    """Update cart item quantity"""
    cart_item = Cart.query.get_or_404(item_id)
    
    if cart_item.user_id != current_user.id:
        abort(403)
    
    quantity = request.json.get('quantity', 1)
    
    if quantity < 1:
        db.session.delete(cart_item)
        message = 'Item removed from cart'
    else:
        cart_item.quantity = quantity
        message = 'Cart updated'
    
    db.session.commit()
    
    subtotal = calculate_cart_total()
    delivery_charge = 50 if subtotal < 200 else 0
    total = subtotal + delivery_charge
    
    return jsonify({
        'success': True,
        'message': message,
        'subtotal': subtotal,
        'delivery_charge': delivery_charge,
        'total': total,
        'cart_count': get_cart_count()
    })

@app.route('/remove-from-cart/<int:item_id>', methods=['POST'])
@login_required
def remove_from_cart(item_id):
    """Remove item from cart"""
    cart_item = Cart.query.get_or_404(item_id)
    
    if cart_item.user_id != current_user.id:
        abort(403)
    
    db.session.delete(cart_item)
    db.session.commit()
    
    flash('Item removed from cart', 'info')
    return redirect(url_for('cart'))

# Order routes
@app.route('/checkout', methods=['GET', 'POST'])
@login_required
def checkout():
    """Checkout page"""
    cart_items = Cart.query.filter_by(user_id=current_user.id).all()
    
    if not cart_items:
        flash('Your cart is empty!', 'warning')
        return redirect(url_for('menu'))
    
    form = CheckoutForm()
    
    # Pre-fill form with user data
    if request.method == 'GET':
        form.name.data = current_user.name
        form.phone.data = current_user.phone
        form.location.data = current_user.location
    
    if form.validate_on_submit():
        subtotal = calculate_cart_total()
        delivery_charge = 50 if subtotal < 200 else 0
        total = subtotal + delivery_charge
        
        # Create order
        order = Order(
            order_number=Order.generate_order_number(),
            user_id=current_user.id,
            total_amount=total,
            location=form.location.data,
            phone=form.phone.data,
            payment_method=form.payment_method.data,
            special_instructions=form.special_instructions.data
        )
        
        db.session.add(order)
        
        # Also update the user's default location for future orders
        current_user.location = form.location.data
        db.session.flush()  # Get order.id
        
        # Add order items
        for cart_item in cart_items:
            order_item = OrderItem(
                order_id=order.id,
                food_id=cart_item.food_id,
                quantity=cart_item.quantity,
                price=cart_item.food.price,
                special_instructions=cart_item.special_instructions
            )
            db.session.add(order_item)
        
        # Clear cart
        for cart_item in cart_items:
            db.session.delete(cart_item)
        
        db.session.commit()
        
        flash('Order placed successfully!', 'success')
        return redirect(url_for('order_success', order_id=order.id))
    
    subtotal = calculate_cart_total()
    delivery_charge = 50 if subtotal < 200 else 0
    total = subtotal + delivery_charge
    
    return render_template('checkout.html',
                         form=form,
                         cart_items=cart_items,
                         subtotal=subtotal,
                         delivery_charge=delivery_charge,
                         total=total)

@app.route('/order-success/<int:order_id>')
@login_required
def order_success(order_id):
    """Order confirmation page"""
    order = Order.query.get_or_404(order_id)
    
    if order.user_id != current_user.id and not current_user.is_admin:
        abort(403)
    
    return render_template('order_success.html', order=order)

@app.route('/my-orders')
@login_required
def my_orders():
    """User order history"""
    page = request.args.get('page', 1, type=int)
    orders = Order.query.filter_by(user_id=current_user.id)\
                       .order_by(Order.created_at.desc())\
                       .paginate(page=page, per_page=10)
    return render_template('orders.html', orders=orders)

@app.route('/order/<int:order_id>')
@login_required
def order_details(order_id):
    """View order details"""
    order = Order.query.get_or_404(order_id)
    
    if order.user_id != current_user.id and not current_user.is_admin:
        abort(403)
    
    return render_template('order_details.html', order=order)

@app.route('/cancel-order/<int:order_id>', methods=['POST'])
@login_required
def cancel_order(order_id):
    """Cancel an order"""
    order = Order.query.get_or_404(order_id)
    
    if order.user_id != current_user.id:
        abort(403)
    
    if order.status not in ['pending', 'confirmed']:
        flash('Order cannot be cancelled at this stage', 'danger')
        return redirect(url_for('order_details', order_id=order_id))
    
    order.status = 'cancelled'
    db.session.commit()
    
    flash('Order cancelled successfully', 'success')
    return redirect(url_for('my_orders'))

# Service Routes
@app.route('/services', methods=['GET', 'POST'])
@login_required
def services():
    """Guest services page"""
    form = ServiceRequestForm()
    
    if form.validate_on_submit():
        service_request = ServiceRequest(
            user_id=current_user.id,
            service_type=form.service_type.data,
            description=form.description.data
        )
        db.session.add(service_request)
        db.session.commit()
        
        flash('Service request submitted successfully! Our staff will attend to you shortly.', 'success')
        return redirect(url_for('services'))
    
    # Get history
    requests = ServiceRequest.query.filter_by(user_id=current_user.id)\
                                 .order_by(ServiceRequest.created_at.desc()).all()
    
    return render_template('services.html', form=form, requests=requests)

# Profile routes
@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """User profile page"""
    form = ProfileForm()
    
    if form.validate_on_submit():
        current_user.name = form.name.data
        current_user.phone = form.phone.data
        current_user.location = form.location.data
        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('profile'))
    
    # Pre-fill form
    if request.method == 'GET':
        form.name.data = current_user.name
        form.phone.data = current_user.phone
        form.location.data = current_user.location
    
    # Fetch stats
    base_query = Order.query.filter_by(user_id=current_user.id)
    total_orders_count = base_query.count()
    total_spent = db.session.query(db.func.sum(Order.total_amount)).filter_by(user_id=current_user.id).scalar() or 0
    
    # Pagination for order history
    page = request.args.get('page', 1, type=int)
    orders = base_query.order_by(Order.created_at.desc())\
                       .paginate(page=page, per_page=5)
    
    return render_template('auth/profile.html', 
                         form=form, 
                         orders=orders,
                         total_orders_count=total_orders_count,
                         total_spent=total_spent)

# Admin routes
@app.route('/admin')
@login_required
@admin_required
def admin_dashboard():
    """Admin dashboard"""
    
    total_users = User.query.count()
    total_orders = Order.query.count()
    total_foods = Food.query.count()
    pending_orders = Order.query.filter_by(status='pending').count()
    
    # Sales Chart Data
    end_date_str = request.args.get('end_date')
    start_date_str = request.args.get('start_date')
    
    today = datetime.utcnow().date()
    
    if end_date_str and start_date_str:
        try:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        except ValueError:
            end_date = today
            start_date = end_date - timedelta(days=6)
    else:
        end_date = today
        start_date = end_date - timedelta(days=6)
        
    # Ensure start_date is not after end_date
    if start_date > end_date:
        start_date = end_date - timedelta(days=6)

    dates = []
    sales = []
    
    delta = (end_date - start_date).days
    for i in range(delta + 1):
        date = start_date + timedelta(days=i)
        dates.append(date.strftime('%b %d'))
        
        day_start = datetime.combine(date, datetime.min.time())
        day_end = datetime.combine(date, datetime.max.time())
        
        daily_total = db.session.query(db.func.sum(Order.total_amount))\
            .filter(Order.created_at >= day_start)\
            .filter(Order.created_at <= day_end)\
            .filter(Order.status != 'cancelled')\
            .scalar() or 0
            
        sales.append(float(daily_total))
    
    # Order Status Distribution
    status_counts = dict(db.session.query(Order.status, db.func.count(Order.id)).group_by(Order.status).all())
    
    # Define a consistent order and color for statuses
    status_config = {
        'pending': {'label': 'Pending', 'color': '#0d6efd'},
        'confirmed': {'label': 'Confirmed', 'color': '#0dcaf0'},
        'preparing': {'label': 'Preparing', 'color': '#ffc107'},
        'delivered': {'label': 'Delivered', 'color': '#198754'},
        'cancelled': {'label': 'Cancelled', 'color': '#dc3545'}
    }

    status_labels = [v['label'] for k, v in status_config.items()]
    status_data = [status_counts.get(k, 0) for k in status_config.keys()]
    status_colors = [v['color'] for k, v in status_config.items()]
    
    recent_orders = Order.query.order_by(Order.created_at.desc()).limit(10).all()
    
    return render_template('admin/dashboard.html',
                         total_users=total_users,
                         total_orders=total_orders,
                         total_foods=total_foods,
                         pending_orders=pending_orders,
                         recent_orders=recent_orders,
                         dates=dates,
                         sales=sales,
                         status_labels=status_labels,
                         status_data=status_data,
                         status_colors=status_colors,
                         start_date=start_date.strftime('%Y-%m-%d'),
                         end_date=end_date.strftime('%Y-%m-%d'))

@app.route('/admin/foods')
@login_required
@admin_required
def manage_foods():
    """Manage food items"""
    
    page = request.args.get('page', 1, type=int)
    foods = Food.query.order_by(Food.created_at.desc())\
                     .paginate(page=page, per_page=20)
    
    return render_template('admin/manage_food.html', foods=foods)

@app.route('/admin/foods/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_food():
    """Add new food item"""
    
    form = FoodForm()
    
    if form.validate_on_submit():
        image_filename = 'default-food.jpg'
        
        if form.image.data:
            saved_image = save_image(form.image.data)
            if saved_image:
                image_filename = saved_image
        
        food = Food(
            name=form.name.data,
            category=form.category.data,
            price=form.price.data,
            description=form.description.data,
            image=image_filename,
            is_available=form.is_available.data
        )
        
        db.session.add(food)
        db.session.commit()
        
        flash('Food item added successfully!', 'success')
        return redirect(url_for('manage_foods'))
    
    return render_template('admin/add_food.html', form=form)

@app.route('/admin/foods/edit/<int:food_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_food(food_id):
    """Edit food item"""
    
    food = Food.query.get_or_404(food_id)
    form = FoodForm(obj=food)
    
    if form.validate_on_submit():
        food.name = form.name.data
        food.category = form.category.data
        food.price = form.price.data
        food.description = form.description.data
        food.is_available = form.is_available.data
        
        if form.image.data:
            saved_image = save_image(form.image.data)
            if saved_image:
                # Delete old image if not default
                if food.image != 'default-food.jpg':
                    old_image_path = os.path.join(app.config['UPLOAD_FOLDER'], food.image)
                    if os.path.exists(old_image_path):
                        os.remove(old_image_path)
                food.image = saved_image
        
        db.session.commit()
        flash('Food item updated successfully!', 'success')
        return redirect(url_for('manage_foods'))
    
    return render_template('admin/edit_food.html', form=form, food=food)

@app.route('/admin/foods/delete/<int:food_id>', methods=['POST'])
@login_required
@admin_required
def delete_food(food_id):
    """Delete food item"""
    
    food = Food.query.get_or_404(food_id)
    
    # Delete image if not default
    if food.image != 'default-food.jpg':
        image_path = os.path.join(app.config['UPLOAD_FOLDER'], food.image)
        if os.path.exists(image_path):
            os.remove(image_path)
    
    db.session.delete(food)
    db.session.commit()
    
    flash('Food item deleted successfully!', 'success')
    return redirect(url_for('manage_foods'))

@app.route('/admin/orders')
@login_required
@admin_required
def admin_orders():
    """View all orders"""
    
    status = request.args.get('status', 'all')
    page = request.args.get('page', 1, type=int)
    search_query = request.args.get('q', '')
    
    query = Order.query
    
    if status != 'all':
        query = query.filter_by(status=status)
    
    if search_query:
        query = query.filter(Order.order_number.ilike(f'%{search_query}%'))
    
    orders = query.order_by(Order.created_at.desc())\
                 .paginate(page=page, per_page=20)
    
    return render_template('admin/view_orders.html', 
                         orders=orders, 
                         current_status=status)

@app.route('/admin/orders/update/<int:order_id>', methods=['POST'])
@login_required
@admin_required
def update_order_status(order_id):
    """Update order status"""
    
    order = Order.query.get_or_404(order_id)
    new_status = request.json.get('status')
    
    if new_status in ['pending', 'confirmed', 'preparing', 'delivered', 'cancelled']:
        order.status = new_status
        db.session.commit()
        return jsonify({'success': True})
    
    return jsonify({'success': False}), 400

@app.route('/admin/orders/print/<int:order_id>')
@login_required
@admin_required
def print_receipt(order_id):
    """Print order receipt"""
    order = Order.query.get_or_404(order_id)
    return render_template('admin/print_receipt.html', order=order)

@app.route('/admin/users')
@login_required
@admin_required
def admin_users():
    """View all users"""
    
    page = request.args.get('page', 1, type=int)
    search_query = request.args.get('q', '')
    
    query = User.query
    
    if search_query:
        query = query.filter(
            (User.name.ilike(f'%{search_query}%')) | 
            (User.email.ilike(f'%{search_query}%'))
        )
    
    users = query.order_by(User.created_at.desc())\
                     .paginate(page=page, per_page=20)
    
    return render_template('admin/users.html', users=users)

@app.route('/admin/users/edit/<int:user_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_user(user_id):
    """Edit user details"""
    user = User.query.get_or_404(user_id)
    form = AdminUserForm(obj=user)
    
    if form.validate_on_submit():
        # Check if email is taken by another user
        existing_user = User.query.filter_by(email=form.email.data).first()
        if existing_user and existing_user.id != user.id:
            flash('Email already registered by another user!', 'danger')
            return render_template('admin/edit_user.html', form=form, user=user)
            
        user.name = form.name.data
        user.email = form.email.data
        user.phone = form.phone.data
        user.location = form.location.data
        
        # Prevent self-demotion
        if user.id == current_user.id and not form.is_admin.data:
            flash('You cannot remove your own admin privileges.', 'warning')
            user.is_admin = True
        else:
            user.is_admin = form.is_admin.data
            
        db.session.commit()
        flash('User updated successfully!', 'success')
        return redirect(url_for('admin_users'))
        
    return render_template('admin/edit_user.html', form=form, user=user)

@app.route('/admin/users/delete/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):
    """Delete a user"""
    user = User.query.get_or_404(user_id)
    
    if user.id == current_user.id:
        flash('You cannot delete your own account!', 'danger')
        return redirect(url_for('admin_users'))
    
    # Delete related data to avoid foreign key constraints
    Cart.query.filter_by(user_id=user.id).delete()
    ServiceRequest.query.filter_by(user_id=user.id).delete()
    
    # Delete orders (will cascade to order items if configured, but doing explicitly for safety)
    orders = Order.query.filter_by(user_id=user.id).all()
    for order in orders:
        db.session.delete(order)
        
    db.session.delete(user)
    db.session.commit()
    
    flash('User and all associated data deleted successfully!', 'success')
    return redirect(url_for('admin_users'))

@app.route('/admin/services')
@login_required
@admin_required
def admin_services():
    """Manage service requests"""
    page = request.args.get('page', 1, type=int)
    status = request.args.get('status', 'all')
    
    query = ServiceRequest.query
    if status != 'all':
        query = query.filter_by(status=status)
        
    requests = query.order_by(ServiceRequest.created_at.desc())\
                    .paginate(page=page, per_page=20)
    
    return render_template('admin/services.html', requests=requests, current_status=status)

@app.route('/admin/services/update/<int:request_id>', methods=['POST'])
@login_required
@admin_required
def update_service_status(request_id):
    """Update service request status"""
    req = ServiceRequest.query.get_or_404(request_id)
    new_status = request.json.get('status')
    
    if new_status in ['pending', 'in_progress', 'completed', 'cancelled']:
        req.status = new_status
        db.session.commit()
        return jsonify({'success': True})
    return jsonify({'success': False}), 400

@app.route('/admin/kds')
@login_required
@admin_required
def kds():
    """Kitchen Display System"""
    return render_template('admin/kds.html')

@app.route('/api/kds/orders')
@login_required
@admin_required
def get_kds_orders():
    """Get active orders for KDS"""
    orders = Order.query.filter(Order.status.in_(['confirmed', 'preparing']))\
                       .order_by(Order.created_at.asc()).all()
    
    orders_data = []
    for order in orders:
        items = []
        for item in order.items:
            items.append({
                'name': item.food_item.name,
                'quantity': item.quantity,
                'special_instructions': item.special_instructions
            })
            
        orders_data.append({
            'id': order.id,
            'order_number': order.order_number,
            'customer': order.customer.name,
            'location': order.location,
            'status': order.status,
            'created_at': order.created_at.isoformat(),
            'items': items,
            'special_instructions': order.special_instructions
        })
        
    return jsonify(orders_data)

@app.route('/admin/export-sales')
@login_required
@admin_required
def export_sales():
    """Export sales data to CSV"""
    end_date_str = request.args.get('end_date')
    start_date_str = request.args.get('start_date')
    
    today = datetime.utcnow().date()
    
    if end_date_str and start_date_str:
        try:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        except ValueError:
            end_date = today
            start_date = end_date - timedelta(days=6)
    else:
        end_date = today
        start_date = end_date - timedelta(days=6)
    
    # Query orders
    day_start = datetime.combine(start_date, datetime.min.time())
    day_end = datetime.combine(end_date, datetime.max.time())
    
    orders = Order.query.filter(Order.created_at >= day_start)\
                        .filter(Order.created_at <= day_end)\
                        .filter(Order.status != 'cancelled')\
                        .order_by(Order.created_at.desc()).all()
    
    # Generate CSV
    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(['Order ID', 'Date', 'Customer', 'Items', 'Total Amount', 'Status', 'Payment Method'])
    
    for order in orders:
        items_str = ", ".join([f"{item.food_item.name} x{item.quantity}" for item in order.items])
        cw.writerow([
            order.order_number,
            order.created_at.strftime('%Y-%m-%d %H:%M'),
            order.customer.name,
            items_str,
            order.total_amount,
            order.status,
            order.payment_method
        ])
        
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = f"attachment; filename=sales_report_{start_date}_{end_date}.csv"
    output.headers["Content-type"] = "text/csv"
    return output

@app.route('/api/admin/notifications')
@login_required
@admin_required
def admin_notifications():
    """Get notification counts for admin"""
    services_count = ServiceRequest.query.filter_by(status='pending').count()
    return jsonify({'services': services_count})

# Coupon Routes
@app.route('/admin/coupons')
@login_required
@admin_required
def manage_coupons():
    """Manage coupons"""
    coupons = Coupon.query.order_by(Coupon.created_at.desc()).all()
    return render_template('admin/manage_coupons.html', coupons=coupons)

@app.route('/admin/coupons/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_coupon():
    """Add new coupon"""
    form = CouponForm()
    if form.validate_on_submit():
        coupon = Coupon(
            code=form.code.data.upper(),
            discount_type=form.discount_type.data,
            value=form.value.data,
            valid_to=datetime.combine(form.valid_to.data, datetime.max.time()),
            usage_limit=form.usage_limit.data,
            active=form.active.data
        )
        db.session.add(coupon)
        db.session.commit()
        flash('Coupon created successfully!', 'success')
        return redirect(url_for('manage_coupons'))
    return render_template('admin/add_coupon.html', form=form)

@app.route('/admin/coupons/delete/<int:coupon_id>', methods=['POST'])
@login_required
@admin_required
def delete_coupon(coupon_id):
    """Delete coupon"""
    coupon = Coupon.query.get_or_404(coupon_id)
    db.session.delete(coupon)
    db.session.commit()
    flash('Coupon deleted successfully!', 'success')
    return redirect(url_for('manage_coupons'))

@app.route('/admin/coupons/delete-expired', methods=['POST'])
@login_required
@admin_required
def delete_expired_coupons():
    """Delete all expired coupons"""
    now = datetime.utcnow()
    expired_coupons = Coupon.query.filter(Coupon.valid_to < now).all()
    count = len(expired_coupons)
    for coupon in expired_coupons:
        db.session.delete(coupon)
    db.session.commit()
    flash(f'{count} expired coupons deleted successfully!', 'success')
    return redirect(url_for('manage_coupons'))

@app.route('/subscribe', methods=['POST'])
def subscribe():
    """Newsletter subscription"""
    email = request.form.get('email')
    
    if not email:
        return jsonify({'success': False, 'message': 'Email is required'})
    
    # Check if already subscribed
    existing = Newsletter.query.filter_by(email=email).first()
    if existing:
        return jsonify({'success': False, 'message': 'You are already subscribed!'})
        
    new_sub = Newsletter(email=email)
    db.session.add(new_sub)
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Successfully subscribed!'})

@app.route('/admin/newsletter')
@login_required
@admin_required
def admin_newsletter():
    """Manage newsletter subscribers"""
    page = request.args.get('page', 1, type=int)
    subscribers = Newsletter.query.order_by(Newsletter.created_at.desc())\
                                .paginate(page=page, per_page=20)
    return render_template('admin/newsletter.html', subscribers=subscribers)

@app.route('/admin/newsletter/export')
@login_required
@admin_required
def export_newsletter():
    """Export newsletter subscribers to CSV"""
    subscribers = Newsletter.query.order_by(Newsletter.created_at.desc()).all()
    
    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(['ID', 'Email', 'Subscribed Date'])
    
    for sub in subscribers:
        cw.writerow([sub.id, sub.email, sub.created_at.strftime('%Y-%m-%d %H:%M')])
        
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = "attachment; filename=subscribers.csv"
    output.headers["Content-type"] = "text/csv"
    return output

@app.route('/admin/newsletter/delete/<int:id>', methods=['POST'])
@login_required
@admin_required
def delete_subscriber(id):
    """Delete newsletter subscriber"""
    sub = Newsletter.query.get_or_404(id)
    db.session.delete(sub)
    db.session.commit()
    flash('Subscriber removed successfully!', 'success')
    return redirect(url_for('admin_newsletter'))

# API endpoints
@app.route('/api/foods')
def api_foods():
    """API endpoint for foods"""
    foods = Food.query.filter_by(is_available=True).all()
    return jsonify([{
        'id': f.id,
        'name': f.name,
        'category': f.category,
        'price': f.price,
        'description': f.description,
        'image': f.image
    } for f in foods])

@app.route('/api/search')
def api_search():
    """Search foods API"""
    query = request.args.get('q', '')
    if len(query) < 2:
        return jsonify([])
    
    foods = Food.query.filter(
        Food.name.ilike(f'%{query}%') | Food.description.ilike(f'%{query}%'),
        Food.is_available == True
    ).limit(10).all()
    
    return jsonify([{
        'id': f.id,
        'name': f.name,
        'category': f.category,
        'price': f.price,
        'image': f.image
    } for f in foods])

# Create tables
with app.app_context():
    # Ensure upload directory exists
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    
    db.create_all()
    
    # Create admin user if not exists
    try:
        admin = User.query.filter_by(email='admin@foodapp.com').first()
    except OperationalError:
        # If schema has changed (e.g. missing columns), recreate DB
        print("Database schema mismatch detected. Recreating database...")
        db.drop_all()
        db.create_all()
        admin = None
        
    if not admin:
        admin = User(
            name='Admin',
            email='admin@foodapp.com',
            password=generate_password_hash('admin123'),
            phone='1234567890',
            location='Front Desk',
            is_admin=True
        )
        db.session.add(admin)
        db.session.commit()
        print("Admin user created (email: admin@foodapp.com, pass: admin123)")
    else:
        # Ensure existing admin has correct privileges
        if not admin.is_admin:
            admin.is_admin = True
            db.session.commit()

    # Seed food items if empty
    if Food.query.count() == 0:
        print("Seeding database with sample food items...")
        sample_foods = [
            Food(
                name='Club Sandwich', 
                category='sandwich', 
                price=450.0, 
                description='Triple-decker sandwich with chicken, bacon, lettuce, tomato, and mayo. Served with fries.', 
                image='default-food.jpg', 
                is_available=True
            ),
            Food(
                name='Caesar Salad', 
                category='starters', 
                price=350.0, 
                description='Crisp romaine lettuce, parmesan cheese, croutons, and caesar dressing.', 
                image='default-food.jpg', 
                is_available=True
            ),
            Food(
                name='Grilled Salmon', 
                category='main-course', 
                price=850.0, 
                description='Fresh Atlantic salmon grilled to perfection, served with asparagus and lemon butter sauce.', 
                image='default-food.jpg', 
                is_available=True
            ),
            Food(
                name='Butter Chicken', 
                category='main-course', 
                price=650.0, 
                description='Tender chicken cooked in a rich tomato and butter gravy. Served with naan.', 
                image='default-food.jpg', 
                is_available=True
            ),
            Food(
                name='Continental Breakfast', 
                category='breakfast', 
                price=550.0, 
                description='Assorted pastries, toast, butter, jam, fresh fruit, and coffee or tea.', 
                image='default-food.jpg', 
                is_available=True
            ),
            Food(
                name='Cappuccino', 
                category='beverages', 
                price=250.0, 
                description='Freshly brewed espresso with steamed milk and foam.', 
                image='default-food.jpg', 
                is_available=True
            )
        ]
        
        for food in sample_foods:
            db.session.add(food)
        
        db.session.commit()
        print("Sample food items added successfully.")

if __name__ == '__main__':
    app.run(debug=True)

    #Email (ID): admin@foodapp.com
    #Password: admin123
    #patilparshwa67@gmail.com
    #123456Qw@