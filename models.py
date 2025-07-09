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
        """Create instance from dictionary - Enhanced with deletion support"""
        instance = cls()
        for key, value in data.items():
            setattr(instance, key, value)
        
        # Ensure deletion fields have default values if missing
        if not hasattr(instance, 'is_deleted'):
            instance.is_deleted = False
        if not hasattr(instance, 'deleted_at'):
            instance.deleted_at = None
        if not hasattr(instance, 'deleted_by'):
            instance.deleted_by = None
            
        return instance
    
    def save(self):
        """Save model to database - to be implemented by subclasses"""
        raise NotImplementedError
    
    @classmethod
    def get_by_id(cls, doc_id):
        """Get model by ID - to be implemented by subclasses"""
        raise NotImplementedError

class Location(BaseModel):
    """Enhanced Location model with state-based delivery zones"""
    
    def __init__(self):
        super().__init__()
        self.location_id = str(uuid.uuid4())
        self.name = None
        self.address = None
        self.pincode = None  # Location's own pincode
        self.phone = None
        self.manager_name = None
        self.description = None
        self.is_active = True
        self.serviceable_states = []  # List of states this location can service
        self.serviceable_pincodes = []  # Auto-generated from states
        
        
        # Indian states grouped by pincode zones
        self.pincode_states = {
            '1': ['Delhi NCR', 'Haryana', 'Himachal Pradesh', 'Punjab', 'UT/Chandigarh', 'UT/Jammu and Kashmir', 'UT/Ladakh'],
            '2': ['Uttarakhand', 'Uttar Pradesh'],
            '3': ['Gujarat', 'Rajasthan', 'UT/Dadra, Nagar Haveli, Daman & Diu'],
            '4': ['Chhattisgarh', 'Goa', 'Madhya Pradesh', 'Maharashtra'],
            '5': ['Andhra Pradesh', 'Karnataka', 'Telangana'],
            '6': ['Kerala', 'Tamil Nadu', 'UT/Puducherry', 'UT/Lakshadweep'],
            '7': ['Arunachal Pradesh', 'Assam', 'Manipur', 'Meghalaya', 'Mizoram', 'Nagaland', 'Odisha', 'Sikkim', 'Tripura', 'West Bengal', 'UT/Andaman and Nicobar Islands'],
            '8': ['Bihar', 'Jharkhand']
        }
    
    def save(self):
        """Save location to Firebase with auto-generated serviceable pincodes"""
        try:
            # Auto-generate serviceable pincodes from states
            if self.serviceable_states:
                self.serviceable_pincodes = self.generate_pincodes_from_states(self.serviceable_states)
            
            self.updated_at = datetime.now()
            db = config.get_db()
            doc_ref = db.collection('locations').document(self.location_id)
            doc_ref.set(self.to_dict())
            return True
        except Exception as e:
            print(f"Error saving location: {e}")
            return False
    
    def generate_pincodes_from_states(self, selected_states):
        """Generate list of pincode zones from selected states"""
        try:
            serviceable_zones = []
            
            for zone, states in self.pincode_states.items():
                if any(state in selected_states for state in states):
                    serviceable_zones.append(zone)
            
            return serviceable_zones
            
        except Exception as e:
            print(f"Generate pincodes from states error: {e}")
            return []
    
    def can_deliver_to_pincode(self, pincode):
        """Check if this location can deliver to a specific pincode"""
        if not pincode or len(pincode) != 6 or not pincode.isdigit():
            return False
        
        # Get the first digit (zone) from the pincode
        pincode_zone = pincode[0]
        
        # Check if this zone is in our serviceable zones
        if pincode_zone in self.serviceable_pincodes:
            return True
        
        # Alternative check: see if any state in the pincode zone is serviceable
        states_in_zone = self.pincode_states.get(pincode_zone, [])
        for state in states_in_zone:
            if state in self.serviceable_states:
                return True
        
        return False
    
    def can_deliver_to_state(self, state_name):
        """Check if this location can deliver to a specific state"""
        return state_name in self.serviceable_states
    
    def get_delivery_zones(self):
        """Get all pincode zones this location can deliver to"""
        return self.serviceable_pincodes
    
    def get_delivery_states(self):
        """Get all states this location can deliver to"""
        return self.serviceable_states
    
    def get_delivery_coverage_info(self):
        """Get comprehensive delivery coverage information"""
        try:
            coverage_info = {
                'zones': self.serviceable_pincodes,
                'states': self.serviceable_states,
                'zone_details': {}
            }
            
            # Add zone details
            for zone in self.serviceable_pincodes:
                states_in_zone = self.pincode_states.get(zone, [])
                serviceable_states_in_zone = [state for state in states_in_zone if state in self.serviceable_states]
                
                coverage_info['zone_details'][zone] = {
                    'all_states': states_in_zone,
                    'serviceable_states': serviceable_states_in_zone,
                    'coverage_percentage': (len(serviceable_states_in_zone) / len(states_in_zone)) * 100 if states_in_zone else 0
                }
            
            return coverage_info
            
        except Exception as e:
            print(f"Error getting delivery coverage info: {e}")
            return {
                'zones': [],
                'states': [],
                'zone_details': {}
            }
    
    @classmethod
    def get_locations_for_pincode(cls, pincode):
        """Get all locations that can deliver to a specific pincode"""
        try:
            if not pincode or len(pincode) != 6 or not pincode.isdigit():
                return []
            
            locations = cls.get_all_active()
            serviceable_locations = []
            
            for location in locations:
                if location.can_deliver_to_pincode(pincode):
                    serviceable_locations.append(location)
            
            print(f"Found {len(serviceable_locations)} locations that can deliver to pincode {pincode}")
            return serviceable_locations
            
        except Exception as e:
            print(f"Error getting locations for pincode: {e}")
            return []
    
    @classmethod
    def get_locations_for_state(cls, state_name):
        """Get all locations that can deliver to a specific state"""
        try:
            locations = cls.get_all_active()
            serviceable_locations = []
            
            for location in locations:
                if location.can_deliver_to_state(state_name):
                    serviceable_locations.append(location)
            
            return serviceable_locations
            
        except Exception as e:
            print(f"Error getting locations for state: {e}")
            return []
    
    @classmethod
    def get_locations_for_zone(cls, zone):
        """Get all locations that can deliver to a specific pincode zone"""
        try:
            locations = cls.get_all_active()
            serviceable_locations = []
            
            for location in locations:
                if zone in location.serviceable_pincodes:
                    serviceable_locations.append(location)
            
            return serviceable_locations
            
        except Exception as e:
            print(f"Error getting locations for zone: {e}")
            return []
    
    def update_serviceable_states(self, new_states):
        """Update serviceable states and regenerate pincodes"""
        try:
            if not isinstance(new_states, list):
                return False
            
            self.serviceable_states = new_states
            self.serviceable_pincodes = self.generate_pincodes_from_states(new_states)
            
            return self.save()
            
        except Exception as e:
            print(f"Error updating serviceable states: {e}")
            return False
    
    def add_serviceable_state(self, state_name):
        """Add a single state to serviceable states"""
        try:
            if state_name not in self.serviceable_states:
                self.serviceable_states.append(state_name)
                self.serviceable_pincodes = self.generate_pincodes_from_states(self.serviceable_states)
                return self.save()
            return True
            
        except Exception as e:
            print(f"Error adding serviceable state: {e}")
            return False
    
    def remove_serviceable_state(self, state_name):
        """Remove a single state from serviceable states"""
        try:
            if state_name in self.serviceable_states:
                self.serviceable_states.remove(state_name)
                self.serviceable_pincodes = self.generate_pincodes_from_states(self.serviceable_states)
                return self.save()
            return True
            
        except Exception as e:
            print(f"Error removing serviceable state: {e}")
            return False
    
    @classmethod
    def get_by_id(cls, location_id):
        """Get location by ID"""
        try:
            db = config.get_db()
            doc = db.collection('locations').document(location_id).get()
            if doc.exists:
                return cls.from_dict(doc.to_dict())
            return None
        except Exception as e:
            print(f"Error getting location by ID: {e}")
            return None
    
    @classmethod
    def get_by_name(cls, name):
        """Get location by name"""
        try:
            db = config.get_db()
            docs = db.collection('locations').where('name', '==', name).limit(1).get()
            for doc in docs:
                return cls.from_dict(doc.to_dict())
            return None
        except Exception as e:
            print(f"Error getting location by name: {e}")
            return None
    
    @classmethod
    def get_all_active(cls):
        """Get all active locations"""
        try:
            db = config.get_db()
            docs = db.collection('locations').where('is_active', '==', True).get()
            locations = []
            for doc in docs:
                locations.append(cls.from_dict(doc.to_dict()))
            return locations
        except Exception as e:
            print(f"Error getting active locations: {e}")
            return []
    
    @classmethod
    def get_all(cls):
        """Get all locations"""
        try:
            db = config.get_db()
            docs = db.collection('locations').get()
            locations = []
            for doc in docs:
                locations.append(cls.from_dict(doc.to_dict()))
            return locations
        except Exception as e:
            print(f"Error getting all locations: {e}")
            return []
    
    @classmethod
    def get_delivery_statistics(cls):
        """Get comprehensive delivery statistics across all locations"""
        try:
            locations = cls.get_all_active()
            
            stats = {
                'total_active_locations': len(locations),
                'total_serviceable_states': set(),
                'total_serviceable_zones': set(),
                'coverage_by_zone': {},
                'coverage_by_state': {},
                'locations_without_coverage': []
            }
            
            # Pincode states mapping
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
            
            # Initialize zone and state coverage
            for zone in pincode_states.keys():
                stats['coverage_by_zone'][zone] = 0
            
            all_states = [state for states in pincode_states.values() for state in states]
            for state in all_states:
                stats['coverage_by_state'][state] = 0
            
            # Process each location
            for location in locations:
                if not location.serviceable_states:
                    stats['locations_without_coverage'].append(location.name)
                    continue
                
                # Add to total sets
                stats['total_serviceable_states'].update(location.serviceable_states)
                stats['total_serviceable_zones'].update(location.serviceable_pincodes)
                
                # Count coverage
                for zone in location.serviceable_pincodes:
                    stats['coverage_by_zone'][zone] += 1
                
                for state in location.serviceable_states:
                    stats['coverage_by_state'][state] += 1
            
            # Convert sets to lists and add counts
            stats['total_serviceable_states'] = list(stats['total_serviceable_states'])
            stats['total_serviceable_zones'] = list(stats['total_serviceable_zones'])
            stats['unique_serviceable_states_count'] = len(stats['total_serviceable_states'])
            stats['unique_serviceable_zones_count'] = len(stats['total_serviceable_zones'])
            
            return stats
            
        except Exception as e:
            print(f"Error getting delivery statistics: {e}")
            return {}
    
    def to_dict(self):
        """Convert location to dictionary with additional fields"""
        try:
            data = super().to_dict()
            
            # Ensure serviceable_states and serviceable_pincodes are lists
            if not isinstance(data.get('serviceable_states'), list):
                data['serviceable_states'] = []
            
            if not isinstance(data.get('serviceable_pincodes'), list):
                data['serviceable_pincodes'] = []
            
            # Add computed fields
            data['delivery_coverage'] = self.get_delivery_coverage_info()
            data['serviceable_states_count'] = len(data['serviceable_states'])
            data['serviceable_zones_count'] = len(data['serviceable_pincodes'])
            
            return data
            
        except Exception as e:
            print(f"Error converting location to dict: {e}")
            return super().to_dict()
    
    @classmethod
    def from_dict(cls, data):
        """Create location instance from dictionary"""
        try:
            location = cls()
            for key, value in data.items():
                if key == 'pincode_states':
                    # Don't set pincode_states from data as it's a class constant
                    continue
                setattr(location, key, value)
            
            # Ensure required fields have default values
            if not hasattr(location, 'serviceable_states') or location.serviceable_states is None:
                location.serviceable_states = []
            
            if not hasattr(location, 'serviceable_pincodes') or location.serviceable_pincodes is None:
                location.serviceable_pincodes = []
            
            if not hasattr(location, 'is_active'):
                location.is_active = True
            
            return location
            
        except Exception as e:
            print(f"Error creating location from dict: {e}")
            # Return a basic location instance
            location = cls()
            location.location_id = data.get('location_id', str(uuid.uuid4()))
            location.name = data.get('name', 'Unknown Location')
            location.serviceable_states = data.get('serviceable_states', [])
            location.serviceable_pincodes = data.get('serviceable_pincodes', [])
            return location

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
        self.branch_id = None
        # NEW DELETION FIELDS
        self.is_deleted = False
        self.deleted_at = None
        self.deleted_by = None   

    @classmethod
    def get_by_branch_id(cls, branch_id):
        """Get users by branch ID"""
        try:
            db = config.get_db()
            docs = db.collection('users').where('branch_id', '==', branch_id).get()
            users = []
            for doc in docs:
                users.append(cls.from_dict(doc.to_dict()))
            return users
        except Exception as e:
            print(f"Error getting users by branch ID: {e}")
            return []
    
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
        self.company_alias = None
        # NEW DELETION FIELDS
        self.is_deleted = False
        self.deleted_at = None
        self.deleted_by = None
        self.restored_at = None
        self.restored_by = None
    
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
        
        # Add these methods to the Customer class:
    @classmethod
    def get_all_including_deleted(cls):
        """Get all customers including deleted ones"""
        try:
            db = config.get_db()
            docs = db.collection('customers').get()
            customers = []
            for doc in docs:
                customers.append(cls.from_dict(doc.to_dict()))
            return customers
        except Exception as e:
            print(f"Error getting all customers including deleted: {e}")
            return []

    @classmethod
    def get_deleted_customers(cls):
        """Get only deleted customers"""
        try:
            db = config.get_db()
            docs = db.collection('customers').where('is_deleted', '==', True).get()
            customers = []
            for doc in docs:
                customers.append(cls.from_dict(doc.to_dict()))
            return customers
        except Exception as e:
            print(f"Error getting deleted customers: {e}")
            return []

    def is_customer_deleted(self):
        """Check if customer is deleted"""
        return getattr(self, 'is_deleted', False)

