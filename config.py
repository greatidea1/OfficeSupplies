# Configuration - Firebase Setup and App Configuration
import os
import firebase_admin
from firebase_admin import credentials, firestore, storage
import json
import uuid
from werkzeug.utils import secure_filename

class Config:
    """Configuration class for Firebase and app settings"""
    
    def __init__(self):
        self.app = None
        self.db = None
        self.bucket = None
        self.firebase_app = None
        self.initialized = False
        self.use_local_storage = True  # Set to False to use Firebase Storage
        self.upload_folder = 'uploads'
    
    def init_app(self, app):
        """Initialize Firebase with Flask app"""
        try:
            self.app = app
            
            # Setup local storage directories
            if self.use_local_storage:
                self.setup_local_storage()
            
            # Get Firebase configuration from environment or config file
            firebase_config = self.get_firebase_config()
            
            if not firebase_config:
                raise ValueError("Firebase configuration not found")
            
            # Initialize Firebase Admin SDK
            if not firebase_admin._apps:
                if 'credentials_path' in firebase_config:
                    # Use service account key file
                    cred = credentials.Certificate(firebase_config['credentials_path'])
                elif 'credentials_json' in firebase_config:
                    # Use service account key JSON
                    cred = credentials.Certificate(firebase_config['credentials_json'])
                else:
                    # Use default credentials (for deployed environments)
                    cred = credentials.ApplicationDefault()
                
                # Initialize Firebase app
                if self.use_local_storage:
                    # Only initialize Firestore for database
                    self.firebase_app = firebase_admin.initialize_app(cred)
                else:
                    # Initialize with storage bucket for Firebase Storage
                    self.firebase_app = firebase_admin.initialize_app(cred, {
                        'storageBucket': firebase_config.get('storage_bucket', 'office-supplies-system.appspot.com')
                    })
            else:
                self.firebase_app = firebase_admin.get_app()
            
            # Initialize Firestore database
            self.db = firestore.client()
            
            # Initialize Storage bucket only if using Firebase Storage
            if not self.use_local_storage:
                self.bucket = storage.bucket()
            
            self.initialized = True
            
            # Create initial collections and indexes
            self.setup_initial_data()
            
            print("Firebase initialized successfully")
            storage_type = "Local Storage" if self.use_local_storage else "Firebase Storage"
            print(f"Using {storage_type} for file uploads")
            
        except Exception as e:
            print(f"Firebase initialization error: {e}")
            raise e
    
    def get_firebase_config(self):
        """Get Firebase configuration from environment or file"""
        try:
            # Try to get from environment variables first
            credentials_json = os.environ.get('FIREBASE_CREDENTIALS_JSON')
            if credentials_json:
                return {
                    'credentials_json': json.loads(credentials_json),
                    'storage_bucket': os.environ.get('FIREBASE_STORAGE_BUCKET', 'office-supplies-system.appspot.com')
                }
            
            # Try to get from credentials file
            credentials_path = os.environ.get('FIREBASE_CREDENTIALS_PATH', 'firebase-credentials.json')
            if os.path.exists(credentials_path):
                return {
                    'credentials_path': credentials_path,
                    'storage_bucket': os.environ.get('FIREBASE_STORAGE_BUCKET', 'office-supplies-system.appspot.com')
                }
            
            # For development - use default configuration
            if os.path.exists('firebase-config.json'):
                with open('firebase-config.json', 'r') as f:
                    return json.load(f)
            
            # Return None if no configuration found
            return None
            
        except Exception as e:
            print(f"Error getting Firebase configuration: {e}")
            return None
    
    def get_db(self):
        """Get Firestore database instance"""
        if not self.initialized:
            raise ValueError("Firebase not initialized. Call init_app() first.")
        return self.db
    
    def get_storage(self):
        """Get Storage instance - local or Firebase"""
        if not self.initialized:
            raise ValueError("Configuration not initialized. Call init_app() first.")
        
        if self.use_local_storage:
            return LocalStorage(self.upload_folder)
        return self.bucket
    
    def setup_local_storage(self):
        """Setup local storage directories"""
        try:
            directories = [
                'uploads/agreements',
                'uploads/products', 
                'uploads/avatars',
                'uploads/temp'
            ]
            
            for directory in directories:
                os.makedirs(directory, exist_ok=True)
            
            # Create .gitkeep files to ensure directories are tracked
            for directory in directories:
                gitkeep_path = os.path.join(directory, '.gitkeep')
                if not os.path.exists(gitkeep_path):
                    with open(gitkeep_path, 'w') as f:
                        f.write('')
            
            print("Local storage directories created successfully")
            
        except Exception as e:
            print(f"Error setting up local storage: {e}")
            raise e
    
    def setup_initial_data(self):
        """Setup initial data and collections"""
        try:
            # Create vendor settings document if it doesn't exist
            settings_ref = self.db.collection('vendor_settings').document('vendor_settings')
            if not settings_ref.get().exists:
                initial_settings = {
                    'company_name': 'Office Supplies Vendor',
                    'postal_address': '',
                    'primary_contact_name': '',
                    'primary_contact_phone': '',
                    'alternate_contact_name': '',
                    'alternate_contact_phone': '',
                    'email_address': '',
                    'email_username': '',
                    'email_password': '',
                    'email_server_url': '',
                    'email_port': 587,
                    'email_use_tls': True,
                    'created_at': firestore.SERVER_TIMESTAMP,
                    'updated_at': firestore.SERVER_TIMESTAMP
                }
                settings_ref.set(initial_settings)
                print("Created initial vendor settings")
            
            # Create default superadmin user if no users exist
            users_ref = self.db.collection('users')
            users_query = users_ref.where('role', '==', 'vendor_superadmin').limit(1)
            users_docs = list(users_query.get())
            
            if not users_docs:
                from models import User
                
                # Create default superadmin
                superadmin = User.create_vendor_superadmin(
                    username='superadmin',
                    email='admin@officesupplies.com',
                    password='admin123',  # Change this in production
                    full_name='System Administrator'
                )
                
                if superadmin.save():
                    print("Created default superadmin user")
                    print("Username: superadmin")
                    print("Password: admin123")
                    print("IMPORTANT: Change the default password after first login!")
            
            # Create sample product categories collection
            categories_ref = self.db.collection('product_categories')
            categories_doc = categories_ref.document('default').get()
            
            if not categories_doc.exists:
                default_categories = {
                    'categories': [
                        'Office Stationery',
                        'Computer Accessories',
                        'Furniture',
                        'Office Equipment',
                        'Printing Supplies',
                        'Storage & Organization',
                        'Cleaning Supplies',
                        'Safety Equipment',
                        'Communication Equipment',
                        'Miscellaneous'
                    ],
                    'created_at': firestore.SERVER_TIMESTAMP
                }
                categories_ref.document('default').set(default_categories)
                print("Created default product categories")
            
            print("Initial data setup completed")
            
        except Exception as e:
            print(f"Error setting up initial data: {e}")
    
    def create_indexes(self):
        """Create database indexes for better performance"""
        try:
            # Note: Firestore indexes are typically created via Firebase Console
            # or using the Firebase CLI. This method is for reference.
            
            indexes_needed = [
                # Users collection
                {
                    'collection': 'users',
                    'fields': [
                        {'field': 'username', 'order': 'ASCENDING'},
                        {'field': 'is_active', 'order': 'ASCENDING'}
                    ]
                },
                {
                    'collection': 'users',
                    'fields': [
                        {'field': 'customer_id', 'order': 'ASCENDING'},
                        {'field': 'role', 'order': 'ASCENDING'}
                    ]
                },
                
                # Orders collection
                {
                    'collection': 'orders',
                    'fields': [
                        {'field': 'customer_id', 'order': 'ASCENDING'},
                        {'field': 'created_at', 'order': 'DESCENDING'}
                    ]
                },
                {
                    'collection': 'orders',
                    'fields': [
                        {'field': 'status', 'order': 'ASCENDING'},
                        {'field': 'created_at', 'order': 'DESCENDING'}
                    ]
                },
                {
                    'collection': 'orders',
                    'fields': [
                        {'field': 'user_id', 'order': 'ASCENDING'},
                        {'field': 'created_at', 'order': 'DESCENDING'}
                    ]
                },
                
                # Products collection
                {
                    'collection': 'products',
                    'fields': [
                        {'field': 'is_active', 'order': 'ASCENDING'},
                        {'field': 'category', 'order': 'ASCENDING'}
                    ]
                },
                {
                    'collection': 'products',
                    'fields': [
                        {'field': 'quantity', 'order': 'ASCENDING'},
                        {'field': 'is_active', 'order': 'ASCENDING'}
                    ]
                },
                
                # Customers collection
                {
                    'collection': 'customers',
                    'fields': [
                        {'field': 'is_active', 'order': 'ASCENDING'},
                        {'field': 'created_at', 'order': 'DESCENDING'}
                    ]
                }
            ]
            
            print("Database indexes should be created via Firebase Console:")
            for index in indexes_needed:
                print(f"Collection: {index['collection']}")
                for field in index['fields']:
                    print(f"  - {field['field']} ({field['order']})")
                print()
            
        except Exception as e:
            print(f"Error setting up indexes: {e}")
    
    def test_connection(self):
        """Test Firebase connection"""
        try:
            if not self.initialized:
                return False
            
            # Test Firestore connection
            test_doc = self.db.collection('_test').document('connection_test')
            test_doc.set({'timestamp': firestore.SERVER_TIMESTAMP})
            test_doc.delete()
            
            # Test Storage connection
            blobs = list(self.bucket.list_blobs(max_results=1))
            
            return True
            
        except Exception as e:
            print(f"Firebase connection test failed: {e}")
            return False
    
    def cleanup(self):
        """Cleanup Firebase connections"""
        try:
            if self.firebase_app:
                firebase_admin.delete_app(self.firebase_app)
            self.initialized = False
            print("Firebase cleanup completed")
        except Exception as e:
            print(f"Firebase cleanup error: {e}")

