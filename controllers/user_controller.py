# User Controller - Handle user management operations
from flask import request, session
from models import User, Customer, Department, Branch
from controllers.auth_controller import auth_controller
from config import config
import uuid

class UserController:
    """Handle user management operations"""
    
    def __init__(self):
        self.auth = auth_controller

    def get_users_with_branch_info(self):
        """Get users list with branch information - NEW METHOD"""
        try:
            current_user = self.auth.get_current_user()
            if not current_user:
                return {'success': False, 'message': 'Authentication required'}
            
            # Get query parameters
            search = request.args.get('search', '')
            role = request.args.get('role', '')
            status = request.args.get('status', '')
            customer_id = request.args.get('customer_id', '')
            branch_id = request.args.get('branch_id', '')
            
            # Get users based on current user's role and permissions
            if current_user.role == 'vendor_superadmin':
                users = self.get_all_users()
            elif current_user.role == 'vendor_admin':
                users = self.get_vendor_and_customer_users()
            elif current_user.role == 'customer_hr_admin':
                users = self.get_customer_users(current_user.customer_id)
            else:
                return {'success': False, 'message': 'Insufficient permissions'}
            
            # Apply filters
            if search:
                search = search.lower()
                users = [u for u in users if 
                        search in u.username.lower() or 
                        search in (u.full_name or '').lower() or 
                        search in u.email.lower()]
            
            if role:
                # Handle multiple roles (comma-separated)
                if ',' in role:
                    role_list = [r.strip() for r in role.split(',')]
                    users = [u for u in users if u.role in role_list]
                else:
                    users = [u for u in users if u.role == role]
            
            if status:
                if status == 'active':
                    users = [u for u in users if u.is_active]
                elif status == 'inactive':
                    users = [u for u in users if not u.is_active]
            
            if customer_id:
                users = [u for u in users if u.customer_id == customer_id]
            
            if branch_id:
                users = [u for u in users if getattr(u, 'branch_id', None) == branch_id]
            
            # Sort users
            users.sort(key=lambda u: (u.full_name or u.username or '').lower())
            
            # Convert to dict and add additional info including branch information
            user_list = []
            for user in users:
                user_dict = user.to_dict()
                
                # Remove sensitive information
                if 'password_hash' in user_dict:
                    del user_dict['password_hash']
                
                # Add customer information
                if user.customer_id:
                    from models import Customer
                    customer = Customer.get_by_id(user.customer_id)
                    user_dict['customer_name'] = customer.company_name if customer else 'Unknown'
                
                # Add department information
                if user.department_id:
                    from models import Department
                    department = Department.get_by_id(user.department_id)
                    user_dict['department_name'] = department.name if department else 'Unknown'
                
                # Add branch information
                if hasattr(user, 'branch_id') and user.branch_id:
                    from models import Branch
                    branch = Branch.get_by_id(user.branch_id)
                    if branch:
                        user_dict['branch_name'] = branch.name
                        user_dict['branch_address'] = branch.address
                    else:
                        user_dict['branch_name'] = 'Unknown Branch'
                        user_dict['branch_address'] = None
                else:
                    user_dict['branch_name'] = None
                    user_dict['branch_address'] = None
                
                # Add permission flags
                user_dict['can_edit'] = self.can_edit_user(current_user, user)
                user_dict['can_delete'] = self.can_delete_user(current_user, user)
                
                user_list.append(user_dict)
            
            # Get available roles for current user
            available_roles = self.get_available_roles(current_user)
            
            return {
                'success': True,
                'users': user_list,
                'available_roles': available_roles,
                'total': len(user_list)
            }
            
        except Exception as e:
            print(f"Get users with branch info error: {e}")
            import traceback
            traceback.print_exc()
            return {'success': False, 'message': 'Failed to retrieve users'}
        
    def get_departments_by_branch(self, branch_id):
        """Get departments filtered by branch ID"""
        try:
            current_user = self.auth.get_current_user()
            if not current_user:
                return {'success': False, 'message': 'Authentication required'}
            
            if not branch_id:
                return {'success': True, 'departments': []}
            
            # Get departments for the specified branch
            departments = Department.get_by_branch_id(branch_id)
            
            # Filter only active departments
            active_departments = [dept for dept in departments if dept.is_active]
            
            dept_list = []
            for dept in active_departments:
                dept_list.append({
                    'department_id': dept.department_id,
                    'name': dept.name,
                    'description': dept.description or '',
                    'branch_id': dept.branch_id
                })
            
            return {
                'success': True,
                'departments': dept_list
            }
            
        except Exception as e:
            print(f"Get departments by branch error: {e}")
            return {'success': False, 'message': 'Failed to retrieve departments'}
    
    def get_users(self):
        """Get users list with enhanced branch information including pincode"""
        try:
            current_user = self.auth.get_current_user()
            if not current_user:
                return {'success': False, 'message': 'Authentication required'}
            
            # Get query parameters
            search = request.args.get('search', '')
            role_filter = request.args.get('role', '')
            status_filter = request.args.get('status', '')
            customer_filter = request.args.get('customer_id', '')
            department_filter = request.args.get('department_id', '')
            branch_filter = request.args.get('branch_id', '')
            
            users = []
            
            if current_user.role in ['vendor_superadmin', 'vendor_admin']:
                # Vendor users can see all users or filter by customer
                if customer_filter:
                    users = User.get_by_customer_id(customer_filter)
                    # Also get vendor users if no customer filter
                    vendor_users = []
                else:
                    # Get all users
                    from config import config
                    db = config.get_db()
                    docs = db.collection('users').get()
                    for doc in docs:
                        users.append(User.from_dict(doc.to_dict()))
                        
            elif current_user.role == 'customer_hr_admin':
                # Customer HR admin can see users from their organization
                users = User.get_by_customer_id(current_user.customer_id)
                
            elif current_user.role == 'customer_dept_head':
                # Department head can see users from their department
                users = User.get_by_department_id(current_user.department_id)
                
            else:
                return {'success': False, 'message': 'Insufficient permissions'}
            
            # Apply filters
            filtered_users = []
            
            for user in users:
                # Skip if user doesn't match filters
                if search:
                    search_term = search.lower()
                    if not (search_term in (user.username or '').lower() or 
                        search_term in (user.full_name or '').lower() or 
                        search_term in (user.email or '').lower()):
                        continue
                
                if role_filter and user.role != role_filter:
                    continue
                    
                if status_filter:
                    if status_filter == 'active' and not user.is_active:
                        continue
                    elif status_filter == 'inactive' and user.is_active:
                        continue
                
                if department_filter and user.department_id != department_filter:
                    continue
                    
                if branch_filter and getattr(user, 'branch_id', None) != branch_filter:
                    continue
                
                filtered_users.append(user)
            
            # Convert to dictionaries and add additional information
            user_list = []
            for user in filtered_users:
                user_dict = user.to_dict()
                
                # Add customer information for vendor users
                if current_user.role.startswith('vendor_') and user.customer_id:
                    from models import Customer
                    customer = Customer.get_by_id(user.customer_id)
                    if customer:
                        user_dict['customer_name'] = customer.company_name
                    else:
                        user_dict['customer_name'] = 'Unknown Customer'
                
                # Add department information
                if user.department_id:
                    from models import Department
                    department = Department.get_by_id(user.department_id)
                    if department:
                        user_dict['department_name'] = department.name
                    else:
                        user_dict['department_name'] = 'Unknown Department'
                else:
                    user_dict['department_name'] = None
                
                # Add branch information with pincode
                if hasattr(user, 'branch_id') and user.branch_id:
                    from models import Branch
                    branch = Branch.get_by_id(user.branch_id)
                    if branch:
                        # Include pincode in branch display
                        branch_display = branch.name
                        if hasattr(branch, 'pincode') and branch.pincode:
                            branch_display += f" ({branch.pincode})"
                        
                        user_dict['branch_name'] = branch_display
                        user_dict['branch_address'] = branch.address
                        user_dict['branch_pincode'] = getattr(branch, 'pincode', None)
                        user_dict['branch_name_only'] = branch.name  # For filtering purposes
                    else:
                        user_dict['branch_name'] = 'Unknown Branch'
                        user_dict['branch_address'] = None
                        user_dict['branch_pincode'] = None
                        user_dict['branch_name_only'] = None
                else:
                    user_dict['branch_name'] = None
                    user_dict['branch_address'] = None
                    user_dict['branch_pincode'] = None
                    user_dict['branch_name_only'] = None
                
                # Format role for display
                role_map = {
                    'vendor_superadmin': 'Vendor SuperAdmin',
                    'vendor_admin': 'Vendor Admin', 
                    'vendor_normal': 'Vendor User',
                    'customer_hr_admin': 'HR Admin',
                    'customer_dept_head': 'Department Head',
                    'customer_employee': 'Employee'
                }
                user_dict['role_display'] = role_map.get(user.role, user.role)
                
                # Add login status - FIXED DATETIME COMPARISON
                if user.last_login:
                    from datetime import datetime, timedelta
                    try:
                        # Handle both timezone-aware and naive datetimes
                        current_time = datetime.now()
                        thirty_days_ago = current_time - timedelta(days=30)
                        
                        # Convert user.last_login to same timezone format as current_time
                        if hasattr(user.last_login, 'tzinfo') and user.last_login.tzinfo is not None:
                            # last_login is timezone-aware, make current_time timezone-aware
                            if current_time.tzinfo is None:
                                import pytz
                                current_time = current_time.replace(tzinfo=pytz.UTC)
                                thirty_days_ago = thirty_days_ago.replace(tzinfo=pytz.UTC)
                        else:
                            # last_login is timezone-naive, ensure current_time is also naive
                            if hasattr(current_time, 'tzinfo') and current_time.tzinfo is not None:
                                current_time = current_time.replace(tzinfo=None)
                                thirty_days_ago = thirty_days_ago.replace(tzinfo=None)
                        
                        if user.last_login >= thirty_days_ago:
                            user_dict['login_status'] = 'recent'
                        else:
                            user_dict['login_status'] = 'old'
                    except Exception as e:
                        print(f"Error comparing dates for user {user.username}: {e}")
                        user_dict['login_status'] = 'unknown'
                else:
                    user_dict['login_status'] = 'never'
                
                user_list.append(user_dict)
            
            # Sort users - FIXED DATETIME COMPARISON FOR SORTING
            sort_by = request.args.get('sort', 'name_asc')
            if sort_by == 'name_asc':
                user_list.sort(key=lambda u: (u.get('full_name') or u.get('username', '')).lower())
            elif sort_by == 'name_desc':
                user_list.sort(key=lambda u: (u.get('full_name') or u.get('username', '')).lower(), reverse=True)
            elif sort_by == 'role_asc':
                user_list.sort(key=lambda u: u.get('role', ''))
            elif sort_by == 'role_desc':
                user_list.sort(key=lambda u: u.get('role', ''), reverse=True)
            elif sort_by == 'login_desc':
                # Sort by login status instead of raw datetime to avoid comparison issues
                status_order = {'recent': 3, 'old': 2, 'never': 1, 'unknown': 0}
                user_list.sort(key=lambda u: status_order.get(u.get('login_status', 'unknown'), 0), reverse=True)
            elif sort_by == 'created_desc':
                # Handle created_at datetime comparison safely
                def safe_created_at(user_dict):
                    try:
                        created_at = user_dict.get('created_at')
                        if created_at:
                            if isinstance(created_at, str):
                                from datetime import datetime
                                return datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                            return created_at
                        return datetime.min
                    except:
                        return datetime.min
                user_list.sort(key=safe_created_at, reverse=True)
            
            # Get available roles for current user
            available_roles = self.get_available_roles(current_user)
            
            return {
                'success': True,
                'users': user_list,
                'total': len(user_list),
                'available_roles': available_roles,  # ADD THIS LINE
                'filters_applied': {
                    'search': bool(search),
                    'role': bool(role_filter),
                    'status': bool(status_filter),
                    'customer': bool(customer_filter),
                    'department': bool(department_filter),
                    'branch': bool(branch_filter)
                }
            }
            
        except Exception as e:
            print(f"Get users error: {e}")
            import traceback
            traceback.print_exc()
            return {'success': False, 'message': 'Failed to retrieve users'}
    
    def get_user(self, user_id):
        """Get single user details with branch information - UPDATED VERSION"""
        try:
            current_user = self.auth.get_current_user()
            if not current_user:
                return {'success': False, 'message': 'Authentication required'}
            
            user = User.get_by_id(user_id)
            if not user:
                return {'success': False, 'message': 'User not found'}
            
            # Check permissions
            if not self.can_view_user(current_user, user):
                return {'success': False, 'message': 'Access denied'}
            
            user_dict = user.to_dict()
            if 'password_hash' in user_dict:
                del user_dict['password_hash']  # Remove sensitive info
            
            # Add customer information
            if user.customer_id:
                from models import Customer
                customer = Customer.get_by_id(user.customer_id)
                user_dict['customer_name'] = customer.company_name if customer else 'Unknown'
            
            # Add department information
            if user.department_id:
                from models import Department
                department = Department.get_by_id(user.department_id)
                user_dict['department_name'] = department.name if department else 'Unknown'
            
            # Add branch information
            if hasattr(user, 'branch_id') and user.branch_id:
                from models import Branch
                branch = Branch.get_by_id(user.branch_id)
                if branch:
                    user_dict['branch_name'] = branch.name
                    user_dict['branch_address'] = branch.address
                else:
                    user_dict['branch_name'] = 'Unknown Branch'
                    user_dict['branch_address'] = None
            else:
                user_dict['branch_name'] = None
                user_dict['branch_address'] = None
            
            # Add permission flags
            user_dict['can_edit'] = self.can_edit_user(current_user, user)
            user_dict['can_delete'] = self.can_delete_user(current_user, user)
            
            return {
                'success': True,
                'user': user_dict
            }
            
        except Exception as e:
            print(f"Get user error: {e}")
            return {'success': False, 'message': 'Failed to retrieve user'}
    
    def create_user(self):
        """Create new user - FIXED VERSION WITH PASSWORD EMAIL"""
        try:
            current_user = self.auth.get_current_user()
            if not current_user:
                return {'success': False, 'message': 'Authentication required'}
            
            data = request.get_json()
            
            # Validate required fields
            required_fields = ['first_name', 'last_name', 'username', 'email', 'role', 'password']
            for field in required_fields:
                if field not in data or not data[field]:
                    return {'success': False, 'message': f'{field} is required'}
            
            # Check permissions
            if not self.can_create_user_with_role(current_user, data['role']):
                return {'success': False, 'message': 'Insufficient permissions to create user with this role'}
            
            # Check if username already exists
            existing_user = User.get_by_username(data['username'])
            if existing_user:
                return {'success': False, 'message': 'Username already exists'}
            
            # Check if email already exists
            existing_email = User.get_by_email(data['email'])
            if existing_email:
                return {'success': False, 'message': 'Email already exists'}
            
            # Validate department requirement
            if data['role'] in ['customer_employee', 'customer_dept_head']:
                if not data.get('department_id'):
                    return {'success': False, 'message': 'Department is required for employees and department heads'}
            
            # Store the plain password for email before hashing
            plain_password = data['password']
            
            # Create user
            user = User(
                username=data['username'],
                email=data['email'],
                password_hash=User.hash_password(plain_password),  # Hash the password
                role=data['role']
            )
            
            # Set name fields
            user.first_name = data['first_name']
            user.last_name = data['last_name']
            user.full_name = data.get('full_name', f"{data['first_name']} {data['last_name']}")
            
            # Set user as immediately usable
            user.is_first_login = False
            user.password_reset_required = False
            user.is_active = True
            
            # Set customer_id based on role and current user
            if data['role'].startswith('customer_'):
                if current_user.role == 'customer_hr_admin':
                    user.customer_id = current_user.customer_id
                elif current_user.role.startswith('vendor_') and 'customer_id' in data:
                    user.customer_id = data['customer_id']
                else:
                    return {'success': False, 'message': 'Customer ID required for customer users'}
            
            # Set department_id
            if 'department_id' in data and data['department_id']:
                user.department_id = data['department_id']
            
            # Set branch_id if provided
            if 'branch_id' in data and data['branch_id']:
                user.branch_id = data['branch_id']
            
            if user.save():
                # Send welcome email with actual password if requested
                send_email = data.get('send_email', False)
                if send_email:
                    self.send_welcome_email_with_password(user, plain_password)
                
                return {
                    'success': True,
                    'message': 'User created successfully',
                    'user_id': user.user_id
                }
            else:
                return {'success': False, 'message': 'Failed to create user'}
                
        except Exception as e:
            print(f"Create user error: {e}")
            import traceback
            traceback.print_exc()
            return {'success': False, 'message': 'Failed to create user'}
        
    def get_branches_for_customer(self, customer_id=None):
        """Get branches for dropdown (Customer users or vendor with customer_id)"""
        try:
            current_user = self.auth.get_current_user()
            if not current_user:
                return {'success': False, 'message': 'Authentication required'}
            
            # Determine customer_id to use
            if current_user.role.startswith('customer_'):
                target_customer_id = current_user.customer_id
            elif current_user.role.startswith('vendor_') and customer_id:
                target_customer_id = customer_id
            else:
                return {'success': False, 'message': 'Customer ID required'}
            
            branches = Branch.get_by_customer_id(target_customer_id)
            
            branch_list = []
            for branch in branches:
                if branch.is_active:
                    branch_list.append({
                        'branch_id': branch.branch_id,
                        'name': branch.name,
                        'address': branch.address,
                        'pincode': getattr(branch, 'pincode', '')
                    })
            
            return {
                'success': True,
                'branches': branch_list
            }
            
        except Exception as e:
            print(f"Get branches error: {e}")
            return {'success': False, 'message': 'Failed to retrieve branches'}
        
    def send_welcome_email_with_password(self, user, password):
        """Send welcome email with password - role-specific templates"""
        try:
            from controllers.auth_controller import auth_controller
            from models import VendorSettings
            
            settings = VendorSettings.get_settings()
            
            if user.role.startswith('vendor_'):
                return self._send_vendor_welcome_email(user, password, settings)
            elif user.role.startswith('customer_'):
                return self._send_customer_welcome_email(user, password, settings)
            else:
                return False
                
        except Exception as e:
            print(f"Welcome email error: {e}")
            return False
        
    def _send_customer_welcome_email(self, user, password, settings):
        """Send welcome email for customer users"""
        try:
            from controllers.auth_controller import auth_controller
            from models import Customer
            
            # Get customer information
            customer = Customer.get_by_id(user.customer_id) if user.customer_id else None
            company_name = customer.company_name if customer else "Your Organization"
            
            subject = f"Welcome to {settings.company_name} - Office Supplies Portal"
            
            html_body = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5; }}
                    .container {{ max-width: 600px; margin: 0 auto; background-color: white; padding: 40px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                    .header {{ text-align: center; margin-bottom: 30px; }}
                    .logo {{ font-size: 24px; font-weight: bold; color: #059669; margin-bottom: 10px; }}
                    .title {{ font-size: 20px; color: #1f2937; margin-bottom: 10px; }}
                    .credentials {{ background-color: #f0fdf4; padding: 20px; border-radius: 6px; margin: 20px 0; border-left: 4px solid #059669; }}
                    .login-button {{ display: inline-block; background: linear-gradient(135deg, #059669, #047857); color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: 600; margin: 20px 0; }}
                    .login-button:hover {{ background: linear-gradient(135deg, #047857, #065f46); }}
                    .footer {{ margin-top: 30px; padding-top: 20px; border-top: 1px solid #e5e7eb; color: #6b7280; font-size: 14px; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <div class="logo">{settings.company_name}</div>
                        <div class="title">Welcome to Office Supplies Portal</div>
                    </div>
                    
                    <p>Hello {user.full_name or user.username},</p>
                    
                    <p>Your account has been created successfully for <strong>{company_name}</strong>. You can now access the Office Supplies Portal to browse products and place orders.</p>
                    
                    <div class="credentials">
                        <strong>Login Credentials:</strong><br>
                        <strong>Username:</strong> {user.username}<br>
                        <strong>Email:</strong> {user.email}<br>
                        <strong>Password:</strong> <code style="background: #dcfce7; padding: 2px 6px; border-radius: 4px; font-family: monospace;">{password}</code><br>
                        <strong>Role:</strong> {self._format_role_display(user.role)}<br>
                        <strong>Organization:</strong> {company_name}
                    </div>
                    
                    <div style="text-align: center;">
                        <a href="http://localhost:3000/login" class="login-button">
                            🛒 Access Office Supplies Portal
                        </a>
                    </div>
                    
                    <div style="background: #fef3c7; padding: 16px; border-radius: 6px; margin: 20px 0; border-left: 4px solid #f59e0b;">
                        <strong>🔒 Security Note:</strong><br>
                        Please change your password after first login for security purposes.
                    </div>
                    
                    <p><strong>What you can do in the Portal:</strong></p>
                    <ul>
                        <li>Browse and search office supplies catalog</li>
                        <li>Add items to cart and place orders</li>
                        <li>Track your order status and history</li>
                        <li>Manage your profile and preferences</li>
                        {self._get_role_specific_features(user.role)}
                    </ul>
                    
                    <p>If you have any questions or need assistance, please contact your HR administrator or our support team.</p>
                    
                    <div class="footer">
                        <p>Best regards,<br>{settings.company_name} Team</p>
                        <p>This is an automated message. Please do not reply to this email.</p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            return auth_controller.send_email_notification(user.email, subject, html_body, True)
            
        except Exception as e:
            print(f"Customer welcome email error: {e}")
            return False
        
    def _send_vendor_welcome_email(self, user, password, settings):
        """Send welcome email for vendor users"""
        try:
            from controllers.auth_controller import auth_controller
            
            subject = f"Welcome to {settings.company_name} - Vendor Portal Access"
            
            html_body = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5; }}
                    .container {{ max-width: 600px; margin: 0 auto; background-color: white; padding: 40px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                    .header {{ text-align: center; margin-bottom: 30px; }}
                    .logo {{ font-size: 24px; font-weight: bold; color: #2563eb; margin-bottom: 10px; }}
                    .title {{ font-size: 20px; color: #1f2937; margin-bottom: 10px; }}
                    .credentials {{ background-color: #f8fafc; padding: 20px; border-radius: 6px; margin: 20px 0; border-left: 4px solid #2563eb; }}
                    .login-button {{ display: inline-block; background: linear-gradient(135deg, #2563eb, #1d4ed8); color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: 600; margin: 20px 0; }}
                    .login-button:hover {{ background: linear-gradient(135deg, #1d4ed8, #1e40af); }}
                    .footer {{ margin-top: 30px; padding-top: 20px; border-top: 1px solid #e5e7eb; color: #6b7280; font-size: 14px; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <div class="logo">{settings.company_name}</div>
                        <div class="title">Welcome to Vendor Portal</div>
                    </div>
                    
                    <p>Hello {user.full_name or user.username},</p>
                    
                    <p>Your vendor account has been created successfully. You can now access the Vendor Portal to manage products, orders, and customers.</p>
                    
                    <div class="credentials">
                        <strong>Login Credentials:</strong><br>
                        <strong>Username:</strong> {user.username}<br>
                        <strong>Email:</strong> {user.email}<br>
                        <strong>Password:</strong> <code style="background: #e5e7eb; padding: 2px 6px; border-radius: 4px; font-family: monospace;">{password}</code><br>
                        <strong>Role:</strong> {self._format_role_display(user.role)}
                    </div>
                    
                    <div style="text-align: center;">
                        <a href="http://localhost:3000/vendor-login" class="login-button">
                            🚀 Access Vendor Portal
                        </a>
                    </div>
                    
                    <div style="background: #fef3c7; padding: 16px; border-radius: 6px; margin: 20px 0; border-left: 4px solid #f59e0b;">
                        <strong>🔒 Security Note:</strong><br>
                        Please change your password after first login for security purposes.
                    </div>
                    
                    <p><strong>What you can do in the Vendor Portal:</strong></p>
                    <ul>
                        <li>Manage product catalog and inventory</li>
                        <li>Process and track customer orders</li>
                        <li>Manage customer accounts and pricing</li>
                        <li>View sales reports and analytics</li>
                        <li>Configure system settings</li>
                    </ul>
                    
                    <p>If you have any questions or need assistance, please contact our support team.</p>
                    
                    <div class="footer">
                        <p>Best regards,<br>{settings.company_name} Team</p>
                        <p>This is an automated message. Please do not reply to this email.</p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            return auth_controller.send_email_notification(user.email, subject, html_body, True)
            
        except Exception as e:
            print(f"Vendor welcome email error: {e}")
            return False
        
    def _format_role_display(self, role):
        """Format role for display in emails"""
        role_map = {
            'vendor_superadmin': 'Vendor Super Administrator',
            'vendor_admin': 'Vendor Administrator', 
            'vendor_normal': 'Vendor User',
            'customer_hr_admin': 'HR Administrator',
            'customer_dept_head': 'Department Head',
            'customer_employee': 'Employee'
        }
        return role_map.get(role, role.replace('_', ' ').title())

    def _get_role_specific_features(self, role):
        """Get role-specific features for email"""
        if role == 'customer_hr_admin':
            return """
                        <li>Manage company users and departments</li>
                        <li>Approve department orders and budgets</li>
                        <li>View organization-wide reports</li>
                        <li>Configure company settings</li>
            """
        elif role == 'customer_dept_head':
            return """
                        <li>Approve department orders</li>
                        <li>View department order history</li>
                        <li>Manage department team members</li>
            """
        else:
            return """
                        <li>Submit orders for approval</li>
                        <li>View order approval status</li>
            """
        
    def send_welcome_email_without_password(self, user):
        """Deprecated - use send_welcome_email_with_password instead"""
        # This method is kept for backward compatibility
        # Generate a temporary password for the email
        import uuid
        temp_password = f"temp_{uuid.uuid4().hex[:8]}"
        return self.send_welcome_email_with_password(user, temp_password)
    
    def update_user(self, user_id):
        """Update user information - FIXED VERSION"""
        try:
            current_user = self.auth.get_current_user()
            if not current_user:
                return {'success': False, 'message': 'Authentication required'}
            
            user = User.get_by_id(user_id)
            if not user:
                return {'success': False, 'message': 'User not found'}
            
            # Check permissions
            if not self.can_edit_user(current_user, user):
                return {'success': False, 'message': 'Insufficient permissions'}
            
            data = request.get_json()
            
            # Update allowed fields
            updateable_fields = ['full_name', 'email', 'is_active', 'department_id', 'branch_id']
            
            # Role can only be updated by vendor users
            if current_user.role.startswith('vendor_') and 'role' in data:
                if self.can_create_user_with_role(current_user, data['role']):
                    updateable_fields.append('role')
                else:
                    return {'success': False, 'message': 'Cannot assign this role'}
            
            # Track what was actually updated for debugging
            updated_fields = []
            
            for field in updateable_fields:
                if field in data:
                    old_value = getattr(user, field, None)
                    new_value = data[field]
                    
                    if field == 'is_active':
                        new_value = bool(data[field])
                    elif field == 'department_id':
                        # Handle department_id - can be None/empty string
                        new_value = data[field] if data[field] else None
                    elif field == 'branch_id':
                        # Handle branch_id - can be None/empty string  
                        new_value = data[field] if data[field] else None
                    
                    # Only update if value actually changed
                    if old_value != new_value:
                        setattr(user, field, new_value)
                        updated_fields.append(f"{field}: {old_value} -> {new_value}")
            
            # Debug logging
            print(f"DEBUG: Updating user {user.username}")
            print(f"DEBUG: Updated fields: {updated_fields}")
            print(f"DEBUG: Final user data before save:")
            print(f"  - full_name: {user.full_name}")
            print(f"  - email: {user.email}")
            print(f"  - role: {user.role}")
            print(f"  - is_active: {user.is_active}")
            print(f"  - department_id: {getattr(user, 'department_id', None)}")
            print(f"  - branch_id: {getattr(user, 'branch_id', None)}")
            
            if user.save():
                print(f"DEBUG: User {user.username} saved successfully")
                return {
                    'success': True,
                    'message': 'User updated successfully',
                    'updated_fields': len(updated_fields),
                    'debug_info': updated_fields  # Remove this in production
                }
            else:
                print(f"DEBUG: Failed to save user {user.username}")
                return {'success': False, 'message': 'Failed to save user changes'}
                
        except Exception as e:
            print(f"Update user error: {e}")
            import traceback
            traceback.print_exc()
            return {'success': False, 'message': 'Failed to update user'}
    
    def update_profile(self):
        """Update current user's profile"""
        try:
            current_user = self.auth.get_current_user()
            if not current_user:
                return {'success': False, 'message': 'Authentication required'}
            
            data = request.get_json()
            
            # Allow users to update their own profile fields
            updateable_fields = ['full_name']
            
            for field in updateable_fields:
                if field in data:
                    setattr(current_user, field, data[field])
            
            if current_user.save():
                return {
                    'success': True,
                    'message': 'Profile updated successfully'
                }
            else:
                return {'success': False, 'message': 'Failed to update profile'}
                
        except Exception as e:
            print(f"Update profile error: {e}")
            return {'success': False, 'message': 'Failed to update profile'}
    
    def delete_user(self, user_id):
        """Deactivate user (soft delete)"""
        try:
            current_user = self.auth.get_current_user()
            if not current_user:
                return {'success': False, 'message': 'Authentication required'}
            
            user = User.get_by_id(user_id)
            if not user:
                return {'success': False, 'message': 'User not found'}
            
            # Check permissions
            if not self.can_delete_user(current_user, user):
                return {'success': False, 'message': 'Insufficient permissions'}
            
            # Prevent self-deletion
            if user.user_id == current_user.user_id:
                return {'success': False, 'message': 'Cannot delete your own account'}
            
            # Soft delete by deactivating
            user.is_active = False
            
            if user.save():
                return {
                    'success': True,
                    'message': 'User deactivated successfully'
                }
            else:
                return {'success': False, 'message': 'Failed to deactivate user'}
                
        except Exception as e:
            print(f"Delete user error: {e}")
            return {'success': False, 'message': 'Failed to deactivate user'}
    
    def reset_user_password(self, user_id):
        """Reset user password (Admin only) - UPDATED"""
        try:
            current_user = self.auth.get_current_user()
            if not current_user:
                return {'success': False, 'message': 'Authentication required'}
            
            user = User.get_by_id(user_id)
            if not user:
                return {'success': False, 'message': 'User not found'}
            
            # Check permissions
            if not self.can_edit_user(current_user, user):
                return {'success': False, 'message': 'Insufficient permissions'}
            
            # Generate new temporary password
            import uuid
            temp_password = f"temp_{uuid.uuid4().hex[:8]}"
            
            # Reset password
            user.password_hash = User.hash_password(temp_password)
            user.password_reset_required = True
            user.is_first_login = True
            
            if user.save():
                # Send password reset email with new template
                data = request.get_json() or {}
                if data.get('send_email', False):
                    self.send_welcome_email_with_password(user, temp_password)
                
                return {
                    'success': True,
                    'message': 'Password reset successfully',
                    'temp_password': temp_password
                }
            else:
                return {'success': False, 'message': 'Failed to reset password'}
                
        except Exception as e:
            print(f"Reset password error: {e}")
            return {'success': False, 'message': 'Failed to reset password'}
    
    def get_departments(self):
        """Get departments for current user's customer"""
        try:
            current_user = self.auth.get_current_user()
            if not current_user or not current_user.role.startswith('customer_'):
                return {'success': False, 'message': 'Only customer users can view departments'}
            
            departments = Department.get_by_customer_id(current_user.customer_id)
            
            dept_list = []
            for dept in departments:
                dept_dict = dept.to_dict()
                
                # Add user count
                users = User.get_by_customer_id(current_user.customer_id)
                dept_users = [u for u in users if u.department_id == dept.department_id]
                dept_dict['user_count'] = len(dept_users)
                
                dept_list.append(dept_dict)
            
            return {
                'success': True,
                'departments': dept_list
            }
            
        except Exception as e:
            print(f"Get departments error: {e}")
            return {'success': False, 'message': 'Failed to retrieve departments'}
        
    def get_departments_for_customer(self, customer_id=None):
        """Get departments for dropdown (Customer users or vendor with customer_id) - FIXED VERSION"""
        try:
            current_user = self.auth.get_current_user()
            if not current_user:
                return {'success': False, 'message': 'Authentication required'}
            
            # Determine customer_id to use
            if current_user.role.startswith('customer_'):
                target_customer_id = current_user.customer_id
            elif current_user.role.startswith('vendor_') and customer_id:
                target_customer_id = customer_id
            else:
                return {'success': False, 'message': 'Customer ID required'}
            
            departments = Department.get_by_customer_id(target_customer_id)
            
            dept_list = []
            for dept in departments:
                if dept.is_active:
                    dept_list.append({
                        'department_id': dept.department_id,
                        'name': dept.name,
                        'description': dept.description
                    })
            
            return {
                'success': True,
                'departments': dept_list
            }
            
        except Exception as e:
            print(f"Get departments error: {e}")
            return {'success': False, 'message': 'Failed to retrieve departments'}
    
    def create_department(self):
        """Create new department (Customer HR Admin only)"""
        try:
            current_user = self.auth.get_current_user()
            if not current_user or current_user.role != 'customer_hr_admin':
                return {'success': False, 'message': 'Only HR admins can create departments'}
            
            data = request.get_json()
            
            if not data.get('name'):
                return {'success': False, 'message': 'Department name is required'}
            
            department = Department()
            department.customer_id = current_user.customer_id
            department.name = data['name']
            department.description = data.get('description', '')
            
            if department.save():
                return {
                    'success': True,
                    'message': 'Department created successfully',
                    'department_id': department.department_id
                }
            else:
                return {'success': False, 'message': 'Failed to create department'}
                
        except Exception as e:
            print(f"Create department error: {e}")
            return {'success': False, 'message': 'Failed to create department'}
    
    # Helper methods
    
    def get_all_users(self):
        """Get all users (SuperAdmin only)"""
        try:
            db = config.get_db()
            docs = db.collection('users').get()
            return [User.from_dict(doc.to_dict()) for doc in docs]
        except:
            return []
    
    def get_vendor_and_customer_users(self):
        """Get vendor normal users and all customer users (Vendor Admin)"""
        try:
            db = config.get_db()
            
            # Get vendor normal users
            vendor_docs = db.collection('users').where('role', '==', 'vendor_normal').get()
            vendor_users = [User.from_dict(doc.to_dict()) for doc in vendor_docs]
            
            # Get all customer users
            customer_roles = ['customer_hr_admin', 'customer_dept_head', 'customer_employee']
            customer_users = []
            
            for role in customer_roles:
                docs = db.collection('users').where('role', '==', role).get()
                customer_users.extend([User.from_dict(doc.to_dict()) for doc in docs])
            
            return vendor_users + customer_users
        except:
            return []
    
    def get_customer_users(self, customer_id):
        """Get users for specific customer (Customer HR Admin) - DEBUG VERSION"""
        try:
            print(f"DEBUG: Getting users for customer_id: {customer_id}")
            users = User.get_by_customer_id(customer_id)
            print(f"DEBUG: Found {len(users)} users for customer {customer_id}")
            for user in users:
                print(f"  - {user.username} ({user.role}) - active: {user.is_active}")
            return users
        except Exception as e:
            print(f"Error getting customer users: {e}")
            return []
    
    def can_view_user(self, current_user, target_user):
        """Check if current user can view target user"""
        # Vendor SuperAdmin can view all users
        if current_user.role == 'vendor_superadmin':
            return True
        
        # Vendor Admin can view vendor normal and customer users
        if current_user.role == 'vendor_admin':
            return (target_user.role == 'vendor_normal' or 
                   target_user.role.startswith('customer_'))
        
        # Customer HR Admin can view users in their organization
        if current_user.role == 'customer_hr_admin':
            return (target_user.customer_id == current_user.customer_id and
                   target_user.role in ['customer_dept_head', 'customer_employee'])
        
        # Users can view their own profile
        return current_user.user_id == target_user.user_id
    
    def can_edit_user(self, current_user, target_user):
        """Check if current user can edit target user"""
        # Cannot edit own account role/status through user management
        if current_user.user_id == target_user.user_id:
            return False
        
        # Vendor SuperAdmin can edit all users except other superadmins
        if current_user.role == 'vendor_superadmin':
            return target_user.role != 'vendor_superadmin'
        
        # Vendor Admin can edit vendor normal and customer users
        if current_user.role == 'vendor_admin':
            return (target_user.role == 'vendor_normal' or 
                   target_user.role.startswith('customer_'))
        
        # Customer HR Admin can edit users in their organization
        if current_user.role == 'customer_hr_admin':
            return (target_user.customer_id == current_user.customer_id and
                   target_user.role in ['customer_dept_head', 'customer_employee'])
        
        return False
    
    def can_delete_user(self, current_user, target_user):
        """Check if current user can delete target user"""
        # Same rules as edit, but more restrictive
        return self.can_edit_user(current_user, target_user)
    
    def can_create_user_with_role(self, current_user, role):
        """Check if current user can create user with specific role"""
        # Vendor SuperAdmin can create any role except other superadmins
        if current_user.role == 'vendor_superadmin':
            return role != 'vendor_superadmin'
        
        # Vendor Admin can create vendor normal and customer users
        if current_user.role == 'vendor_admin':
            return role in ['vendor_normal', 'customer_hr_admin', 'customer_dept_head', 'customer_employee']
        
        # Customer HR Admin can create department heads and employees
        if current_user.role == 'customer_hr_admin':
            return role in ['customer_dept_head', 'customer_employee']
        
        return False
    
    def get_available_roles(self, current_user):
        """Get roles that current user can assign"""
        if current_user.role == 'vendor_superadmin':
            return [
                {'value': 'vendor_admin', 'label': 'Vendor Admin'},
                {'value': 'vendor_normal', 'label': 'Vendor User'},
                {'value': 'customer_hr_admin', 'label': 'Customer HR Admin'},
                {'value': 'customer_dept_head', 'label': 'Customer Department Head'},
                {'value': 'customer_employee', 'label': 'Customer Employee'}
            ]
        elif current_user.role == 'vendor_admin':
            return [
                {'value': 'vendor_normal', 'label': 'Vendor User'},
                {'value': 'customer_hr_admin', 'label': 'Customer HR Admin'},
                {'value': 'customer_dept_head', 'label': 'Customer Department Head'},
                {'value': 'customer_employee', 'label': 'Customer Employee'}
            ]
        elif current_user.role == 'customer_hr_admin':
            return [
                {'value': 'customer_dept_head', 'label': 'Department Head'},
                {'value': 'customer_employee', 'label': 'Employee'}
            ]
        else:
            return []
        
        # Helper methods for permission checks
    def can_edit_user(self, current_user, target_user):
        """Check if current user can edit target user"""
        if current_user.user_id == target_user.user_id:
            return False
        
        if current_user.role == 'vendor_superadmin':
            return target_user.role != 'vendor_superadmin'
        
        if current_user.role == 'vendor_admin':
            return (target_user.role == 'vendor_normal' or 
                   target_user.role.startswith('customer_'))
        
        if current_user.role == 'customer_hr_admin':
            return (target_user.customer_id == current_user.customer_id and
                   target_user.role in ['customer_dept_head', 'customer_employee'])
        
        return False

    def can_delete_user(self, current_user, target_user):
        """Check if current user can delete target user"""
        return self.can_edit_user(current_user, target_user)

# Global user controller instance
user_controller = UserController()