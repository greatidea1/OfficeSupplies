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
from controllers.branch_controller import branch_controller
from controllers.location_controller import location_controller

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
    
    

    @app.route('/api/customers/<customer_id>', methods=['DELETE'])
    @login_required
    @role_required('vendor_superadmin')
    def api_delete_customer_endpoint(customer_id):
        """API: Delete customer and all associated data"""
        return jsonify(customer_controller.delete_customer(customer_id))

    
    

    # Routes for differential pricing per customer
    
    @app.route('/api/customer-pricing/<customer_id>')
    @login_required
    @role_required('vendor_superadmin', 'vendor_admin')
    def api_get_customer_pricing(customer_id):
        """API: Get customer-specific pricing - FIXED VERSION"""
        try:
            from config import config
            db = config.get_db()
            
            # Get all custom pricing for this customer
            docs = db.collection('customer_pricing').where('customer_id', '==', customer_id).get()
            
            pricing = []
            for doc in docs:
                pricing_data = doc.to_dict()
                pricing.append({
                    'product_id': pricing_data['product_id'],
                    'custom_price': pricing_data['custom_price'],
                    'created_at': pricing_data.get('created_at'),
                    'updated_at': pricing_data.get('updated_at')
                })
            
            return jsonify({
                'success': True,
                'pricing': pricing
            })
            
        except Exception as e:
            print(f"Get customer pricing error: {e}")
            return jsonify({'success': False, 'message': 'Failed to retrieve customer pricing'})
        
        
    @app.route('/api/customer-pricing', methods=['POST'])
    @login_required
    @role_required('vendor_superadmin', 'vendor_admin')
    def api_set_customer_pricing():
        """API: Set customer-specific pricing"""
        try:
            data = request.get_json()
            customer_id = data.get('customer_id')
            product_id = data.get('product_id')
            custom_price = data.get('custom_price')
            
            if not customer_id or not product_id or custom_price is None:
                return jsonify({'success': False, 'message': 'Customer ID, Product ID, and custom price are required'})
            
            # Validate that customer and product exist
            from models import Customer, Product
            customer = Customer.get_by_id(customer_id)
            product = Product.get_by_id(product_id)
            
            if not customer:
                return jsonify({'success': False, 'message': 'Customer not found'})
            
            if not product:
                return jsonify({'success': False, 'message': 'Product not found'})
            
            # Validate price
            try:
                custom_price = float(custom_price)
                if custom_price < 0:
                    return jsonify({'success': False, 'message': 'Price cannot be negative'})
            except (ValueError, TypeError):
                return jsonify({'success': False, 'message': 'Invalid price format'})
            
            # Save custom pricing
            from config import config
            from datetime import datetime
            
            db = config.get_db()
            current_user = auth_controller.get_current_user()
            
            pricing_doc = {
                'customer_id': customer_id,
                'product_id': product_id,
                'custom_price': custom_price,
                'created_by': current_user.user_id,
                'created_at': datetime.now(),
                'updated_at': datetime.now()
            }
            
            # Use combination of customer_id and product_id as document ID
            doc_id = f"{customer_id}_{product_id}"
            db.collection('customer_pricing').document(doc_id).set(pricing_doc)
            
            return jsonify({
                'success': True,
                'message': 'Customer pricing updated successfully'
            })
            
        except Exception as e:
            print(f"Set customer pricing error: {e}")
            return jsonify({'success': False, 'message': 'Failed to update customer pricing'})
        
    @app.route('/api/customer-catalog/<customer_id>')
    @login_required
    def api_customer_catalog(customer_id):
        """API: Get product catalog with customer-specific pricing"""
        try:
            current_user = auth_controller.get_current_user()
            
            # Check permissions
            if current_user.role.startswith('vendor_'):
                # Vendor users can view any customer's catalog
                pass
            elif current_user.role.startswith('customer_') and current_user.customer_id == customer_id:
                # Customer users can only view their own catalog
                pass
            else:
                return jsonify({'success': False, 'message': 'Access denied'})
            
            # Get all active products
            products = Product.get_all_active()
            
            # Get customer-specific pricing
            from config import config
            db = config.get_db()
            pricing_docs = db.collection('customer_pricing').where('customer_id', '==', customer_id).get()
            
            customer_pricing = {}
            for doc in pricing_docs:
                pricing_data = doc.to_dict()
                customer_pricing[pricing_data['product_id']] = pricing_data['custom_price']
            
            # Build catalog with customer pricing
            catalog = []
            for product in products:
                product_dict = product.to_dict()
                
                # Set effective price
                if product.product_id in customer_pricing:
                    product_dict['effective_price'] = customer_pricing[product.product_id]
                    product_dict['has_custom_price'] = True
                    product_dict['savings'] = product.price - customer_pricing[product.product_id]
                else:
                    product_dict['effective_price'] = product.price
                    product_dict['has_custom_price'] = False
                    product_dict['savings'] = 0
                
                # Calculate GST on effective price
                product_dict['gst_amount'] = (product_dict['effective_price'] * product.gst_rate) / 100
                product_dict['price_including_gst'] = product_dict['effective_price'] + product_dict['gst_amount']
                
                catalog.append(product_dict)
            
            return jsonify({
                'success': True,
                'catalog': catalog,
                'customer_id': customer_id,
                'total_products': len(catalog),
                'products_with_custom_pricing': len([p for p in catalog if p['has_custom_price']])
            })
            
        except Exception as e:
            print(f"Customer catalog error: {e}")
            return jsonify({'success': False, 'message': 'Failed to retrieve customer catalog'})
        

    # ================== PRICING IMPORT/EXPORT UTILITIES ==================

    @app.route('/api/pricing-analytics/<customer_id>')
    @login_required
    @role_required('vendor_superadmin', 'vendor_admin')
    def api_pricing_analytics(customer_id):
        """API: Get pricing analytics for a customer"""
        try:
            from config import config
            db = config.get_db()
            
            # Get all custom pricing for this customer
            pricing_docs = db.collection('customer_pricing').where('customer_id', '==', customer_id).get()
            
            total_products_with_custom_pricing = len(list(pricing_docs))
            total_savings = 0
            products_with_savings = []
            
            # Re-query since docs iterator is consumed
            pricing_docs = db.collection('customer_pricing').where('customer_id', '==', customer_id).get()
            
            for doc in pricing_docs:
                pricing_data = doc.to_dict()
                product = Product.get_by_id(pricing_data['product_id'])
                
                if product:
                    savings = product.price - pricing_data['custom_price']
                    total_savings += savings
                    
                    if savings > 0:
                        products_with_savings.append({
                            'product_name': product.product_name,
                            'base_price': product.price,
                            'custom_price': pricing_data['custom_price'],
                            'savings': savings
                        })
            
            # Get customer orders to calculate actual realized savings
            orders = Order.get_by_customer_id(customer_id)
            realized_savings = 0
            
            for order in orders:
                if order.status == 'dispatched':  # Only completed orders
                    order_summary = order_controller.get_order_pricing_summary(order)
                    realized_savings += order_summary.get('total_savings', 0)
            
            return jsonify({
                'success': True,
                'analytics': {
                    'total_products_with_custom_pricing': total_products_with_custom_pricing,
                    'potential_total_savings': total_savings,
                    'realized_savings': realized_savings,
                    'top_savings_products': sorted(products_with_savings, key=lambda x: x['savings'], reverse=True)[:10]
                }
            })
            
        except Exception as e:
            print(f"Pricing analytics error: {e}")
            return jsonify({'success': False, 'message': 'Failed to retrieve pricing analytics'})
        
    @app.route('/api/pricing-summary-report')
    @login_required
    @role_required('vendor_superadmin', 'vendor_admin')
    def api_pricing_summary_report():
        """API: Get overall pricing summary report - FIXED VERSION"""
        try:
            from config import config
            from models import Customer, Product
            
            db = config.get_db()
            
            # Initialize variables
            customers_with_pricing = {}
            report_data = []  # Initialize report_data here
            
            print("Starting pricing summary report generation...")
            
            # Get all customer pricing documents
            pricing_docs = db.collection('customer_pricing').get()
            pricing_docs_list = list(pricing_docs)  # Convert to list to avoid iterator issues
            
            print(f"Found {len(pricing_docs_list)} pricing documents")
            
            # Process each pricing document
            for doc in pricing_docs_list:
                try:
                    pricing_data = doc.to_dict()
                    customer_id = pricing_data.get('customer_id')
                    product_id = pricing_data.get('product_id')
                    custom_price = pricing_data.get('custom_price', 0)
                    
                    if not customer_id or not product_id:
                        print(f"Skipping document with missing customer_id or product_id: {doc.id}")
                        continue
                    
                    # Initialize customer data if not exists
                    if customer_id not in customers_with_pricing:
                        customers_with_pricing[customer_id] = {
                            'total_custom_products': 0,
                            'total_potential_savings': 0
                        }
                    
                    customers_with_pricing[customer_id]['total_custom_products'] += 1
                    
                    # Calculate savings
                    product = Product.get_by_id(product_id)
                    if product and product.price > 0:
                        savings = product.price - custom_price
                        if savings > 0:  # Only count positive savings
                            customers_with_pricing[customer_id]['total_potential_savings'] += savings
                            print(f"Customer {customer_id}: Product {product_id}, Savings: {savings}")
                    
                except Exception as doc_error:
                    print(f"Error processing document {doc.id}: {doc_error}")
                    continue
            
            print(f"Processed pricing data for {len(customers_with_pricing)} customers")
            
            # Build report data with customer names
            for customer_id, data in customers_with_pricing.items():
                try:
                    customer = Customer.get_by_id(customer_id)
                    if customer:
                        report_data.append({
                            'customer_id': customer_id,
                            'customer_name': customer.company_name,
                            'total_custom_products': data['total_custom_products'],
                            'total_potential_savings': round(data['total_potential_savings'], 2)
                        })
                        print(f"Added customer {customer.company_name} to report")
                    else:
                        print(f"Customer {customer_id} not found, skipping")
                except Exception as customer_error:
                    print(f"Error processing customer {customer_id}: {customer_error}")
                    continue
            
            print(f"Final report contains {len(report_data)} customers")
            
            # Sort by total potential savings (highest first)
            report_data.sort(key=lambda x: x['total_potential_savings'], reverse=True)
            
            return jsonify({
                'success': True,
                'report': {
                    'total_customers_with_custom_pricing': len(report_data),
                    'customers': report_data
                }
            })
            
        except Exception as e:
            print(f"Pricing summary report error: {e}")
            import traceback
            traceback.print_exc()
            
            return jsonify({
                'success': False, 
                'message': f'Failed to generate pricing summary report: {str(e)}'
            })
        

    # ================== PRICING VALIDATION AND UTILITIES ==================

    @app.route('/api/validate-pricing/<customer_id>/<product_id>')
    @login_required
    @role_required('vendor_superadmin', 'vendor_admin')
    def api_validate_pricing(customer_id, product_id):
        """API: Validate pricing before setting"""
        try:
            # Check if customer and product exist
            customer = Customer.get_by_id(customer_id)
            product = Product.get_by_id(product_id)
            
            if not customer:
                return jsonify({'success': False, 'message': 'Customer not found'})
            
            if not product:
                return jsonify({'success': False, 'message': 'Product not found'})
            
            # Get current pricing if exists
            from config import config
            db = config.get_db()
            doc_id = f"{customer_id}_{product_id}"
            doc = db.collection('customer_pricing').document(doc_id).get()
            
            current_custom_price = None
            if doc.exists:
                current_custom_price = doc.to_dict().get('custom_price')
            
            return jsonify({
                'success': True,
                'validation_data': {
                    'customer_name': customer.company_name,
                    'product_name': product.product_name,
                    'base_price': product.price,
                    'current_custom_price': current_custom_price,
                    'has_custom_price': current_custom_price is not None,
                    'suggested_max_discount': product.price * 0.3,  # 30% max discount suggestion
                    'minimum_price': product.price * 0.1  # 10% of base price as minimum
                }
            })
            
        except Exception as e:
            print(f"Pricing validation error: {e}")
            return jsonify({'success': False, 'message': 'Failed to validate pricing'})
        
    # ================== PRICING COMPARISON AND ANALYSIS ==================



    @app.route('/api/pricing-suggestions/<customer_id>')
    @login_required
    @role_required('vendor_superadmin', 'vendor_admin')
    def api_pricing_suggestions(customer_id):
        """API: Get pricing suggestions based on order history"""
        try:
            customer = Customer.get_by_id(customer_id)
            if not customer:
                return jsonify({'success': False, 'message': 'Customer not found'})
            
            # Get customer order history
            orders = Order.get_by_customer_id(customer_id)
            completed_orders = [o for o in orders if o.status == 'dispatched']
            
            # Analyze ordering patterns
            product_frequency = {}
            for order in completed_orders:
                for item in order.items:
                    product_id = item['product_id']
                    if product_id not in product_frequency:
                        product_frequency[product_id] = {
                            'count': 0,
                            'total_quantity': 0,
                            'total_value': 0
                        }
                    product_frequency[product_id]['count'] += 1
                    product_frequency[product_id]['total_quantity'] += item['quantity']
                    product_frequency[product_id]['total_value'] += item['total']
            
            # Generate suggestions
            suggestions = []
            for product_id, stats in product_frequency.items():
                if stats['count'] >= 3:  # Products ordered 3+ times
                    product = Product.get_by_id(product_id)
                    if product:
                        avg_order_value = stats['total_value'] / stats['count']
                        suggested_discount = min(0.15, stats['count'] * 0.02)  # Up to 15% discount
                        suggested_price = product.price * (1 - suggested_discount)
                        
                        suggestions.append({
                            'product_id': product_id,
                            'product_name': product.product_name,
                            'base_price': product.price,
                            'suggested_price': suggested_price,
                            'discount_percentage': suggested_discount * 100,
                            'order_frequency': stats['count'],
                            'avg_order_value': avg_order_value,
                            'reason': f"Frequently ordered ({stats['count']} times)"
                        })
            
            # Sort by order frequency
            suggestions.sort(key=lambda x: x['order_frequency'], reverse=True)
            
            return jsonify({
                'success': True,
                'suggestions': suggestions[:10],  # Top 10 suggestions
                'customer_name': customer.company_name,
                'total_completed_orders': len(completed_orders)
            })
            
        except Exception as e:
            print(f"Pricing suggestions error: {e}")
            return jsonify({'success': False, 'message': 'Failed to generate pricing suggestions'})

    @app.route('/api/pricing-comparison/<product_id>')
    @login_required
    @role_required('vendor_superadmin', 'vendor_admin')
    def api_pricing_comparison(product_id):
        """API: Compare pricing across all customers for a product"""
        try:
            product = Product.get_by_id(product_id)
            if not product:
                return jsonify({'success': False, 'message': 'Product not found'})
            
            from config import config
            db = config.get_db()
            
            # Get all custom pricing for this product
            pricing_docs = db.collection('customer_pricing').where('product_id', '==', product_id).get()
            
            pricing_comparison = []
            for doc in pricing_docs:
                pricing_data = doc.to_dict()
                customer = Customer.get_by_id(pricing_data['customer_id'])
                
                if customer:
                    savings = product.price - pricing_data['custom_price']
                    discount_percentage = (savings / product.price) * 100 if product.price > 0 else 0
                    
                    pricing_comparison.append({
                        'customer_id': customer.customer_id,
                        'customer_name': customer.company_name,
                        'custom_price': pricing_data['custom_price'],
                        'savings': savings,
                        'discount_percentage': discount_percentage,
                        'updated_at': pricing_data.get('updated_at')
                    })
            
            # Sort by discount percentage (highest first)
            pricing_comparison.sort(key=lambda x: x['discount_percentage'], reverse=True)
            
            # Calculate statistics
            if pricing_comparison:
                custom_prices = [p['custom_price'] for p in pricing_comparison]
                avg_custom_price = sum(custom_prices) / len(custom_prices)
                min_custom_price = min(custom_prices)
                max_custom_price = max(custom_prices)
                avg_discount = sum(p['discount_percentage'] for p in pricing_comparison) / len(pricing_comparison)
            else:
                avg_custom_price = min_custom_price = max_custom_price = avg_discount = 0
            
            return jsonify({
                'success': True,
                'product_name': product.product_name,
                'base_price': product.price,
                'pricing_comparison': pricing_comparison,
                'statistics': {
                    'total_customers_with_custom_pricing': len(pricing_comparison),
                    'avg_custom_price': avg_custom_price,
                    'min_custom_price': min_custom_price,
                    'max_custom_price': max_custom_price,
                    'avg_discount_percentage': avg_discount
                }
            })
            
        except Exception as e:
            print(f"Pricing comparison error: {e}")
            return jsonify({'success': False, 'message': 'Failed to generate pricing comparison'})

    @app.route('/api/pricing-template/<customer_id>')
    @login_required
    @role_required('vendor_superadmin', 'vendor_admin')
    def api_pricing_template(customer_id):
        """API: Generate pricing template CSV for bulk upload"""
        try:
            import csv
            import tempfile
            from datetime import datetime
            
            # Get all active products
            products = Product.get_all_active()
            
            # Get customer info
            customer = Customer.get_by_id(customer_id)
            if not customer:
                return jsonify({'success': False, 'message': 'Customer not found'}), 404
            
            # Create CSV template
            with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, newline='') as f:
                writer = csv.writer(f)
                
                # Write header
                writer.writerow([
                    'Product ID',
                    'Product Name',
                    'Current Base Price',
                    'Custom Price (Enter your price)',
                    'Category',
                    'Make',
                    'Model'
                ])
                
                # Write product data
                for product in products:
                    writer.writerow([
                        product.product_id,
                        product.product_name,
                        f"{product.price:.2f}",
                        "",  # Empty for user to fill
                        product.category,
                        product.product_make or "",
                        product.product_model or ""
                    ])
                
                temp_path = f.name
            
            # Generate filename
            filename = f"pricing_template_{customer.company_name}_{datetime.now().strftime('%Y%m%d')}.csv"
            
            return send_file(
                temp_path,
                as_attachment=True,
                download_name=filename,
                mimetype='text/csv'
            )
            
        except Exception as e:
            print(f"Pricing template error: {e}")
            return jsonify({'success': False, 'message': 'Failed to generate pricing template'}), 500
        
    @app.route('/api/pricing-import/<customer_id>', methods=['POST'])
    @login_required
    @role_required('vendor_superadmin', 'vendor_admin')
    def api_pricing_import(customer_id):
        """API: Import customer pricing from CSV"""
        try:
            if 'file' not in request.files:
                return jsonify({'success': False, 'message': 'No file uploaded'})
            
            file = request.files['file']
            if file.filename == '':
                return jsonify({'success': False, 'message': 'No file selected'})
            
            if not file.filename.endswith('.csv'):
                return jsonify({'success': False, 'message': 'File must be a CSV'})
            
            # Validate customer exists
            customer = Customer.get_by_id(customer_id)
            if not customer:
                return jsonify({'success': False, 'message': 'Customer not found'})
            
            import csv
            import io
            
            # Read CSV
            stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
            csv_reader = csv.DictReader(stream)
            
            successful_imports = 0
            errors = []
            
            for row_num, row in enumerate(csv_reader, start=2):  # Start at 2 because row 1 is header
                try:
                    product_id = row.get('Product ID', '').strip()
                    custom_price_str = row.get('Custom Price (Enter your price)', '').strip()
                    
                    if not product_id:
                        continue  # Skip empty rows
                    
                    if not custom_price_str:
                        continue  # Skip rows without custom price
                    
                    # Validate product exists
                    product = Product.get_by_id(product_id)
                    if not product:
                        errors.append(f"Row {row_num}: Product {product_id} not found")
                        continue
                    
                    # Validate price
                    try:
                        custom_price = float(custom_price_str)
                        if custom_price < 0:
                            errors.append(f"Row {row_num}: Price cannot be negative")
                            continue
                    except ValueError:
                        errors.append(f"Row {row_num}: Invalid price format '{custom_price_str}'")
                        continue
                    
                    # Set customer pricing
                    result = product_controller.set_customer_pricing(product_id, customer_id, custom_price)
                    if result['success']:
                        successful_imports += 1
                    else:
                        errors.append(f"Row {row_num}: {result['message']}")
                        
                except Exception as e:
                    errors.append(f"Row {row_num}: {str(e)}")
            
            return jsonify({
                'success': True,
                'message': f'Successfully imported pricing for {successful_imports} products',
                'successful_imports': successful_imports,
                'errors': errors[:10],  # Limit errors to first 10
                'total_errors': len(errors)
            })
            
        except Exception as e:
            print(f"Pricing import error: {e}")
            return jsonify({'success': False, 'message': 'Failed to import pricing'}), 500
        
    @app.route('/api/pricing-history/<customer_id>/<product_id>')
    @login_required
    @role_required('vendor_superadmin', 'vendor_admin')
    def api_pricing_history(customer_id, product_id):
        """API: Get pricing history for a customer-product combination"""
        try:
            from config import config
            db = config.get_db()
            
            # Get pricing history (if you implement versioning)
            # For now, just return current pricing
            doc_id = f"{customer_id}_{product_id}"
            doc = db.collection('customer_pricing').document(doc_id).get()
            
            if not doc.exists:
                return jsonify({
                    'success': True,
                    'history': [],
                    'message': 'No custom pricing history found'
                })
            
            pricing_data = doc.to_dict()
            product = Product.get_by_id(product_id)
            customer = Customer.get_by_id(customer_id)
            
            if not product or not customer:
                return jsonify({'success': False, 'message': 'Product or customer not found'})
            
            history = [{
                'date': pricing_data.get('updated_at', pricing_data.get('created_at')),
                'price': pricing_data['custom_price'],
                'base_price': product.price,
                'savings': product.price - pricing_data['custom_price'],
                'updated_by': pricing_data.get('created_by')
            }]
            
            return jsonify({
                'success': True,
                'history': history,
                'product_name': product.product_name,
                'customer_name': customer.company_name
            })
            
        except Exception as e:
            print(f"Pricing history error: {e}")
            return jsonify({'success': False, 'message': 'Failed to retrieve pricing history'})
        
    @app.route('/api/customer-pricing-list/<customer_id>')
    @login_required
    @role_required('vendor_superadmin', 'vendor_admin')
    def api_get_customer_pricing_list(customer_id):
        """API: Get detailed customer pricing list with product information"""
        return jsonify(product_controller.get_customer_pricing_list(customer_id))
    
    @app.route('/api/customer-pricing-widget/<customer_id>')
    @login_required
    def api_customer_pricing_widget(customer_id):
        """API: Get pricing widget data for customer dashboard"""
        try:
            current_user = auth_controller.get_current_user()
            
            # Check permissions
            if current_user.role.startswith('vendor_'):
                pass  # Vendor can view any customer
            elif current_user.role.startswith('customer_') and current_user.customer_id == customer_id:
                pass  # Customer can view own data
            else:
                return jsonify({'success': False, 'message': 'Access denied'})
            
            from config import config
            from datetime import timedelta
            db = config.get_db()
            
            # Get pricing statistics
            pricing_docs = db.collection('customer_pricing').where('customer_id', '==', customer_id).get()
            
            total_custom_products = 0
            total_potential_savings = 0
            
            for doc in pricing_docs:
                pricing_data = doc.to_dict()
                product = Product.get_by_id(pricing_data['product_id'])
                
                if product:
                    total_custom_products += 1
                    savings = product.price - pricing_data['custom_price']
                    if savings > 0:
                        total_potential_savings += savings
            
            # Get recent orders to calculate realized savings
            orders = Order.get_by_customer_id(customer_id)
            recent_orders = [o for o in orders if o.created_at >= datetime.now() - timedelta(days=30)]
            
            recent_realized_savings = 0
            for order in recent_orders:
                if order.status == 'dispatched':
                    order_summary = order_controller.get_order_pricing_summary(order)
                    recent_realized_savings += order_summary.get('total_savings', 0)
            
            return jsonify({
                'success': True,
                'widget_data': {
                    'total_custom_products': total_custom_products,
                    'total_potential_savings': total_potential_savings,
                    'recent_realized_savings': recent_realized_savings,
                    'savings_rate': (total_potential_savings / (total_custom_products * 100)) * 100 if total_custom_products > 0 else 0
                }
            })
            
        except Exception as e:
            print(f"Customer pricing widget error: {e}")
            return jsonify({'success': False, 'message': 'Failed to retrieve pricing widget data'})

        

    @app.route('/api/customer-pricing/<customer_id>/<product_id>', methods=['DELETE'])
    @login_required
    @role_required('vendor_superadmin', 'vendor_admin')
    def api_delete_customer_pricing(customer_id, product_id):
        """API: Delete customer-specific pricing (revert to base price)"""
        try:
            from config import config
            db = config.get_db()
            
            # Delete the custom pricing document
            doc_id = f"{customer_id}_{product_id}"
            db.collection('customer_pricing').document(doc_id).delete()
            
            return jsonify({
                'success': True,
                'message': 'Customer pricing removed successfully'
            })
            
        except Exception as e:
            print(f"Delete customer pricing error: {e}")
            return jsonify({'success': False, 'message': 'Failed to remove customer pricing'})
    
    # ================== PRODUCT ROUTES ==================
    
    @app.route('/products')
    @login_required
    def products():
        """Products page"""
        # Use the same template for both vendor and customer users
        # The template handles role-based functionality with Jinja2 conditionals
        return render_template('products.html')
    
    @app.route('/api/products')
    @login_required
    def api_products():
        """API: Get products list with customer-specific pricing - FIXED FOR ALL USERS"""
        return jsonify(product_controller.get_products())
    
    @app.route('/api/products', methods=['POST'])
    @login_required
    @role_required('vendor_superadmin', 'vendor_admin', 'vendor_normal')
    def api_create_product():
        """API: Create new product without base pricing (pricing set per customer)"""
        return jsonify(product_controller.create_product())
    
    @app.route('/api/products/<product_id>')
    @login_required
    def api_product_details(product_id):
        """API: Get product details with customer-specific pricing"""
        return jsonify(product_controller.get_product(product_id))
    
    @app.route('/api/products/<product_id>', methods=['PUT'])
    @login_required
    @role_required('vendor_superadmin', 'vendor_admin', 'vendor_normal')
    def api_update_product(product_id):
        """API: Update product with support for both JSON and multipart form data"""
        return jsonify(product_controller.update_product(product_id))
    
    @app.route('/api/products/<product_id>', methods=['DELETE'])
    @login_required
    @role_required('vendor_superadmin')
    def api_delete_product(product_id):
        """API: Delete product (soft delete)"""
        return jsonify(product_controller.delete_product(product_id))
    
    # ================== BULK PRICING OPERATIONS ==================

    @app.route('/api/bulk-customer-pricing', methods=['POST'])
    @login_required
    @role_required('vendor_superadmin', 'vendor_admin')
    def api_bulk_set_customer_pricing():
        """API: Set multiple customer-specific prices at once"""
        try:
            data = request.get_json()
            customer_id = data.get('customer_id')
            pricing_updates = data.get('pricing_updates', [])
            
            if not customer_id or not pricing_updates:
                return jsonify({'success': False, 'message': 'Customer ID and pricing updates are required'})
            
            # Validate customer exists
            from models import Customer
            customer = Customer.get_by_id(customer_id)
            if not customer:
                return jsonify({'success': False, 'message': 'Customer not found'})
            
            successful_updates = 0
            errors = []
            
            for update in pricing_updates:
                try:
                    product_id = update.get('product_id')
                    custom_price = float(update.get('custom_price'))
                    
                    # Use the existing set_customer_pricing method
                    result = product_controller.set_customer_pricing(product_id, customer_id, custom_price)
                    
                    if result['success']:
                        successful_updates += 1
                    else:
                        errors.append(f"Product {product_id}: {result['message']}")
                        
                except Exception as e:
                    errors.append(f"Product {update.get('product_id', 'unknown')}: {str(e)}")
            
            return jsonify({
                'success': True,
                'message': f'Updated pricing for {successful_updates} products',
                'successful_updates': successful_updates,
                'errors': errors
            })
            
        except Exception as e:
            print(f"Bulk set customer pricing error: {e}")
            return jsonify({'success': False, 'message': 'Failed to update bulk pricing'})

    @app.route('/api/customer-pricing-export/<customer_id>')
    @login_required
    @role_required('vendor_superadmin', 'vendor_admin')
    def api_export_customer_pricing(customer_id):
        """API: Export customer pricing to CSV"""
        try:
            import csv
            import tempfile
            from datetime import datetime
            
            # Get customer pricing list
            result = product_controller.get_customer_pricing_list(customer_id)
            
            if not result['success']:
                return jsonify(result), 400
            
            # Get customer info
            from models import Customer
            customer = Customer.get_by_id(customer_id)
            customer_name = customer.company_name if customer else customer_id
            
            # Create CSV file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, newline='') as f:
                writer = csv.writer(f)
                
                # Write header
                writer.writerow([
                    'Product ID',
                    'Product Name',
                    'Product Make',
                    'Base Price',
                    'Custom Price',
                    'Savings',
                    'Last Updated'
                ])
                
                # Write data
                for item in result['pricing']:
                    writer.writerow([
                        item['product_id'],
                        item['product_name'],
                        item.get('product_make', ''),
                        f"₹{item['base_price']:.2f}",
                        f"₹{item['custom_price']:.2f}",
                        f"₹{item['savings']:.2f}",
                        item.get('updated_at', '').strftime('%Y-%m-%d %H:%M:%S') if item.get('updated_at') else ''
                    ])
                
                temp_path = f.name
            
            # Generate filename
            filename = f"customer_pricing_{customer_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            
            return send_file(
                temp_path,
                as_attachment=True,
                download_name=filename,
                mimetype='text/csv'
            )
            
        except Exception as e:
            print(f"Export customer pricing error: {e}")
            return jsonify({'success': False, 'message': 'Failed to export pricing'}), 500
    
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
    
    # ================== BRANCH ROUTES ==================

    @app.route('/branches')
    @login_required
    @role_required('customer_hr_admin')
    def branches():
        """Branch management page (HR Admin only)"""
        return render_template('branches.html')

    @app.route('/api/branches')
    @login_required
    def api_branches():
        """API: Get branches list"""
        return jsonify(branch_controller.get_branches())

    @app.route('/api/branches', methods=['POST'])
    @login_required
    @role_required('customer_hr_admin')
    def api_create_branch():
        """API: Create new branch"""
        return jsonify(branch_controller.create_branch())

    @app.route('/api/branches/<branch_id>')
    @login_required
    def api_branch_details(branch_id):
        """API: Get branch details"""
        return jsonify(branch_controller.get_branch(branch_id))

    @app.route('/api/branches/<branch_id>', methods=['PUT'])
    @login_required
    @role_required('customer_hr_admin')
    def api_update_branch(branch_id):
        """API: Update branch"""
        return jsonify(branch_controller.update_branch(branch_id))

    @app.route('/api/branches/<branch_id>', methods=['DELETE'])
    @login_required
    @role_required('customer_hr_admin')
    def api_delete_branch(branch_id):
        """API: Delete branch"""
        return jsonify(branch_controller.delete_branch(branch_id))

    @app.route('/api/branches/company-info')
    @login_required
    @role_required('customer_hr_admin')
    def api_get_company_info():
        """API: Get company information"""
        return jsonify(branch_controller.get_company_info())

    @app.route('/api/branches/company-info', methods=['PUT'])
    @login_required
    @role_required('customer_hr_admin')
    def api_update_company_info():
        """API: Update company information"""
        return jsonify(branch_controller.update_company_info())
    
    
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
    @role_required('customer_employee', 'customer_dept_head', 'customer_hr_admin')  # Allow all customer roles
    def api_create_order():
        """API: Create new order with customer-specific pricing"""
        return jsonify(order_controller.create_order())
    
    @app.route('/api/orders/<order_id>')
    @login_required
    def api_order_details(order_id):
        """API: Get order details with pricing information"""
        return jsonify(order_controller.get_order(order_id))
    
    @app.route('/orders/<order_id>')
    @login_required
    def order_details(order_id):
        """Order details page"""
        return render_template('order_details.html', order_id=order_id)
    
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
    
    @app.route('/api/user-controller/branches')
    @login_required
    def api_get_branches():
        """API: Get branches for dropdown"""
        customer_id = request.args.get('customer_id')
        return jsonify(user_controller.get_branches_for_customer(customer_id))

    @app.route('/api/department-controller/branches')
    @login_required
    @role_required('customer_hr_admin')
    def api_get_branches_for_departments():
        """API: Get branches for department management"""
        return jsonify(department_controller.get_branches_for_customer())
    
    # ================== PROFILE ROUTES ==================
    
    @app.route('/profile')
    @login_required
    def profile():
        """User profile page"""
        return render_template('profile.html')
    
    @app.route('/api/profile/data')
    @login_required
    def api_profile_data():
        """API: Get enhanced profile data with branch info including pincode"""
        try:
            current_user = auth_controller.get_current_user()
            if not current_user:
                return jsonify({'success': False, 'message': 'Authentication required'})
            
            profile_data = {
                'user_id': current_user.user_id,
                'username': current_user.username,
                'full_name': current_user.full_name,
                'email': current_user.email,
                'role': current_user.role,
                'is_active': current_user.is_active,
                'last_login': current_user.last_login,
                'customer_id': current_user.customer_id,
                'department_id': current_user.department_id,
                'branch_id': getattr(current_user, 'branch_id', None)
            }
            
            # Add company info for customer users
            if current_user.role.startswith('customer_') and current_user.customer_id:
                from models import Customer, Department, Branch
                
                customer = Customer.get_by_id(current_user.customer_id)
                if customer:
                    profile_data['company_name'] = customer.company_name
                    profile_data['company_alias'] = getattr(customer, 'company_alias', '')
                
                # Add department info
                if current_user.department_id:
                    department = Department.get_by_id(current_user.department_id)
                    if department:
                        profile_data['department_name'] = department.name
                
                # Add branch info with pincode
                if hasattr(current_user, 'branch_id') and current_user.branch_id:
                    branch = Branch.get_by_id(current_user.branch_id)
                    if branch:
                        branch_display = branch.name
                        if branch.pincode:
                            branch_display += f" ({branch.pincode})"
                        
                        profile_data['branch_name'] = branch_display
                        profile_data['branch_address'] = branch.address
                        profile_data['branch_pincode'] = branch.pincode
            
            return jsonify({
                'success': True,
                'profile': profile_data
            })
            
        except Exception as e:
            print(f"Get profile data error: {e}")
            return jsonify({'success': False, 'message': 'Failed to retrieve profile data'})
    
    @app.route('/api/profile', methods=['PUT'])
    @login_required
    def api_update_profile():
        """API: Update user profile with email support"""
        try:
            current_user = auth_controller.get_current_user()
            if not current_user:
                return jsonify({'success': False, 'message': 'Authentication required'})
            
            data = request.get_json()
            
            # Update allowed fields
            updateable_fields = ['full_name']
            
            # Allow customer users to update email
            if current_user.role.startswith('customer_'):
                updateable_fields.append('email')
                
                # If email is being updated, check if it already exists
                if 'email' in data and data['email'] != current_user.email:
                    from models import User
                    existing_user = User.get_by_email(data['email'])
                    if existing_user and existing_user.user_id != current_user.user_id:
                        return jsonify({'success': False, 'message': 'Email address already exists'})
            
            for field in updateable_fields:
                if field in data:
                    setattr(current_user, field, data[field])
            
            if current_user.save():
                return jsonify({
                    'success': True,
                    'message': 'Profile updated successfully'
                })
            else:
                return jsonify({'success': False, 'message': 'Failed to update profile'})
                
        except Exception as e:
            print(f"Update profile error: {e}")
            return jsonify({'success': False, 'message': 'Failed to update profile'})
    
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
    
    # Add this test endpoint to app.py
    @app.route('/api/test')
    @login_required
    def api_test():
        """Test endpoint to check if API is working"""
        current_user = auth_controller.get_current_user()
        return jsonify({
            'success': True,
            'message': 'API is working',
            'user': {
                'username': current_user.username if current_user else None,
                'role': current_user.role if current_user else None,
                'customer_id': current_user.customer_id if current_user else None
            }
        })
    
    # TEMPORARY Add this test endpoint to app.py to debug directory issues
    @app.route('/api/test-upload-dir')
    @login_required
    @role_required('vendor_superadmin', 'vendor_admin', 'vendor_normal')
    def test_upload_directory():
        """Test endpoint to check upload directory creation"""
        import os
        
        try:
            base_dir = os.path.abspath('uploads')
            products_dir = os.path.join(base_dir, 'products')
            
            # Try to create directory
            os.makedirs(products_dir, exist_ok=True)
            
            # Test file creation
            test_file = os.path.join(products_dir, 'test.txt')
            with open(test_file, 'w') as f:
                f.write('test')
            
            # Check if file exists
            file_exists = os.path.exists(test_file)
            
            # Clean up
            if file_exists:
                os.remove(test_file)
            
            return jsonify({
                'success': True,
                'base_dir': base_dir,
                'products_dir': products_dir,
                'base_exists': os.path.exists(base_dir),
                'products_exists': os.path.exists(products_dir),
                'can_write': file_exists,
                'cwd': os.getcwd()
            })
            
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e),
                'cwd': os.getcwd()
            })
        

    @app.route('/cart')
    @login_required
    @role_required('customer_employee', 'customer_dept_head', 'customer_hr_admin')
    def cart():
        """Shopping cart page for customer users"""
        return render_template('cart.html')
    
    @app.route('/api/vendor/test-connection', methods=['POST'])
    @login_required
    @role_required('vendor_superadmin')
    def api_test_smtp_connection():
        """API: Test SMTP connection without sending email"""
        try:
            current_user = auth_controller.get_current_user()
            if not current_user or current_user.role != 'vendor_superadmin':
                return jsonify({'success': False, 'message': 'Only SuperAdmin can test connection'})
            
            result = auth_controller.test_smtp_connection()
            return jsonify(result)
            
        except Exception as e:
            print(f"Test SMTP connection error: {e}")
            return jsonify({'success': False, 'message': 'Failed to test connection'})

    @app.route('/api/vendor/email-suggestions')
    @login_required
    @role_required('vendor_superadmin')
    def api_email_suggestions():
        """API: Get email configuration suggestions based on email domain"""
        try:
            current_user = auth_controller.get_current_user()
            if not current_user or current_user.role != 'vendor_superadmin':
                return jsonify({'success': False, 'message': 'Access denied'})
            
            email = request.args.get('email', '')
            suggestions = auth_controller.get_email_server_suggestions(email)
            
            return jsonify({
                'success': True,
                'suggestions': suggestions
            })
            
        except Exception as e:
            print(f"Email suggestions error: {e}")
            return jsonify({'success': False, 'message': 'Failed to get email suggestions'})

    @app.route('/api/vendor/validate-email-config')
    @login_required
    @role_required('vendor_superadmin')
    def api_validate_email_config():
        """API: Validate email configuration completeness"""
        try:
            result = vendor_controller.validate_email_configuration()
            return jsonify(result)
            
        except Exception as e:
            print(f"Validate email config error: {e}")
            return jsonify({'success': False, 'message': 'Failed to validate email configuration'})

    @app.route('/api/vendor/email-config-status')
    @login_required
    @role_required('vendor_superadmin')
    def api_email_config_status():
        """API: Get email configuration status"""
        try:
            from models import VendorSettings
            settings = VendorSettings.get_settings()
            status = settings.get_email_config_status()
            
            return jsonify({
                'success': True,
                'status': status
            })
            
        except Exception as e:
            print(f"Email config status error: {e}")
            return jsonify({'success': False, 'message': 'Failed to get email configuration status'})
        
    # ================== CUSTOMER EDIT ROUTES ==================

    @app.route('/customers/<customer_id>/edit')
    @login_required
    @role_required('vendor_superadmin', 'vendor_admin')
    def edit_customer(customer_id):
        """Customer edit page - FIXED VERSION"""
        # Verify customer exists
        from models import Customer
        customer = Customer.get_by_id(customer_id)
        if not customer:
            return render_template('errors/404.html'), 404
        
        return render_template('customer_edit.html', customer_id=customer_id)

    @app.route('/api/customers/<customer_id>', methods=['PUT'])
    @login_required
    @role_required('vendor_superadmin', 'vendor_admin')
    def api_update_customer(customer_id):
        """API: Update customer with file upload support - FIXED VERSION"""
        try:
            current_user = auth_controller.get_current_user()
            if not current_user or current_user.role not in ['vendor_superadmin', 'vendor_admin']:
                return jsonify({'success': False, 'message': 'Insufficient permissions'})
            
            from models import Customer
            customer = Customer.get_by_id(customer_id)
            if not customer:
                return jsonify({'success': False, 'message': 'Customer not found'})
            
            # Handle both form data and JSON
            if request.content_type and request.content_type.startswith('multipart/form-data'):
                data = request.form.to_dict()
            else:
                data = request.get_json()
            
            # Update basic fields
            updateable_fields = [
                'company_name', 'email', 'postal_address', 
                'primary_phone', 'alternate_phone', 'is_active'
            ]
            
            for field in updateable_fields:
                if field in data:
                    if field == 'is_active':
                        setattr(customer, field, data[field] == 'true' or data[field] is True)
                    else:
                        setattr(customer, field, data[field])
            
            # Handle agreement file upload
            if 'agreement_file' in request.files:
                file = request.files['agreement_file']
                if file and file.filename:
                    # Remove old file logic could go here
                    agreement_url = customer_controller.upload_agreement_file(file, customer.customer_id)
                    if agreement_url:
                        customer.agreement_file_url = agreement_url
                    else:
                        return jsonify({'success': False, 'message': 'Failed to upload agreement file'})
            
            # Handle file removal
            if data.get('remove_current_file') == 'true':
                customer.agreement_file_url = None
            
            if customer.save():
                return jsonify({
                    'success': True,
                    'message': 'Customer updated successfully'
                })
            else:
                return jsonify({'success': False, 'message': 'Failed to update customer'})
                
        except Exception as e:
            print(f"Update customer error: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'success': False, 'message': 'Failed to update customer'})

    # ================== PRODUCT CATEGORIES ROUTES ==================

    @app.route('/categories')
    @login_required
    @role_required('vendor_superadmin', 'vendor_admin', 'vendor_normal')
    def categories():
        """Product categories management page"""
        return render_template('categories.html')

    @app.route('/api/products/categories')
    @login_required
    def api_get_categories():
        """API: Get product categories - FIXED VERSION"""
        try:
            categories = product_controller.get_product_categories()
            return jsonify({
                'success': True,
                'categories': categories
            })
        except Exception as e:
            print(f"Get categories error: {e}")
            return jsonify({'success': False, 'message': 'Failed to retrieve categories'})

    @app.route('/api/products/categories', methods=['PUT'])
    @login_required
    @role_required('vendor_superadmin', 'vendor_admin')
    def api_update_categories():
        """API: Update product categories - FIXED VERSION"""
        try:
            data = request.get_json()
            if not data:
                return jsonify({'success': False, 'message': 'No data provided'})
            
            categories = data.get('categories', [])
            
            if not isinstance(categories, list):
                return jsonify({'success': False, 'message': 'Categories must be a list'})
            
            # Validate categories
            for category in categories:
                if not isinstance(category, str) or not category.strip():
                    return jsonify({'success': False, 'message': 'Invalid category format'})
            
            # Remove duplicates and empty strings
            categories = list(set([cat.strip() for cat in categories if cat.strip()]))
            
            result = product_controller.update_product_categories(categories)
            return jsonify(result)
            
        except Exception as e:
            print(f"Update categories error: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'success': False, 'message': f'Failed to update categories: {str(e)}'})
        
    # ================== TEST ENDPOINT FOR DEBUGGING ==================

    @app.route('/api/test-categories')
    @login_required
    @role_required('vendor_superadmin', 'vendor_admin')
    def api_test_categories():
        """Test endpoint for categories functionality"""
        try:
            from config import config
            db = config.get_db()
            
            # Test database connection
            test_doc = db.collection('test').document('test').get()
            
            # Test categories collection
            categories_doc = db.collection('product_categories').document('default').get()
            
            return jsonify({
                'success': True,
                'database_connected': True,
                'categories_doc_exists': categories_doc.exists,
                'categories_data': categories_doc.to_dict() if categories_doc.exists else None,
                'message': 'Categories test completed'
            })
            
        except Exception as e:
            print(f"Test categories error: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({
                'success': False,
                'error': str(e),
                'message': 'Categories test failed'
            })
        
    # ================== ENHANCED USER ROUTES FOR BRANCH SUPPORT ==================



    @app.route('/api/users-with-branches')
    @login_required
    def api_users_with_branches():
        """API: Get users list with branch information - FIXED VERSION"""
        try:
            result = user_controller.get_users()
            
            if result['success']:
                # Add branch information to each user
                for user in result['users']:
                    if user.get('branch_id'):
                        from models import Branch
                        branch = Branch.get_by_id(user['branch_id'])
                        if branch:
                            user['branch_name'] = branch.name
                            user['branch_address'] = branch.address
                        else:
                            user['branch_name'] = 'Unknown Branch'
                            user['branch_address'] = None
                    else:
                        user['branch_name'] = None
                        user['branch_address'] = None
            
            return jsonify(result)
            
        except Exception as e:
            print(f"Get users with branches error: {e}")
            return jsonify({'success': False, 'message': 'Failed to retrieve users'})

    @app.route('/api/branches-dropdown')
    @login_required
    def api_branches_dropdown():
        """API: Get branches for dropdown filtering - FIXED VERSION"""
        try:
            current_user = auth_controller.get_current_user()
            
            # Get branches based on user role
            if current_user.role.startswith('customer_'):
                from models import Branch
                branches = Branch.get_by_customer_id(current_user.customer_id)
            elif current_user.role.startswith('vendor_'):
                # Vendor users can see branches from all customers
                from models import Branch, Customer
                branches = []
                customers = Customer.get_all_active()
                for customer in customers:
                    customer_branches = Branch.get_by_customer_id(customer.customer_id)
                    for branch in customer_branches:
                        if branch.is_active:
                            branch.customer_name = customer.company_name  # Add customer context
                            branches.append(branch)
            else:
                branches = []
            
            branch_list = []
            for branch in branches:
                branch_data = {
                    'branch_id': branch.branch_id,
                    'name': branch.name,
                    'address': branch.address
                }
                
                # Add customer context for vendor users
                if current_user.role.startswith('vendor_') and hasattr(branch, 'customer_name'):
                    branch_data['display_name'] = f"{branch.name} ({branch.customer_name})"
                else:
                    branch_data['display_name'] = branch.name
                
                branch_list.append(branch_data)
            
            return jsonify({
                'success': True,
                'branches': branch_list
            })
            
        except Exception as e:
            print(f"Get branches dropdown error: {e}")
            return jsonify({'success': False, 'message': 'Failed to retrieve branches'})
        

    # ================== LOCATION ROUTES ==================
    
    @app.route('/locations')
    @login_required
    @role_required('vendor_superadmin', 'vendor_admin', 'vendor_normal')
    def locations():
        """Locations management page"""
        return render_template('locations.html')
    
    @app.route('/api/locations')
    @login_required
    @role_required('vendor_superadmin', 'vendor_admin', 'vendor_normal')
    def api_locations():
        """API: Get locations list"""
        return jsonify(location_controller.get_locations())
    
    @app.route('/api/locations', methods=['POST'])
    @login_required
    @role_required('vendor_superadmin', 'vendor_admin')
    def api_create_location():
        """API: Create new location"""
        return jsonify(location_controller.create_location())
    
    @app.route('/api/locations/<location_id>')
    @login_required
    @role_required('vendor_superadmin', 'vendor_admin', 'vendor_normal')
    def api_location_details(location_id):
        """API: Get location details"""
        return jsonify(location_controller.get_location(location_id))
    
    @app.route('/api/locations/<location_id>', methods=['PUT'])
    @login_required
    @role_required('vendor_superadmin', 'vendor_admin')
    def api_update_location(location_id):
        """API: Update location"""
        return jsonify(location_controller.update_location(location_id))
    
    @app.route('/api/locations/<location_id>', methods=['DELETE'])
    @login_required
    @role_required('vendor_superadmin')
    def api_delete_location(location_id):
        """API: Delete location"""
        return jsonify(location_controller.delete_location(location_id))
    
    @app.route('/api/locations-dropdown')
    @login_required
    @role_required('vendor_superadmin', 'vendor_admin', 'vendor_normal')
    def api_locations_dropdown():
        """API: Get locations for dropdown"""
        return jsonify(location_controller.get_locations_dropdown())
    

    # ================== ENHANCED LOCATION ROUTES ==================

    @app.route('/api/locations/states')
    @login_required
    @role_required('vendor_superadmin', 'vendor_admin', 'vendor_normal')
    def api_location_states():
        """API: Get states list grouped by pincode zones"""
        try:
            current_user = auth_controller.get_current_user()
            if not current_user or not current_user.role.startswith('vendor_'):
                return jsonify({'success': False, 'message': 'Access denied'})
            
            # Indian states grouped by pincode zones
            pincode_states = {
                '1': ['Delhi NCR', 'Haryana', 'Himachal Pradesh', 'Punjab', 'UT/Chandigarh', 'UT/Jammu and Kashmir', 'UT/Ladakh'],
                '2': ['Uttarakhand', 'Uttar Pradesh'],
                '3': ['Gujarat', 'Rajasthan', 'UT/Dadra, Nagar Haveli, Daman & Diu'],
                '4': ['Chhattisgarh', 'Goa', 'Madhya Pradesh', 'Maharashtra'],
                '5': ['Andhra Pradesh', 'Karnataka', 'Telangana'],
                '6': ['Kerala', 'Tamil Nadu', 'UT/Puducherry', 'UT/Lakshadweep'],
                '7': ['Arunachal Pradesh', 'Assam', 'Manipur', 'Meghalaya', 'Mizoram', 'Nagaland', 'Odisha', 'Sikkim', 'Tripura', 'West Bengal', 'UT/Andaman and Nicobar Islands'],
                '8': ['Bihar', 'Jharkhand']
            }
            
            # Get all states as a flat list for convenience
            all_states = []
            for zone_states in pincode_states.values():
                all_states.extend(zone_states)
            
            return jsonify({
                'success': True,
                'states_by_zone': pincode_states,
                'all_states': sorted(all_states),
                'total_zones': len(pincode_states),
                'total_states': len(all_states)
            })
            
        except Exception as e:
            print(f"Get location states error: {e}")
            return jsonify({'success': False, 'message': 'Failed to retrieve states list'})

    @app.route('/api/locations/delivery-check/<pincode>')
    @login_required
    def api_location_delivery_check(pincode):
        """API: Check which locations can deliver to a specific pincode"""
        try:
            current_user = auth_controller.get_current_user()
            if not current_user:
                return jsonify({'success': False, 'message': 'Authentication required'})
            
            # Validate pincode
            if not pincode or len(pincode) != 6 or not pincode.isdigit():
                return jsonify({'success': False, 'message': 'Invalid pincode format'})
            
            # Get serviceable locations
            serviceable_locations = location_controller.get_serviceable_locations_for_user(pincode)
            
            if serviceable_locations['success']:
                return jsonify({
                    'success': True,
                    'pincode': pincode,
                    'serviceable_locations': serviceable_locations['locations'],
                    'total_locations': len(serviceable_locations['locations']),
                    'delivery_available': len(serviceable_locations['locations']) > 0
                })
            else:
                return jsonify(serviceable_locations)
                
        except Exception as e:
            print(f"Delivery check error: {e}")
            return jsonify({'success': False, 'message': 'Failed to check delivery availability'})

    @app.route('/api/locations/coverage-stats')
    @login_required
    @role_required('vendor_superadmin', 'vendor_admin')
    def api_location_coverage_stats():
        """API: Get delivery coverage statistics"""
        try:
            from models import Location
            
            stats = Location.get_delivery_statistics()
            
            return jsonify({
                'success': True,
                'coverage_stats': stats
            })
            
        except Exception as e:
            print(f"Coverage stats error: {e}")
            return jsonify({'success': False, 'message': 'Failed to retrieve coverage statistics'})

    @app.route('/api/locations/<location_id>/coverage')
    @login_required
    @role_required('vendor_superadmin', 'vendor_admin', 'vendor_normal')
    def api_location_coverage(location_id):
        """API: Get detailed coverage information for a specific location"""
        try:
            location = Location.get_by_id(location_id)
            if not location:
                return jsonify({'success': False, 'message': 'Location not found'})
            
            coverage_info = location.get_delivery_coverage_info()
            
            return jsonify({
                'success': True,
                'location_id': location_id,
                'location_name': location.name,
                'coverage_info': coverage_info
            })
            
        except Exception as e:
            print(f"Location coverage error: {e}")
            return jsonify({'success': False, 'message': 'Failed to retrieve location coverage'})

    @app.route('/api/locations/<location_id>/test-delivery', methods=['POST'])
    @login_required
    @role_required('vendor_superadmin', 'vendor_admin', 'vendor_normal')
    def api_test_location_delivery(location_id):
        """API: Test if a location can deliver to specific pincodes"""
        try:
            location = Location.get_by_id(location_id)
            if not location:
                return jsonify({'success': False, 'message': 'Location not found'})
            
            data = request.get_json()
            test_pincodes = data.get('pincodes', [])
            
            if not test_pincodes:
                return jsonify({'success': False, 'message': 'No pincodes provided for testing'})
            
            results = []
            for pincode in test_pincodes:
                can_deliver = location.can_deliver_to_pincode(pincode)
                results.append({
                    'pincode': pincode,
                    'can_deliver': can_deliver,
                    'zone': pincode[0] if len(pincode) == 6 else None
                })
            
            return jsonify({
                'success': True,
                'location_id': location_id,
                'location_name': location.name,
                'test_results': results,
                'total_tested': len(test_pincodes),
                'deliverable_count': sum(1 for r in results if r['can_deliver'])
            })
            
        except Exception as e:
            print(f"Test location delivery error: {e}")
            return jsonify({'success': False, 'message': 'Failed to test delivery'})

    @app.route('/api/locations/bulk-update-states', methods=['POST'])
    @login_required
    @role_required('vendor_superadmin', 'vendor_admin')
    def api_bulk_update_location_states():
        """API: Bulk update serviceable states for multiple locations"""
        try:
            data = request.get_json()
            updates = data.get('updates', [])
            
            if not updates:
                return jsonify({'success': False, 'message': 'No updates provided'})
            
            successful_updates = 0
            failed_updates = []
            
            for update in updates:
                try:
                    location_id = update.get('location_id')
                    new_states = update.get('serviceable_states', [])
                    
                    location = Location.get_by_id(location_id)
                    if not location:
                        failed_updates.append(f"Location {location_id} not found")
                        continue
                    
                    if location.update_serviceable_states(new_states):
                        successful_updates += 1
                    else:
                        failed_updates.append(f"Failed to update location {location.name}")
                        
                except Exception as e:
                    failed_updates.append(f"Error updating location {update.get('location_id', 'unknown')}: {str(e)}")
            
            return jsonify({
                'success': True,
                'message': f'Successfully updated {successful_updates} locations',
                'successful_updates': successful_updates,
                'failed_updates': failed_updates,
                'total_processed': len(updates)
            })
            
        except Exception as e:
            print(f"Bulk update location states error: {e}")
            return jsonify({'success': False, 'message': 'Failed to bulk update locations'})

    @app.route('/api/user/deliverable-locations')
    @login_required
    @role_required('customer_employee', 'customer_dept_head', 'customer_hr_admin')
    def api_user_deliverable_locations():
        """API: Get locations that can deliver to current user's branch"""
        try:
            current_user = auth_controller.get_current_user()
            
            # Get user's branch pincode
            user_pincode = None
            if hasattr(current_user, 'branch_id') and current_user.branch_id:
                from models import Branch
                branch = Branch.get_by_id(current_user.branch_id)
                if branch and branch.pincode:
                    user_pincode = branch.pincode
            
            if not user_pincode:
                return jsonify({
                    'success': False,
                    'message': 'User branch pincode not found. Please contact your HR admin to set up branch location.'
                })
            
            # Get deliverable locations
            result = location_controller.get_serviceable_locations_for_user(user_pincode)
            
            if result['success']:
                return jsonify({
                    'success': True,
                    'user_pincode': user_pincode,
                    'deliverable_locations': result['locations'],
                    'total_locations': len(result['locations']),
                    'delivery_available': len(result['locations']) > 0
                })
            else:
                return jsonify(result)
                
        except Exception as e:
            print(f"User deliverable locations error: {e}")
            return jsonify({'success': False, 'message': 'Failed to retrieve deliverable locations'})

    @app.route('/api/products/deliverable')
    @login_required
    @role_required('customer_employee', 'customer_dept_head', 'customer_hr_admin')
    def api_user_deliverable_products():
        """API: Get products that can be delivered to current user's location"""
        try:
            current_user = auth_controller.get_current_user()
            
            # Get user's branch pincode
            user_pincode = None
            if hasattr(current_user, 'branch_id') and current_user.branch_id:
                from models import Branch
                branch = Branch.get_by_id(current_user.branch_id)
                if branch and branch.pincode:
                    user_pincode = branch.pincode
            
            if not user_pincode:
                return jsonify({
                    'success': False,
                    'message': 'User branch pincode not found. Please contact your HR admin to set up branch location.'
                })
            
            # Get deliverable products
            deliverable_products = Product.get_products_for_user_pincode(user_pincode)
            
            # Convert to dict format
            products_list = []
            for product in deliverable_products:
                product_dict = product.to_dict()
                
                # Add location information
                location_names = []
                if hasattr(product, 'location_ids') and product.location_ids:
                    for location_id in product.location_ids:
                        location = Location.get_by_id(location_id)
                        if location and location.can_deliver_to_pincode(user_pincode):
                            location_names.append(location.name)
                
                product_dict['deliverable_from'] = location_names
                products_list.append(product_dict)
            
            return jsonify({
                'success': True,
                'user_pincode': user_pincode,
                'products': products_list,
                'total_products': len(products_list),
                'delivery_available': len(products_list) > 0
            })
            
        except Exception as e:
            print(f"User deliverable products error: {e}")
            return jsonify({'success': False, 'message': 'Failed to retrieve deliverable products'})

    # Add this route to test the location-based filtering
    @app.route('/api/locations/test-filtering/<pincode>')
    @login_required
    @role_required('vendor_superadmin', 'vendor_admin')
    def api_test_location_filtering(pincode):
        """API: Test location-based product filtering for a specific pincode"""
        try:
            # Validate pincode
            if not pincode or len(pincode) != 6 or not pincode.isdigit():
                return jsonify({'success': False, 'message': 'Invalid pincode format'})
            
            # Get serviceable locations
            serviceable_locations = Location.get_locations_for_pincode(pincode)
            
            # Get products from serviceable locations
            deliverable_products = []
            if serviceable_locations:
                serviceable_location_ids = [loc.location_id for loc in serviceable_locations]
                all_products = Product.get_all_active()
                
                for product in all_products:
                    product_locations = getattr(product, 'location_ids', [])
                    if not product_locations and hasattr(product, 'location_id') and product.location_id:
                        product_locations = [product.location_id]
                    
                    if any(loc_id in serviceable_location_ids for loc_id in product_locations):
                        deliverable_products.append({
                            'product_id': product.product_id,
                            'product_name': product.product_name,
                            'category': product.category,
                            'available_from': [loc.name for loc in serviceable_locations if loc.location_id in product_locations]
                        })
            
            return jsonify({
                'success': True,
                'test_pincode': pincode,
                'serviceable_locations': [{'id': loc.location_id, 'name': loc.name} for loc in serviceable_locations],
                'deliverable_products': deliverable_products,
                'location_count': len(serviceable_locations),
                'product_count': len(deliverable_products)
            })
            
        except Exception as e:
            print(f"Test location filtering error: {e}")
            return jsonify({'success': False, 'message': 'Failed to test location filtering'})
        
    # Add these routes to app.py

    @app.route('/api/customers/<customer_id>/deletion-preview')
    @login_required
    @role_required('vendor_superadmin')
    def api_customer_deletion_preview(customer_id):
        """API: Get customer deletion preview"""
        return jsonify(customer_controller.get_customer_deletion_preview(customer_id))

    @app.route('/api/customers/<customer_id>', methods=['DELETE'])
    @login_required
    @role_required('vendor_superadmin')
    def api_delete_customer(customer_id):
        """API: Delete customer and all associated data"""
        return jsonify(customer_controller.delete_customer(customer_id))

    @app.route('/api/customers/<customer_id>/restore', methods=['POST'])
    @login_required
    @role_required('vendor_superadmin')
    def api_restore_customer(customer_id):
        """API: Restore deleted customer"""
        return jsonify(customer_controller.restore_customer(customer_id))

    # REPLACE the existing api_customers route with this enhanced version:
    @app.route('/api/customers')
    @login_required
    def api_customers():
        """API: Get customers list - Enhanced with deletion support"""
        if request.method == 'GET':
            return jsonify(customer_controller.get_customers())
        elif request.method == 'POST':
            return jsonify(customer_controller.create_customer())

    return app


# Create Flask app instance
app = create_app()

if __name__ == '__main__':
    # Development server
    app.run(debug=True, host='0.0.0.0', port=3000)