class LocalStorage:
    """Local file storage handler"""
    
    def __init__(self, base_path='uploads'):
        self.base_path = base_path
    
    def blob(self, file_path):
        """Create a blob-like object for local storage"""
        return LocalBlob(file_path, self.base_path)
    
    def upload_from_file(self, file_stream, path, content_type=None):
        """Upload file to local storage"""
        try:
            # Ensure directory exists
            full_dir = os.path.join(self.base_path, os.path.dirname(path))
            os.makedirs(full_dir, exist_ok=True)
            
            # Save file
            full_path = os.path.join(self.base_path, path)
            with open(full_path, 'wb') as f:
                file_stream.seek(0)
                f.write(file_stream.read())
            
            return f"/{path}"
            
        except Exception as e:
            print(f"Error uploading file locally: {e}")
            raise e
    
    def list_blobs(self, max_results=None):
        """List files in local storage"""
        try:
            files = []
            for root, dirs, filenames in os.walk(self.base_path):
                for filename in filenames:
                    if filename != '.gitkeep':
                        rel_path = os.path.relpath(os.path.join(root, filename), self.base_path)
                        files.append(rel_path.replace('\\', '/'))
                        if max_results and len(files) >= max_results:
                            break
            return files[:max_results] if max_results else files
        except Exception as e:
            print(f"Error listing local files: {e}")
            return []

