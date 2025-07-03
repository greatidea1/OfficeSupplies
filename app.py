# Main Flask Application - Office Supplies Vendor System
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_file
from flask_cors import CORS
from werkzeug.utils import secure_filename
import os
from datetime import datetime, timedelta
import uuid
import mimetypes

# Import controllers
from controllers.auth_controller import auth_controller
from controllers.vendor_controller import vendor_controller
from controllers.product_controller import product_controller
from controllers.order_controller import order_controller
from controllers.customer_controller import customer_controller
from controllers.user_controller import user_controller
from controllers.department_controller import department_controller

# Import models
from models import User, Customer, Product, Order, VendorSettings
from config import config

def create_app():
    """Create and configure Flask application"""
    app = Flask(__name__)
    
    # Configure app
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
    app.config['UPLOAD_FOLDER'] = 'uploads'
    
    # Enable CORS for API endpoints
    CORS(app, resources={r"/api/*": {"origins": "*"}})
    
    # Create upload directory if it doesn't exist
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    
    # Initialize configuration
    config.init_app(app)
    
    # Template filters
    @app.template_filter('datetime')
    def datetime_filter(value):
        """Format datetime for templates"""
        if value:
            return value.strftime('%Y-%m-%d %H:%M:%S')
        return ''
    
    @app.template_filter('currency')
    def currency_filter(value):
        """Format currency for templates"""
        try:
            return f"₹{float(value):,.2f}"
        except (ValueError, TypeError):
            return "₹0.00"
    
    # Authentication decorator
    def login_required(f):
        """Decorator to require authentication"""
        from functools import wraps
        @wraps(f)
        def decorated_function(*args, **kwargs):
            current_user = auth_controller.get_current_user()
            if not current_user:
                if request.path.startswith('/api/'):
                    return jsonify({'success': False, 'message': 'Authentication required'}), 401
                return redirect(url_for('login'))
            return f(*args, **kwargs)
        return decorated_function
    
    def role_required(*allowed_roles):
        """Decorator to require specific roles"""
        def decorator(f):
            from functools import wraps
            @wraps(f)
            def decorated_function(*args, **kwargs):
                current_user = auth_controller.get_current_user()
                if not current_user or current_user.role not in allowed_roles:
                    if request.path.startswith('/api/'):
                        return jsonify({'success': False, 'message': 'Insufficient permissions'}), 403
                    return redirect(url_for('dashboard'))
                return f(*args, **kwargs)
            return decorated_function
        return decorator
    
    # Context processor to inject current user
    @app.context_processor
    def inject_user():
        """Inject current user into all templates"""
        current_user = auth_controller.get_current_user()
        return dict(current_user=current_user)
    
    # Error handlers
    @app.errorhandler(404)
    def not_found_error(error):
        """Handle 404 errors"""
        if request.path.startswith('/api/'):
            return jsonify({'success': False, 'message': 'Resource not found'}), 404
        return render_template('errors/404.html'), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        """Handle 500 errors"""
        if request.path.startswith('/api/'):
            return jsonify({'success': False, 'message': 'Internal server error'}), 500
        return render_template('errors/500.html'), 500
    
    @app.errorhandler(413)
    def too_large(error):
        """Handle file too large errors"""
        return jsonify({'success': False, 'message': 'File too large. Maximum size is 16MB.'}), 413
    
    # ================== PUBLIC ROUTES ==================
    
    @app.route('/')
    def index():
        """Landing page"""
        current_user = auth_controller.get_current_user()
        if current_user:
            return redirect(url_for('dashboard'))
        return render_template('index.html')
    
    @app.route('/login')
    def login():
        """Login page"""
        current_user = auth_controller.get_current_user()
        if current_user:
            return redirect(url_for('dashboard'))
        return render_template('auth/login.html')
    
    @app.route('/vendor-login')
    def vendor_login():
        """Vendor login page"""
        current_user = auth_controller.get_current_user()
        if current_user:
            return redirect(url_for('dashboard'))
        return render_template('auth/vendor_login.html')
    
    # ================== AUTH API ROUTES ==================
    
    @app.route('/api/auth/login', methods=['POST'])
    def api_login():
        """API: User login - FIXED VERSION"""
        try:
            print(f"Login request received: {request.method} {request.path}")
            print(f"Content-Type: {request.content_type}")
            
            # Get JSON data
            try:
                data = request.get_json()
                #print(f"Request data: {data}")
            except Exception as e:
                print(f"Error parsing JSON: {e}")
                return jsonify({'success': False, 'message': 'Invalid JSON data'}), 400
            
            if not data:
                return jsonify({'success': False, 'message': 'No data provided'}), 400
            
            user_type = data.get('user_type', 'customer')
            print(f"User type: {user_type}")
            
            if user_type == 'customer':
                # Customer login requires customer_id + email + password
                customer_id = data.get('customer_id')
                email = data.get('email')
                password = data.get('password')
                
                print(f"Customer login attempt: customer_id={customer_id}, email={email}")
                
                if not customer_id or not email or not password:
                    return jsonify({'success': False, 'message': 'Customer ID, email and password required'}), 400
                
                result = auth_controller.login(email, password, user_type, customer_id)
            else:
                # Vendor login uses username + password
                username = data.get('username')
                password = data.get('password')
                
                print(f"Vendor login attempt: username={username}")
                
                if not username or not password:
                    return jsonify({'success': False, 'message': 'Username and password required'}), 400
                
                result = auth_controller.login(username, password, user_type)
            
            print(f"Login result: {result}")
            
            if result.get('success'):
                return jsonify(result), 200
            else:
                return jsonify(result), 401
                
        except Exception as e:
            print(f"Login API error: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'success': False, 'message': 'Internal server error'}), 500
    
    @app.route('/api/auth/logout', methods=['POST'])
    def api_logout():
        """API: User logout"""
        result = auth_controller.logout()
        return jsonify(result)
    
    @app.route('/api/auth/change-password', methods=['PUT'])
    @login_required
    def api_change_password():
        """API: Change user password"""
        try:
            data = request.get_json()
            current_password = data.get('current_password')
            new_password = data.get('new_password')
            
            if not current_password or not new_password:
                return jsonify({'success': False, 'message': 'Current and new passwords required'})
            
            result = auth_controller.change_password(current_password, new_password)
            return jsonify(result)
            
        except Exception as e:
            print(f"Change password error: {e}")
            return jsonify({'success': False, 'message': 'Failed to change password'})
    
    # ================== DASHBOARD ROUTES ==================
    
    @app.route('/dashboard')
    @login_required
    def dashboard():
        """Main dashboard - redirects based on user role"""
        current_user = auth_controller.get_current_user()
        
        if current_user.role in ['vendor_superadmin', 'vendor_admin', 'vendor_normal']:
            return render_template('dashboards/vendor_dashboard.html')
        elif current_user.role == 'customer_hr_admin':
            return render_template('dashboards/customer_hr_dashboard.html')
        elif current_user.role == 'customer_dept_head':
            return render_template('dashboards/customer_dept_dashboard.html')
        elif current_user.role == 'customer_employee':
            return render_template('dashboards/customer_employee_dashboard.html')
        else:
            return render_template('errors/403.html'), 403
    
    @app.route('/api/dashboard/<dashboard_type>')
    @login_required
    def api_dashboard_data(dashboard_type):
        """API: Get dashboard data"""
        if dashboard_type == 'vendor':
            return jsonify(vendor_controller.get_dashboard_statistics())
        elif dashboard_type == 'customer':
            return jsonify(customer_controller.get_dashboard_statistics())
        elif dashboard_type == 'employee':
            return jsonify(customer_controller.get_employee_dashboard_statistics())
        else:
            return jsonify({'success': False, 'message': 'Invalid dashboard type'})
    
    @app.route('/api/dashboard/recent-activity')
    @login_required
    def api_recent_activity():
        """API: Get recent user activity"""
        # Implementation depends on activity logging system
        return jsonify({
            'success': True,
            'activities': []  # Placeholder
        })
    
    # ================== CUSTOMER ROUTES ==================
    
    @app.route('/customers')
    @login_required
    @role_required('vendor_superadmin', 'vendor_admin')
    def customers():
        """Customer management page"""
        return render_template('customers.html')
    
    @app.route('/api/customers')
    @login_required
    def api_customers():
        """API: Get customers list"""
        if request.method == 'GET':
            return jsonify(customer_controller.get_customers())
        elif request.method == 'POST':
            return jsonify(customer_controller.create_customer())
    
    @app.route('/api/customers', methods=['POST'])
    @login_required
    @role_required('vendor_superadmin')
    def api_create_customer():
        """API: Create new customer"""
        return jsonify(customer_controller.create_customer())
    
    @app.route('/api/customers/<customer_id>')
    @login_required
    def api_customer_details(customer_id):
        """API: Get customer details"""
        return jsonify(customer_controller.get_customer(customer_id))
    
    @app.route('/api/customers/<customer_id>/statistics')
    @login_required
    def api_customer_statistics(customer_id):
        """API: Get customer statistics"""
        return jsonify(customer_controller.get_customer_statistics(customer_id))
    
    # ================== PRODUCT ROUTES ==================
    
    @app.route('/products')
    @login_required
    def products():
        """Products page"""
        current_user = auth_controller.get_current_user()
        if current_user.role in ['vendor_superadmin', 'vendor_admin', 'vendor_normal']:
            return render_template('vendor/products.html')
        else:
            return render_template('customer/products.html')
    
    @app.route('/api/products')
    @login_required
    def api_products():
        """API: Get products list"""
        return jsonify(product_controller.get_products())
    
    @app.route('/api/products', methods=['POST'])
    @login_required
    @role_required('vendor_superadmin', 'vendor_admin', 'vendor_normal')
    def api_create_product():
        """API: Create new product"""
        return jsonify(product_controller.create_product())
    
    @app.route('/api/products/<product_id>')
    @login_required
    def api_product_details(product_id):
        """API: Get product details"""
        return jsonify(product_controller.get_product(product_id))
    
    @app.route('/api/products/<product_id>', methods=['PUT'])
    @login_required
    @role_required('vendor_superadmin', 'vendor_admin', 'vendor_normal')
    def api_update_product(product_id):
        """API: Update product"""
        return jsonify(product_controller.update_product(product_id))
    
    # ================== DEPARTMENT ROUTES ==================

    @app.route('/departments')
    @login_required
    @role_required('customer_hr_admin')
    def departments():
        """Departments management page (HR Admin only)"""
        return render_template('departments.html')

    @app.route('/api/departments')
    @login_required
    def api_departments():
        """API: Get departments list"""
        return jsonify(department_controller.get_departments())

    @app.route('/api/departments', methods=['POST'])
    @login_required
    @role_required('customer_hr_admin')
    def api_create_department():
        """API: Create new department"""
        return jsonify(department_controller.create_department())

    @app.route('/api/departments/<department_id>')
    @login_required
    def api_department_details(department_id):
        """API: Get department details"""
        return jsonify(department_controller.get_department(department_id))

    @app.route('/api/departments/<department_id>', methods=['PUT'])
    @login_required
    @role_required('customer_hr_admin')
    def api_update_department(department_id):
        """API: Update department"""
        return jsonify(department_controller.update_department(department_id))

    @app.route('/api/departments/<department_id>', methods=['DELETE'])
    @login_required
    @role_required('customer_hr_admin')
    def api_delete_department(department_id):
        """API: Delete department"""
        return jsonify(department_controller.delete_department(department_id))
    
    @app.route('/api/departments/<department_id>/assign-head', methods=['PUT'])
    @login_required
    @role_required('customer_hr_admin')
    def api_assign_department_head(department_id):
        """API: Assign department head"""
        return jsonify(department_controller.assign_department_head(department_id))
    
    # ================== ORDER ROUTES ==================
    
    @app.route('/orders')
    @login_required
    def orders():
        """Orders page"""
        return render_template('orders.html')
    
    @app.route('/api/orders')
    @login_required
    def api_orders():
        """API: Get orders list"""
        return jsonify(order_controller.get_orders())
    
    @app.route('/api/orders', methods=['POST'])
    @login_required
    @role_required('customer_employee')
    def api_create_order():
        """API: Create new order"""
        return jsonify(order_controller.create_order())
    
    @app.route('/api/orders/<order_id>')
    @login_required
    def api_order_details(order_id):
        """API: Get order details"""
        return jsonify(order_controller.get_order(order_id))
    
    @app.route('/api/orders/<order_id>/dept-approval', methods=['PUT'])
    @login_required
    @role_required('customer_dept_head')
    def api_dept_approval(order_id):
        """API: Department head approval"""
        return jsonify(order_controller.process_dept_approval(order_id))
    
    @app.route('/api/orders/<order_id>/hr-approval', methods=['PUT'])
    @login_required
    @role_required('customer_hr_admin')
    def api_hr_approval(order_id):
        """API: HR admin approval"""
        return jsonify(order_controller.process_hr_approval(order_id))
    
    @app.route('/api/orders/<order_id>/pack', methods=['PUT'])
    @login_required
    @role_required('vendor_superadmin', 'vendor_admin', 'vendor_normal')
    def api_pack_order(order_id):
        """API: Mark order items as packed"""
        return jsonify(order_controller.pack_order(order_id))
    
    @app.route('/api/orders/<order_id>/dispatch-approval', methods=['PUT'])
    @login_required
    @role_required('vendor_superadmin', 'vendor_admin')
    def api_dispatch_approval(order_id):
        """API: Approve order dispatch"""
        return jsonify(order_controller.approve_dispatch(order_id))
    
    @app.route('/api/orders/<order_id>/dispatch', methods=['PUT'])
    @login_required
    @role_required('vendor_superadmin', 'vendor_admin', 'vendor_normal')
    def api_dispatch_order(order_id):
        """API: Mark order as dispatched"""
        return jsonify(order_controller.dispatch_order(order_id))
    
    # ================== USER MANAGEMENT ROUTES ==================
    
    @app.route('/users')
    @login_required
    @role_required('vendor_superadmin', 'vendor_admin', 'customer_hr_admin')
    def users():
        """User management page"""
        return render_template('users.html')
    
    @app.route('/api/users')
    @login_required
    def api_users():
        """API: Get users list"""
        return jsonify(user_controller.get_users())
    
    @app.route('/api/users', methods=['POST'])
    @login_required
    def api_create_user():
        """API: Create new user"""
        return jsonify(user_controller.create_user())
    
    @app.route('/api/users/<user_id>', methods=['PUT'])
    @login_required
    def api_update_user(user_id):
        """API: Update user"""
        return jsonify(user_controller.update_user(user_id))
    

    @app.route('/api/users/<user_id>/reset-password', methods=['POST'])
    @login_required
    def api_reset_user_password(user_id):
        """API: Reset user password"""
        return jsonify(user_controller.reset_user_password(user_id))
    
    @app.route('/api/users/<user_id>')
    @login_required
    def api_user_details(user_id):
        """API: Get user details"""
        return jsonify(user_controller.get_user(user_id))

    @app.route('/api/users/<user_id>', methods=['DELETE'])
    @login_required
    def api_delete_user(user_id):
        """API: Delete user (deactivate)"""
        return jsonify(user_controller.delete_user(user_id))

    @app.route('/api/user-controller/departments')
    @login_required
    def api_get_departments():
        """API: Get departments for dropdown"""
        customer_id = request.args.get('customer_id')
        return jsonify(user_controller.get_departments_for_customer(customer_id))
    
    # ================== PROFILE ROUTES ==================
    
    @app.route('/profile')
    @login_required
    def profile():
        """User profile page"""
        return render_template('profile.html')
    
    @app.route('/api/profile', methods=['PUT'])
    @login_required
    def api_update_profile():
        """API: Update user profile"""
        return jsonify(user_controller.update_profile())
    
    # ================== SETTINGS ROUTES ==================
    
    @app.route('/settings')
    @login_required
    def settings():
        """Settings page"""
        return render_template('settings.html')
    
    @app.route('/api/vendor/settings')
    @login_required
    @role_required('vendor_superadmin', 'vendor_admin', 'vendor_normal')
    def api_vendor_settings():
        """API: Get vendor settings"""
        return jsonify(vendor_controller.get_vendor_settings())
    
    @app.route('/api/vendor/settings', methods=['PUT'])
    @login_required
    @role_required('vendor_superadmin')
    def api_update_vendor_settings():
        """API: Update vendor settings"""
        return jsonify(vendor_controller.update_vendor_settings(request.get_json()))
    
    @app.route('/api/vendor/test-email', methods=['POST'])
    @login_required
    @role_required('vendor_superadmin')
    def api_test_email():
        """API: Test email configuration"""
        return jsonify(vendor_controller.test_email_configuration())
    
    # ================== FILE SERVING ROUTES ==================
    
    @app.route('/uploads/<path:filename>')
    def uploaded_file(filename):
        """Serve uploaded files from local storage"""
        try:
            return send_file(os.path.join('uploads', filename))
        except FileNotFoundError:
            return jsonify({'success': False, 'message': 'File not found'}), 404
    
    # ================== FILE UPLOAD ROUTES ==================
    
    @app.route('/api/upload', methods=['POST'])
    @login_required
    def api_upload_file():
        """API: Upload file to local or Firebase Storage"""
        try:
            if 'file' not in request.files:
                return jsonify({'success': False, 'message': 'No file provided'})
            
            file = request.files['file']
            if file.filename == '':
                return jsonify({'success': False, 'message': 'No file selected'})
            
            # Validate file type
            allowed_extensions = {'png', 'jpg', 'jpeg', 'pdf', 'doc', 'docx', 'xls', 'xlsx'}
            file_extension = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
            
            if file_extension not in allowed_extensions:
                return jsonify({'success': False, 'message': 'File type not allowed'})
            
            # Generate unique filename
            filename = f"{uuid.uuid4().hex}.{file_extension}"
            upload_path = request.form.get('path', 'uploads')
            
            # Get storage handler
            storage_handler = config.get_storage()
            
            if config.use_local_storage:
                # Local storage
                file_path = f"{upload_path}/{filename}"
                full_path = os.path.join('uploads', file_path)
                
                # Ensure directory exists
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                
                # Save file
                file.save(full_path)
                
                file_url = f"/uploads/{file_path}"
            else:
                # Firebase Storage
                blob = storage_handler.blob(f"{upload_path}/{filename}")
                blob.upload_from_file(file.stream, content_type=file.content_type)
                blob.make_public()
                file_url = blob.public_url
            
            return jsonify({
                'success': True,
                'filename': filename,
                'url': file_url,
                'message': 'File uploaded successfully'
            })
            
        except Exception as e:
            print(f"File upload error: {e}")
            return jsonify({'success': False, 'message': 'File upload failed'})
    
    # ================== EXPORT ROUTES ==================
    
    @app.route('/api/vendor/export/<export_type>')
    @login_required
    @role_required('vendor_superadmin')
    def api_export_data(export_type):
        """API: Export system data"""
        try:
            result = vendor_controller.export_data(export_type)
            
            if result['success']:
                # Create downloadable file
                import json
                import tempfile
                
                with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                    json.dump(result['export_data'], f, indent=2)
                    temp_path = f.name
                
                filename = f"{export_type}_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                
                return send_file(
                    temp_path,
                    as_attachment=True,
                    download_name=filename,
                    mimetype='application/json'
                )
            else:
                return jsonify(result), 400
                
        except Exception as e:
            print(f"Export error: {e}")
            return jsonify({'success': False, 'message': 'Export failed'}), 500
    
    # ================== VENDOR SPECIFIC ROUTES ==================
    
    @app.route('/api/vendor/customers-dropdown')
    @login_required
    @role_required('vendor_superadmin', 'vendor_admin')
    def api_vendor_customers_dropdown():
        """API: Get customers for dropdown"""
        return jsonify(vendor_controller.get_customer_dropdown_data())
    
    @app.route('/api/vendor/system-health')
    @login_required
    @role_required('vendor_superadmin')
    def api_system_health():
        """API: Get system health status"""
        return jsonify(vendor_controller.get_system_health())
    
    @app.route('/api/vendor/notifications')
    @login_required
    @role_required('vendor_superadmin', 'vendor_admin', 'vendor_normal')
    def api_vendor_notifications():
        """API: Get vendor notifications"""
        # Implementation depends on notification system
        return jsonify({
            'success': True,
            'notifications': []  # Placeholder
        })
    
    return app

# Create Flask app instance
app = create_app()

if __name__ == '__main__':
    # Development server
    app.run(debug=True, host='0.0.0.0', port=3000)