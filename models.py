# Data Models - Office Supplies Vendor System
from datetime import datetime
import uuid
import hashlib
from config import config

class BaseModel:
    """Base model with common functionality"""
    
    def __init__(self):
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
    
    def to_dict(self):
        """Convert model to dictionary"""
        result = {}
        for key, value in self.__dict__.items():
            if isinstance(value, datetime):
                result[key] = value
            else:
                result[key] = value
        return result
    
    @classmethod
    # Replace the from_dict method in User class in models.py

    @classmethod
    def from_dict(cls, data):
        """Create user instance from dictionary - FIXED VERSION"""
        user = cls()
        for key, value in data.items():
            setattr(user, key, value)
        
        # Ensure required fields have default values if missing
        if not hasattr(user, 'username') or user.username is None:
            user.username = ''
        if not hasattr(user, 'role') or user.role is None:
            user.role = ''
        if not hasattr(user, 'full_name') or user.full_name is None:
            user.full_name = ''
        if not hasattr(user, 'is_active'):
            user.is_active = True
            
        return user
    
    def save(self):
        """Save model to database - to be implemented by subclasses"""
        raise NotImplementedError
    
    @classmethod
    def get_by_id(cls, doc_id):
        """Get model by ID - to be implemented by subclasses"""
        raise NotImplementedError