class Branch(BaseModel):
    """Branch model for customer organization locations"""
    
    def __init__(self):
        super().__init__()
        self.branch_id = str(uuid.uuid4())
        self.customer_id = None
        self.name = None
        self.address = None
        self.pincode = None  # NEW FIELD: 6-digit pincode
        self.phone = None
        self.email = None
        self.manager_name = None
        self.is_active = True
        # NEW DELETION FIELDS
        self.is_deleted = False
        self.deleted_at = None
        self.deleted_by = None
    
    def save(self):
        """Save branch to Firebase"""
        try:
            self.updated_at = datetime.now()
            db = config.get_db()
            doc_ref = db.collection('branches').document(self.branch_id)
            doc_ref.set(self.to_dict())
            return True
        except Exception as e:
            print(f"Error saving branch: {e}")
            return False
    
    @classmethod
    def get_by_id(cls, branch_id):
        """Get branch by ID"""
        try:
            db = config.get_db()
            doc = db.collection('branches').document(branch_id).get()
            if doc.exists:
                return cls.from_dict(doc.to_dict())
            return None
        except Exception as e:
            print(f"Error getting branch by ID: {e}")
            return None
    
    @classmethod
    def get_by_customer_id(cls, customer_id):
        """Get branches by customer ID"""
        try:
            db = config.get_db()
            docs = db.collection('branches').where('customer_id', '==', customer_id).get()
            branches = []
            for doc in docs:
                branches.append(cls.from_dict(doc.to_dict()))
            return branches
        except Exception as e:
            print(f"Error getting branches by customer ID: {e}")
            return []

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
        self.location_ids = []  # CHANGED: Now supports multiple locations
        # Keep location_id for backward compatibility
        self.location_id = None  # Will be deprecated but kept for existing data
    
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
    def get_products_for_user_pincode(cls, user_pincode):
        """Get products that can be delivered to user's pincode"""
        try:
            if not user_pincode or len(user_pincode) != 6:
                return []
            
            # Get serviceable locations for this pincode
            from models import Location
            serviceable_locations = Location.get_locations_for_pincode(user_pincode)
            serviceable_location_ids = [loc.location_id for loc in serviceable_locations]
            
            if not serviceable_location_ids:
                return []
            
            # Get all active products
            all_products = cls.get_all_active()
            
            # Filter products that are available from serviceable locations
            deliverable_products = []
            for product in all_products:
                product_locations = getattr(product, 'location_ids', [])
                if not product_locations and hasattr(product, 'location_id') and product.location_id:
                    # Backward compatibility
                    product_locations = [product.location_id]
                
                # Check if any of the product's locations are serviceable
                if any(loc_id in serviceable_location_ids for loc_id in product_locations):
                    deliverable_products.append(product)
            
            return deliverable_products
            
        except Exception as e:
            print(f"Error getting products for user pincode: {e}")
            return []

    @classmethod
    def get_products_by_location_ids(cls, location_ids):
        """Get products that are available at any of the specified locations"""
        try:
            db = config.get_db()
            products = []
            
            # Get all active products
            docs = db.collection('products').where('is_active', '==', True).get()
            
            for doc in docs:
                product_data = doc.to_dict()
                product = cls.from_dict(product_data)
                
                # Check if product is in any of the specified locations
                product_locations = getattr(product, 'location_ids', [])
                if not product_locations and hasattr(product, 'location_id') and product.location_id:
                    # Backward compatibility
                    product_locations = [product.location_id]
                
                if any(loc_id in location_ids for loc_id in product_locations):
                    products.append(product)
            
            return products
        except Exception as e:
            print(f"Error getting products by location IDs: {e}")
            return []

    def is_deliverable_to_pincode(self, pincode):
        """Check if this product can be delivered to a specific pincode"""
        try:
            if not pincode or len(pincode) != 6:
                return False
            
            # Get product locations
            product_locations = getattr(self, 'location_ids', [])
            if not product_locations and hasattr(self, 'location_id') and self.location_id:
                product_locations = [self.location_id]
            
            if not product_locations:
                return False
            
            # Check if any of the product's locations can deliver to this pincode
            from models import Location
            for location_id in product_locations:
                location = Location.get_by_id(location_id)
                if location and location.can_deliver_to_pincode(pincode):
                    return True
            
            return False
            
        except Exception as e:
            print(f"Error checking product deliverability to pincode: {e}")
            return False

    def get_serviceable_locations(self):
        """Get all locations that carry this product"""
        try:
            from models import Location
            
            product_locations = getattr(self, 'location_ids', [])
            if not product_locations and hasattr(self, 'location_id') and self.location_id:
                product_locations = [self.location_id]
            
            locations = []
            for location_id in product_locations:
                location = Location.get_by_id(location_id)
                if location:
                    locations.append(location)
            
            return locations
            
        except Exception as e:
            print(f"Error getting serviceable locations for product: {e}")
            return []
    
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
        """Get all active products - DEBUG VERSION"""
        try:
            print("Getting all active products from database...")
            db = config.get_db()
            docs = db.collection('products').where('is_active', '==', True).get()
            
            products = []
            doc_count = 0
            
            for doc in docs:
                doc_count += 1
                try:
                    product_data = doc.to_dict()
                    print(f"Processing product {doc_count}: {product_data.get('product_name', 'Unknown')}")
                    product = cls.from_dict(product_data)
                    products.append(product)
                except Exception as e:
                    print(f"Error processing product document {doc.id}: {e}")
                    continue
            
            print(f"Successfully loaded {len(products)} active products")
            return products
            
        except Exception as e:
            print(f"Error getting active products: {e}")
            import traceback
            traceback.print_exc()
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
    
    @classmethod
    def get_by_location_id(cls, location_id):
        """Get products by location ID"""
        try:
            db = config.get_db()
            docs = db.collection('products').where('location_id', '==', location_id).where('is_active', '==', True).get()
            products = []
            for doc in docs:
                products.append(cls.from_dict(doc.to_dict()))
            return products
        except Exception as e:
            print(f"Error getting products by location ID: {e}")
            return []

    @classmethod
    def get_all_active_with_location(cls, location_id=None):
        """Get all active products, optionally filtered by location"""
        try:
            db = config.get_db()
            
            if location_id:
                docs = db.collection('products').where('is_active', '==', True).where('location_id', '==', location_id).get()
            else:
                docs = db.collection('products').where('is_active', '==', True).get()
            
            products = []
            for doc in docs:
                products.append(cls.from_dict(doc.to_dict()))
            return products
        except Exception as e:
            print(f"Error getting products with location filter: {e}")
            return []

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
        self.branch_id = None
        # NEW DELETION FIELDS
        self.is_deleted = False
        self.deleted_at = None
        self.deleted_by = None
    
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
    def get_by_branch_id(cls, branch_id):
        """Get departments by branch ID"""
        try:
            db = config.get_db()
            docs = db.collection('departments').where('branch_id', '==', branch_id).get()
            departments = []
            for doc in docs:
                departments.append(cls.from_dict(doc.to_dict()))
            return departments
        except Exception as e:
            print(f"Error getting departments by branch ID: {e}")
            return []

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
    """Vendor settings model for system configuration with enhanced email settings"""
    
    def __init__(self):
        super().__init__()
        self.settings_id = 'vendor_settings'  # Singleton
        self.company_name = None
        self.postal_address = None
        self.primary_contact_name = None
        self.primary_contact_phone = None
        self.alternate_contact_name = None
        self.alternate_contact_phone = None
        
        # Email Configuration Fields
        self.email_address = None
        self.email_username = None
        self.email_password = None
        self.email_server_url = None
        self.email_port = 587
        self.email_use_tls = True
        self.email_use_ssl = False
        self.email_timeout = 30
        self.email_from_name = None  # Display name for "From" field
    
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
            settings.email_use_ssl = False
            settings.email_timeout = 30
            settings.save()
        return settings
    
    def get_email_config_status(self):
        """Get email configuration status"""
        required_fields = [
            self.email_address,
            self.email_password,
            self.email_server_url,
            self.email_username
        ]
        
        configured_fields = sum(1 for field in required_fields if field)
        total_fields = len(required_fields)
        
        return {
            'is_complete': configured_fields == total_fields,
            'configured_fields': configured_fields,
            'total_fields': total_fields,
            'completion_percentage': (configured_fields / total_fields) * 100
        }
    
    def validate_email_settings(self):
        """Validate email settings format"""
        errors = []
        
        if self.email_address:
            if '@' not in self.email_address:
                errors.append('Invalid email address format')
        
        if self.email_port:
            if not (1 <= self.email_port <= 65535):
                errors.append('Port must be between 1 and 65535')
        
        if self.email_timeout:
            if self.email_timeout < 1:
                errors.append('Timeout must be at least 1 second')
        
        return {
            'is_valid': len(errors) == 0,
            'errors': errors
        }