class LocalBlob:
    """Local blob object that mimics Firebase Storage blob"""
    
    def __init__(self, file_path, base_path):
        self.file_path = file_path
        self.base_path = base_path
        self.full_path = os.path.join(base_path, file_path)
    
    def upload_from_file(self, file_stream, content_type=None):
        """Upload file stream to local storage"""
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.full_path), exist_ok=True)
            
            # Save file
            with open(self.full_path, 'wb') as f:
                file_stream.seek(0)
                f.write(file_stream.read())
            
        except Exception as e:
            print(f"Error uploading blob locally: {e}")
            raise e
    
    def make_public(self):
        """Make file public (no-op for local storage)"""
        pass
    
    @property
    def public_url(self):
        """Get public URL for local file"""
        return f"/{self.file_path}"

# Global configuration instance
config = Config()

# Development configuration helper
def create_dev_config():
    """Create development configuration file template"""
    dev_config = {
        "credentials_path": "path/to/your/firebase-service-account-key.json",
        "storage_bucket": "your-project-id.appspot.com",
        "project_id": "your-project-id"
    }
    
    with open('firebase-config.json.template', 'w') as f:
        json.dump(dev_config, f, indent=2)
    
    print("Created firebase-config.json.template")
    print("Copy this to firebase-config.json and update with your Firebase project details")

if __name__ == '__main__':
    # Create development configuration template
    create_dev_config()