class User(BaseModel):
    """User model for authentication and user management"""
    
    def __init__(self, username=None, email=None, password_hash=None, role=None):
        super().__init__()
        self.user_id = str(uuid.uuid4())
        self.username = username
        self.email = email
        self.password_hash = password_hash
        self.role = role  # vendor_superadmin, vendor_admin, vendor_normal, customer_hr_admin, customer_dept_head, customer_employee
        self.first_name = None  # NEW FIELD
        self.last_name = None   # NEW FIELD
        self.full_name = None
        self.is_active = True
        self.last_login = None
        self.customer_id = None  # For customer users
        self.department_id = None  # For customer employees
        self.is_first_login = True
        self.password_reset_required = False
    
    @staticmethod
    def hash_password(password):
        """Hash password using SHA-256"""
        return hashlib.sha256(password.encode()).hexdigest()
    
    def verify_password(self, password):
        """Verify password against hash"""
        return self.password_hash == self.hash_password(password)
    
    def save(self):
        """Save user to Firebase"""
        try:
            self.updated_at = datetime.now()
            db = config.get_db()
            doc_ref = db.collection('users').document(self.user_id)
            doc_ref.set(self.to_dict())
            return True
        except Exception as e:
            print(f"Error saving user: {e}")
            return False
    
    @classmethod
    def get_by_id(cls, user_id):
        """Get user by ID"""
        try:
            db = config.get_db()
            doc = db.collection('users').document(user_id).get()
            if doc.exists:
                return cls.from_dict(doc.to_dict())
            return None
        except Exception as e:
            print(f"Error getting user by ID: {e}")
            return None
    
    @classmethod
    def get_by_username(cls, username):
        """Get user by username"""
        try:
            db = config.get_db()
            docs = db.collection('users').where('username', '==', username).limit(1).get()
            for doc in docs:
                return cls.from_dict(doc.to_dict())
            return None
        except Exception as e:
            print(f"Error getting user by username: {e}")
            return None

    @classmethod
    def get_by_department_id(cls, department_id):
        """Get users by department ID"""
        try:
            db = config.get_db()
            docs = db.collection('users').where('department_id', '==', department_id).get()
            users = []
            for doc in docs:
                users.append(cls.from_dict(doc.to_dict()))
            return users
        except Exception as e:
            print(f"Error getting users by department ID: {e}")
            return []

    @classmethod
    def get_by_customer_and_roles(cls, customer_id, roles):
        """Get users by customer ID and specific roles"""
        try:
            db = config.get_db()
            users = []
            
            # Query for each role separately since Firestore doesn't support 'in' with arrays
            for role in roles:
                docs = db.collection('users').where('customer_id', '==', customer_id).where('role', '==', role).get()
                for doc in docs:
                    users.append(cls.from_dict(doc.to_dict()))
            
            return users
        except Exception as e:
            print(f"Error getting users by customer and roles: {e}")
            return []
    
    @classmethod
    def get_by_email(cls, email):
        """Get user by email"""
        try:
            db = config.get_db()
            docs = db.collection('users').where('email', '==', email).limit(1).get()
            for doc in docs:
                return cls.from_dict(doc.to_dict())
            return None
        except Exception as e:
            print(f"Error getting user by email: {e}")
            return None
    
    @classmethod
    def get_by_customer_id(cls, customer_id):
        """Get users by customer ID - DEBUG VERSION"""
        try:
            db = config.get_db()
            docs = db.collection('users').where('customer_id', '==', customer_id).get()
            users = []
            print(f"DEBUG: Raw docs count: {len(list(docs))}")
            
            # Re-query since docs iterator is consumed
            docs = db.collection('users').where('customer_id', '==', customer_id).get()
            
            for doc in docs:
                user_data = doc.to_dict()
                print(f"DEBUG: Raw user data: {user_data}")
                user = cls.from_dict(user_data)
                print(f"DEBUG: Created user: username={user.username}, role={user.role}")
                users.append(user)
            return users
        except Exception as e:
            print(f"Error getting users by customer ID: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    @classmethod
    def create_vendor_superadmin(cls, username, email, password, full_name=None):
        """Create vendor superadmin user"""
        user = cls(
            username=username,
            email=email,
            password_hash=cls.hash_password(password),
            role='vendor_superadmin'
        )
        user.full_name = full_name
        user.is_first_login = False
        return user
    
    @classmethod
    def create_customer_hr_admin(cls, username, email, password, customer_id, full_name=None):
        """Create customer HR admin user"""
        user = cls(
            username=username,
            email=email,
            password_hash=cls.hash_password(password),
            role='customer_hr_admin'
        )
        user.full_name = full_name
        user.customer_id = customer_id
        user.is_first_login = True
        user.password_reset_required = True
        return user
    
    def update_last_login(self):
        """Update last login timestamp"""
        self.last_login = datetime.now()
        self.save()
    
    def change_password(self, new_password):
        """Change user password"""
        self.password_hash = self.hash_password(new_password)
        self.is_first_login = False
        self.password_reset_required = False
        return self.save()

class Customer(BaseModel):
    """Customer model for company information"""
    
    def __init__(self):
        super().__init__()
        self.customer_id = self.generate_customer_id()
        self.company_name = None
        self.email = None
        self.postal_address = None
        self.primary_phone = None
        self.alternate_phone = None
        self.agreement_file_url = None
        self.is_active = True
        self.hr_admin_created = False
    
    @staticmethod
    def generate_customer_id():
        """Generate 5-digit customer ID"""
        import random
        return f"{random.randint(10000, 99999)}"
    
    def save(self):
        """Save customer to Firebase"""
        try:
            self.updated_at = datetime.now()
            db = config.get_db()
            doc_ref = db.collection('customers').document(self.customer_id)
            doc_ref.set(self.to_dict())
            return True
        except Exception as e:
            print(f"Error saving customer: {e}")
            return False
    
    @classmethod
    def get_by_id(cls, customer_id):
        """Get customer by ID"""
        try:
            db = config.get_db()
            doc = db.collection('customers').document(customer_id).get()
            if doc.exists:
                return cls.from_dict(doc.to_dict())
            return None
        except Exception as e:
            print(f"Error getting customer by ID: {e}")
            return None
    
    @classmethod
    def get_by_email(cls, email):
        """Get customer by email"""
        try:
            db = config.get_db()
            docs = db.collection('customers').where('email', '==', email).limit(1).get()
            for doc in docs:
                return cls.from_dict(doc.to_dict())
            return None
        except Exception as e:
            print(f"Error getting customer by email: {e}")
            return None
    
    @classmethod
    def get_all_active(cls):
        """Get all active customers"""
        try:
            db = config.get_db()
            docs = db.collection('customers').where('is_active', '==', True).get()
            customers = []
            for doc in docs:
                customers.append(cls.from_dict(doc.to_dict()))
            return customers
        except Exception as e:
            print(f"Error getting active customers: {e}")
            return []
    
    @classmethod
    def get_all(cls):
        """Get all customers"""
        try:
            db = config.get_db()
            docs = db.collection('customers').get()
            customers = []
            for doc in docs:
                customers.append(cls.from_dict(doc.to_dict()))
            return customers
        except Exception as e:
            print(f"Error getting all customers: {e}")
            return []
    
    # Updated Customer class in models.py - Add this method to the Customer class

    def create_hr_admin_user(self, send_email=False):
        """Create HR admin user with auto-generated password"""
        try:
            # Generate temporary password
            import uuid
            temp_password = f"temp_{uuid.uuid4().hex[:8]}"
            
            # Generate username from customer ID
            username = f"{self.customer_id}_hr"
            
            hr_user = User.create_customer_hr_admin(
                username=username,
                email=self.email,
                password=temp_password,
                customer_id=self.customer_id,
                full_name=f"{self.company_name} HR Admin"
            )
            
            if hr_user.save():
                self.hr_admin_created = True
                self.save()
                
                if send_email:
                    # Send welcome email
                    from controllers.auth_controller import auth_controller
                    auth_controller.send_welcome_email(hr_user, temp_password)
                
                return {'success': True, 'user': hr_user, 'temp_password': temp_password}
            else:
                return {'success': False, 'message': 'Failed to create HR admin user'}
                
        except Exception as e:
            print(f"Error creating HR admin user: {e}")
            return {'success': False, 'message': 'Failed to create HR admin user'}

class Product(BaseModel):
    """Product model for inventory management"""
    
    def __init__(self):
        super().__init__()
        self.product_id = str(uuid.uuid4())
        self.item_no = None  # Item number/SKU
        self.category = None
        self.product_name = None
        self.product_make = None
        self.product_model = None
        self.description = None
        self.price = 0.0
        self.quantity = 0
        self.gst_rate = 18.0  # Default GST rate
        self.hsn_code = None
        self.is_active = True
        self.low_stock_threshold = 10
        self.image_urls = []
        self.product_specifications = {}
    
    def save(self):
        """Save product to Firebase"""
        try:
            self.updated_at = datetime.now()
            db = config.get_db()
            doc_ref = db.collection('products').document(self.product_id)
            doc_ref.set(self.to_dict())
            return True
        except Exception as e:
            print(f"Error saving product: {e}")
            return False
    
    @classmethod
    def get_by_id(cls, product_id):
        """Get product by ID"""
        try:
            db = config.get_db()
            doc = db.collection('products').document(product_id).get()
            if doc.exists:
                return cls.from_dict(doc.to_dict())
            return None
        except Exception as e:
            print(f"Error getting product by ID: {e}")
            return None
    
    @classmethod
    def get_by_item_no(cls, item_no):
        """Get product by item number"""
        try:
            db = config.get_db()
            docs = db.collection('products').where('item_no', '==', item_no).limit(1).get()
            for doc in docs:
                return cls.from_dict(doc.to_dict())
            return None
        except Exception as e:
            print(f"Error getting product by item number: {e}")
            return None
    
    @classmethod
    def get_all_active(cls):
        """Get all active products"""
        try:
            db = config.get_db()
            docs = db.collection('products').where('is_active', '==', True).get()
            products = []
            for doc in docs:
                products.append(cls.from_dict(doc.to_dict()))
            return products
        except Exception as e:
            print(f"Error getting active products: {e}")
            return []
    
    @classmethod
    def get_low_stock_products(cls):
        """Get products with low stock"""
        try:
            products = cls.get_all_active()
            low_stock = []
            for product in products:
                if product.quantity <= product.low_stock_threshold:
                    low_stock.append(product)
            return low_stock
        except Exception as e:
            print(f"Error getting low stock products: {e}")
            return []
    
    @classmethod
    def search_products(cls, search_term, category=None):
        """Search products by name, description, or category"""
        try:
            products = cls.get_all_active()
            results = []
            
            search_term = search_term.lower() if search_term else ''
            
            for product in products:
                match = False
                
                # Search in product name
                if search_term in product.product_name.lower():
                    match = True
                
                # Search in description
                if product.description and search_term in product.description.lower():
                    match = True
                
                # Search in category
                if product.category and search_term in product.category.lower():
                    match = True
                
                # Search in make/model
                if product.product_make and search_term in product.product_make.lower():
                    match = True
                
                if product.product_model and search_term in product.product_model.lower():
                    match = True
                
                # Filter by category if specified
                if category and product.category != category:
                    match = False
                
                if match:
                    results.append(product)
            
            return results
        except Exception as e:
            print(f"Error searching products: {e}")
            return []
    
    def update_quantity(self, new_quantity):
        """Update product quantity"""
        self.quantity = new_quantity
        return self.save()
    
    def reduce_quantity(self, amount):
        """Reduce product quantity"""
        if self.quantity >= amount:
            self.quantity -= amount
            return self.save()
        return False
    
    def is_low_stock(self):
        """Check if product is low on stock"""
        return self.quantity <= self.low_stock_threshold

class Order(BaseModel):
    """Order model for order management"""
    
    def __init__(self):
        super().__init__()
        self.order_id = self.generate_order_id()
        self.customer_id = None
        self.user_id = None  # Employee who created the order
        self.department_id = None
        self.status = 'draft'  # draft, pending_dept_approval, pending_hr_approval, approved, packed, ready_for_dispatch, dispatched, cancelled
        self.items = []  # List of order items
        self.total_amount = 0.0
        self.total_gst = 0.0
        self.comments = []  # List of comments/approvals
        self.packed_items = {}  # Track which items are packed
        self.dispatch_approved_by = None
        self.dispatched_by = None
        self.dispatch_date = None
    
    @staticmethod
    def generate_order_id():
        """Generate unique order ID"""
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        random_part = uuid.uuid4().hex[:6].upper()
        return f"ORD{timestamp}{random_part}"
    
    def add_item(self, product_id, quantity, price):
        """Add item to order"""
        item = {
            'product_id': product_id,
            'quantity': quantity,
            'price': price,
            'total': quantity * price
        }
        self.items.append(item)
        self.calculate_totals()
    
    def calculate_totals(self):
        """Calculate order totals"""
        subtotal = sum(item['total'] for item in self.items)
        
        # Calculate GST (fetch GST rates from products)
        total_gst = 0
        for item in self.items:
            product = Product.get_by_id(item['product_id'])
            if product:
                gst_amount = (item['total'] * product.gst_rate) / 100
                total_gst += gst_amount
        
        self.total_gst = total_gst
        self.total_amount = subtotal + total_gst
    
    def add_comment(self, user_id, role, action, message):
        """Add comment/approval to order"""
        comment = {
            'user_id': user_id,
            'role': role,
            'action': action,  # approved, rejected, commented
            'message': message,
            'timestamp': datetime.now()
        }
        self.comments.append(comment)
    
    def save(self):
        """Save order to Firebase"""
        try:
            self.updated_at = datetime.now()
            db = config.get_db()
            doc_ref = db.collection('orders').document(self.order_id)
            doc_ref.set(self.to_dict())
            return True
        except Exception as e:
            print(f"Error saving order: {e}")
            return False
    
    @classmethod
    def get_by_id(cls, order_id):
        """Get order by ID"""
        try:
            db = config.get_db()
            doc = db.collection('orders').document(order_id).get()
            if doc.exists:
                return cls.from_dict(doc.to_dict())
            return None
        except Exception as e:
            print(f"Error getting order by ID: {e}")
            return None
    
    @classmethod
    def get_by_customer_id(cls, customer_id):
        """Get orders by customer ID"""
        try:
            db = config.get_db()
            docs = db.collection('orders').where('customer_id', '==', customer_id).get()
            orders = []
            for doc in docs:
                orders.append(cls.from_dict(doc.to_dict()))
            return orders
        except Exception as e:
            print(f"Error getting orders by customer ID: {e}")
            return []
        
    @classmethod
    def get_active_by_customer_id(cls, customer_id):
        """Get only active departments by customer ID"""
        try:
            db = config.get_db()
            docs = db.collection('departments').where('customer_id', '==', customer_id).where('is_active', '==', True).get()
            departments = []
            for doc in docs:
                departments.append(cls.from_dict(doc.to_dict()))
            return departments
        except Exception as e:
            print(f"Error getting active departments by customer ID: {e}")
            return []
    
    @classmethod
    def get_by_user_id(cls, user_id):
        """Get orders by user ID"""
        try:
            db = config.get_db()
            docs = db.collection('orders').where('user_id', '==', user_id).get()
            orders = []
            for doc in docs:
                orders.append(cls.from_dict(doc.to_dict()))
            return orders
        except Exception as e:
            print(f"Error getting orders by user ID: {e}")
            return []
    
    @classmethod
    def get_by_status(cls, status):
        """Get orders by status"""
        try:
            db = config.get_db()
            docs = db.collection('orders').where('status', '==', status).get()
            orders = []
            for doc in docs:
                orders.append(cls.from_dict(doc.to_dict()))
            return orders
        except Exception as e:
            print(f"Error getting orders by status: {e}")
            return []
    
    def update_status(self, new_status, user_id=None, comments=None):
        """Update order status"""
        old_status = self.status
        self.status = new_status
        
        if comments and user_id:
            self.add_comment(user_id, 'system', 'status_change', f"Status changed from {old_status} to {new_status}. {comments}")
        
        return self.save()
    
    def can_be_approved_by_dept_head(self, user):
        """Check if order can be approved by department head"""
        return (self.status == 'pending_dept_approval' and 
                user.role == 'customer_dept_head' and 
                user.customer_id == self.customer_id)
    
    def can_be_approved_by_hr(self, user):
        """Check if order can be approved by HR"""
        return (self.status == 'pending_hr_approval' and 
                user.role == 'customer_hr_admin' and 
                user.customer_id == self.customer_id)

class Department(BaseModel):
    """Department model for customer organization"""
    
    def __init__(self):
        super().__init__()
        self.department_id = str(uuid.uuid4())
        self.customer_id = None
        self.name = None
        self.description = None
        self.department_head_id = None
        self.is_active = True
    
    def save(self):
        """Save department to Firebase"""
        try:
            self.updated_at = datetime.now()
            db = config.get_db()
            doc_ref = db.collection('departments').document(self.department_id)
            doc_ref.set(self.to_dict())
            return True
        except Exception as e:
            print(f"Error saving department: {e}")
            return False

    @classmethod
    def get_by_id(cls, department_id):
        """Get department by ID"""
        try:
            db = config.get_db()
            doc = db.collection('departments').document(department_id).get()
            if doc.exists:
                return cls.from_dict(doc.to_dict())
            return None
        except Exception as e:
            print(f"Error getting department by ID: {e}")
            return None

    @classmethod
    def get_by_customer_id(cls, customer_id):
        """Get departments by customer ID"""
        try:
            db = config.get_db()
            docs = db.collection('departments').where('customer_id', '==', customer_id).where('is_active', '==', True).get()
            departments = []
            for doc in docs:
                departments.append(cls.from_dict(doc.to_dict()))
            return departments
        except Exception as e:
            print(f"Error getting departments by customer ID: {e}")
            return []
    
    @classmethod
    def get_by_customer_id(cls, customer_id):
        """Get departments by customer ID"""
        try:
            db = config.get_db()
            docs = db.collection('departments').where('customer_id', '==', customer_id).get()
            departments = []
            for doc in docs:
                departments.append(cls.from_dict(doc.to_dict()))
            return departments
        except Exception as e:
            print(f"Error getting departments by customer ID: {e}")
            return []
        
        # Add these methods to the Department class in models.py

    @classmethod
    def get_by_id(cls, department_id):
        """Get department by ID"""
        try:
            db = config.get_db()
            doc = db.collection('departments').document(department_id).get()
            if doc.exists:
                return cls.from_dict(doc.to_dict())
            return None
        except Exception as e:
            print(f"Error getting department by ID: {e}")
            return None

    @classmethod
    def get_by_department_id(cls, department_id):
        """Get users by department ID"""
        try:
            db = config.get_db()
            docs = db.collection('users').where('department_id', '==', department_id).get()
            users = []
            for doc in docs:
                users.append(cls.from_dict(doc.to_dict()))
            return users
        except Exception as e:
            print(f"Error getting users by department ID: {e}")
            return []

class VendorSettings(BaseModel):
    """Vendor settings model for system configuration"""
    
    def __init__(self):
        super().__init__()
        self.settings_id = 'vendor_settings'  # Singleton
        self.company_name = None
        self.postal_address = None
        self.primary_contact_name = None
        self.primary_contact_phone = None
        self.alternate_contact_name = None
        self.alternate_contact_phone = None
        self.email_address = None
        self.email_username = None
        self.email_password = None
        self.email_server_url = None
        self.email_port = 587
        self.email_use_tls = True
    
    def save(self):
        """Save vendor settings to Firebase"""
        try:
            self.updated_at = datetime.now()
            db = config.get_db()
            doc_ref = db.collection('vendor_settings').document(self.settings_id)
            doc_ref.set(self.to_dict())
            return True
        except Exception as e:
            print(f"Error saving vendor settings: {e}")
            return False
    
    @classmethod
    def get_settings(cls):
        """Get vendor settings (singleton)"""
        try:
            db = config.get_db()
            doc = db.collection('vendor_settings').document('vendor_settings').get()
            if doc.exists:
                return cls.from_dict(doc.to_dict())
            else:
                # Create default settings
                settings = cls()
                settings.save()
                return settings
        except Exception as e:
            print(f"Error getting vendor settings: {e}")
            # Return default settings
            return cls()
    
    @classmethod
    def initialize_default_settings(cls):
        """Initialize default vendor settings"""
        settings = cls.get_settings()
        if not settings.company_name:
            settings.company_name = "Office Supplies Vendor"
            settings.email_port = 587
            settings.email_use_tls = True
            settings.save()
        return settings