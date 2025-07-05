# User Controller - Handle user management operations
from flask import request, session
from models import User, Customer, Department
from controllers.auth_controller import auth_controller
from config import config
import uuid

class UserController:
    """Handle user management operations"""
    
    def __init__(self):
        self.auth = auth_controller
    
    def get_users(self):
        """Get users list based on current user's permissions - FIXED VERSION"""
        try:
            current_user = self.auth.get_current_user()
            if not current_user:
                return {'success': False, 'message': 'Authentication required'}
            
            # Get query parameters
            search = request.args.get('search', '')
            role = request.args.get('role', '')
            status = request.args.get('status', '')
            customer_id = request.args.get('customer_id', '')
            
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
            
            # Sort users
            users.sort(key=lambda u: (u.full_name or u.username or '').lower())
            
            # Convert to dict and add additional info
            user_list = []
            for user in users:
                user_dict = user.to_dict()
                
                # Remove sensitive information
                del user_dict['password_hash']
                
                # Add additional info
                if user.customer_id:
                    customer = Customer.get_by_id(user.customer_id)
                    user_dict['customer_name'] = customer.company_name if customer else 'Unknown'
                
                if user.department_id:
                    department = Department.get_by_id(user.department_id)
                    user_dict['department_name'] = department.name if department else 'Unknown'
                
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
            print(f"Get users error: {e}")
            import traceback
            traceback.print_exc()
            return {'success': False, 'message': 'Failed to retrieve users'}
    
    def get_user(self, user_id):
        """Get single user details"""
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
            del user_dict['password_hash']  # Remove sensitive info
            
            # Add additional info
            if user.customer_id:
                customer = Customer.get_by_id(user.customer_id)
                user_dict['customer_name'] = customer.company_name if customer else 'Unknown'
            
            if user.department_id:
                department = Department.get_by_id(user.department_id)
                user_dict['department_name'] = department.name if department else 'Unknown'
            
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
        """Create new user - FIXED VERSION"""
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
            
            # Create user - THIS IS WHERE user VARIABLE IS CREATED
            user = User(
                username=data['username'],
                email=data['email'],
                password_hash=User.hash_password(data['password']),
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
            
            # Set branch_id if provided - NOW user VARIABLE EXISTS
            if 'branch_id' in data and data['branch_id']:
                user.branch_id = data['branch_id']
            
            if user.save():
                # Send welcome email if requested
                send_email = data.get('send_email', False)
                if send_email:
                    self.send_welcome_email_without_password(user)
                
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
            
            from models import Branch
            branches = Branch.get_by_customer_id(target_customer_id)
            
            branch_list = []
            for branch in branches:
                if branch.is_active:
                    branch_list.append({
                        'branch_id': branch.branch_id,
                        'name': branch.name,
                        'address': branch.address
                    })
            
            return {
                'success': True,
                'branches': branch_list
            }
            
        except Exception as e:
            print(f"Get branches error: {e}")
            return {'success': False, 'message': 'Failed to retrieve branches'}
        
    def send_welcome_email_without_password(self, user):
        """Send welcome email without exposing password"""
        try:
            from controllers.auth_controller import auth_controller
            from models import VendorSettings
            
            settings = VendorSettings.get_settings()
            
            subject = f"Welcome to {settings.company_name} - Office Supplies System"
            
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
                    .footer {{ margin-top: 30px; padding-top: 20px; border-top: 1px solid #e5e7eb; color: #6b7280; font-size: 14px; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <div class="logo">{settings.company_name}</div>
                        <div class="title">Welcome to Office Supplies System</div>
                    </div>
                    
                    <p>Hello {user.full_name or user.username},</p>
                    
                    <p>Your account has been created successfully. You can now access the Office Supplies System using your credentials.</p>
                    
                    <div class="credentials">
                        <strong>Login Information:</strong><br>
                        <strong>Username:</strong> {user.username}<br>
                        <strong>Email:</strong> {user.email}<br>
                        <strong>Role:</strong> {user.role.replace('_', ' ').title()}<br>
                        <strong>Password:</strong> Use the password provided by your administrator
                    </div>
                    
                    <p><strong>Login URLs:</strong></p>
                    <ul>
                        <li><strong>Customer Portal:</strong> <a href="http://localhost:3000/login">http://localhost:3000/login</a></li>
                        <li><strong>Vendor Portal:</strong> <a href="http://localhost:3000/vendor-login">http://localhost:3000/vendor-login</a></li>
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
            print(f"Welcome email error: {e}")
            return False
    
    def update_user(self, user_id):
        """Update user information"""
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
            updateable_fields = ['full_name', 'email', 'is_active']
            
            # Role can only be updated by vendor users
            if current_user.role.startswith('vendor_') and 'role' in data:
                if self.can_create_user_with_role(current_user, data['role']):
                    updateable_fields.append('role')
                else:
                    return {'success': False, 'message': 'Cannot assign this role'}
            
            # Department can be updated for customer employees
            if (data.get('role') == 'customer_employee' or user.role == 'customer_employee') and 'department_id' in data:
                updateable_fields.append('department_id')
            
            for field in updateable_fields:
                if field in data:
                    if field == 'is_active':
                        setattr(user, field, bool(data[field]))
                    else:
                        setattr(user, field, data[field])
            
            if user.save():
                return {
                    'success': True,
                    'message': 'User updated successfully'
                }
            else:
                return {'success': False, 'message': 'Failed to update user'}
                
        except Exception as e:
            print(f"Update user error: {e}")
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
        """Reset user password (Admin only)"""
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
            temp_password = f"temp_{uuid.uuid4().hex[:8]}"
            
            # Reset password
            user.password_hash = User.hash_password(temp_password)
            user.password_reset_required = True
            user.is_first_login = True
            
            if user.save():
                # Send password reset email
                data = request.get_json() or {}
                if data.get('send_email', False):
                    self.auth.send_welcome_email(user, temp_password)
                
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

# Global user controller instance
user_controller = UserController()