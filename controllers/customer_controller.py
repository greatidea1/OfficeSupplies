# Customer Controller - Handle customer management and operations
from flask import request, session
from werkzeug.utils import secure_filename
import uuid
import os
from datetime import datetime, timedelta
from models import Customer, User, Order, Department
from controllers.auth_controller import auth_controller
from config import config

class CustomerController:
    """Handle customer management operations"""
    
    def __init__(self):
        self.auth = auth_controller
    
    def get_customers(self):
        """Get customers list (Vendor users only)"""
        try:
            current_user = self.auth.get_current_user()
            if not current_user or not current_user.role.startswith('vendor_'):
                return {'success': False, 'message': 'Only vendor users can view customers'}
            
            # Get query parameters
            search = request.args.get('search', '')
            status = request.args.get('status', '')
            sort_by = request.args.get('sort', 'name_asc')
            
            # Get all customers
            if current_user.role in ['vendor_superadmin', 'vendor_admin']:
                customers = Customer.get_all()
            else:
                customers = Customer.get_all_active()
            
            # Apply search filter
            if search:
                search = search.lower()
                customers = [c for c in customers if 
                           search in c.company_name.lower() or 
                           search in c.email.lower() or 
                           search in c.customer_id.lower()]
            
            # Apply status filter
            if status:
                if status == 'active':
                    customers = [c for c in customers if c.is_active]
                elif status == 'inactive':
                    customers = [c for c in customers if not c.is_active]
            
            # Apply sorting
            if sort_by == 'name_asc':
                customers.sort(key=lambda c: c.company_name.lower())
            elif sort_by == 'name_desc':
                customers.sort(key=lambda c: c.company_name.lower(), reverse=True)
            elif sort_by == 'created_desc':
                customers.sort(key=lambda c: c.created_at, reverse=True)
            elif sort_by == 'created_asc':
                customers.sort(key=lambda c: c.created_at)
            
            # Convert to dict and add statistics
            customer_list = []
            for customer in customers:
                customer_dict = customer.to_dict()
                
                # Add statistics
                stats = self.get_customer_statistics_internal(customer.customer_id)
                customer_dict['statistics'] = stats
                
                customer_list.append(customer_dict)
            
            return {
                'success': True,
                'customers': customer_list,
                'total': len(customer_list)
            }
            
        except Exception as e:
            print(f"Get customers error: {e}")
            return {'success': False, 'message': 'Failed to retrieve customers'}
    
    def get_customer(self, customer_id):
        """Get single customer details"""
        try:
            current_user = self.auth.get_current_user()
            if not current_user:
                return {'success': False, 'message': 'Authentication required'}
            
            # Check permissions
            if (current_user.role.startswith('vendor_') or 
                (current_user.role.startswith('customer_') and current_user.customer_id == customer_id)):
                pass  # Access allowed
            else:
                return {'success': False, 'message': 'Access denied'}
            
            customer = Customer.get_by_id(customer_id)
            if not customer:
                return {'success': False, 'message': 'Customer not found'}
            
            customer_dict = customer.to_dict()
            
            # Add detailed statistics
            customer_dict['statistics'] = self.get_customer_statistics_internal(customer_id)
            
            # Add user information
            users = User.get_by_customer_id(customer_id)
            customer_dict['users'] = [
                {
                    'user_id': u.user_id,
                    'username': u.username,
                    'full_name': u.full_name,
                    'email': u.email,
                    'role': u.role,
                    'is_active': u.is_active,
                    'last_login': u.last_login
                } for u in users
            ]
            
            # Add departments
            departments = Department.get_by_customer_id(customer_id)
            customer_dict['departments'] = [
                {
                    'department_id': d.department_id,
                    'name': d.name,
                    'description': d.description,
                    'is_active': d.is_active
                } for d in departments
            ]
            
            return {
                'success': True,
                'customer': customer_dict
            }
            
        except Exception as e:
            print(f"Get customer error: {e}")
            return {'success': False, 'message': 'Failed to retrieve customer'}
    
    def create_customer(self):
        """Create new customer (Vendor SuperAdmin only)"""
        try:
            current_user = self.auth.get_current_user()
            if not current_user or current_user.role != 'vendor_superadmin':
                return {'success': False, 'message': 'Only SuperAdmin can create customers'}
            
            # Handle both form data and JSON
            if request.content_type and request.content_type.startswith('multipart/form-data'):
                data = request.form.to_dict()
            else:
                data = request.get_json()
            
            # Validate required fields
            required_fields = ['company_name', 'email', 'postal_address', 'primary_phone']
            for field in required_fields:
                if field not in data or not data[field]:
                    return {'success': False, 'message': f'{field.replace("_", " ").title()} is required'}
            
            # Check if email already exists
            existing_customer = Customer.get_by_email(data['email'])
            if existing_customer:
                return {'success': False, 'message': 'Email address already exists'}
            
            # Create customer
            customer = Customer()
            customer.company_name = data['company_name']
            customer.email = data['email']
            customer.postal_address = data['postal_address']
            customer.primary_phone = data['primary_phone']
            customer.alternate_phone = data.get('alternate_phone', '')
            
            # Handle agreement file upload
            if 'agreement_file' in request.files:
                file = request.files['agreement_file']
                if file and file.filename:
                    agreement_url = self.upload_agreement_file(file, customer.customer_id)
                    if agreement_url:
                        customer.agreement_file_url = agreement_url
                    else:
                        return {'success': False, 'message': 'Failed to upload agreement file'}
            
            # Save customer
            if customer.save():
                # Create HR admin user
                hr_result = customer.create_hr_admin_user(send_email=data.get('send_email', False))
                
                if hr_result['success']:
                    return {
                        'success': True,
                        'message': 'Customer registered successfully',
                        'customer_id': customer.customer_id,
                        'hr_credentials': {
                            'username': hr_result['user'].username,
                            'temp_password': hr_result['temp_password']
                        }
                    }
                else:
                    # Customer created but HR user creation failed
                    return {
                        'success': True,
                        'message': 'Customer created but HR user creation failed. Please create manually.',
                        'customer_id': customer.customer_id,
                        'warning': hr_result['message']
                    }
            else:
                return {'success': False, 'message': 'Failed to create customer'}
                
        except Exception as e:
            print(f"Create customer error: {e}")
            return {'success': False, 'message': 'Failed to create customer'}
    
    def update_customer(self, customer_id):
        """Update customer information (Vendor SuperAdmin only)"""
        try:
            current_user = self.auth.get_current_user()
            if not current_user or current_user.role != 'vendor_superadmin':
                return {'success': False, 'message': 'Only SuperAdmin can update customers'}
            
            customer = Customer.get_by_id(customer_id)
            if not customer:
                return {'success': False, 'message': 'Customer not found'}
            
            data = request.get_json()
            
            # Update allowed fields
            updateable_fields = [
                'company_name', 'email', 'postal_address', 
                'primary_phone', 'alternate_phone', 'is_active'
            ]
            
            for field in updateable_fields:
                if field in data:
                    if field == 'is_active':
                        setattr(customer, field, bool(data[field]))
                    else:
                        setattr(customer, field, data[field])
            
            if customer.save():
                return {
                    'success': True,
                    'message': 'Customer updated successfully'
                }
            else:
                return {'success': False, 'message': 'Failed to update customer'}
                
        except Exception as e:
            print(f"Update customer error: {e}")
            return {'success': False, 'message': 'Failed to update customer'}
    
    def get_customer_statistics(self, customer_id):
        """Get customer statistics"""
        try:
            current_user = self.auth.get_current_user()
            if not current_user:
                return {'success': False, 'message': 'Authentication required'}
            
            # Check permissions
            if (current_user.role.startswith('vendor_') or 
                (current_user.role.startswith('customer_') and current_user.customer_id == customer_id)):
                pass  # Access allowed
            else:
                return {'success': False, 'message': 'Access denied'}
            
            statistics = self.get_customer_statistics_internal(customer_id)
            
            return {
                'success': True,
                'statistics': statistics
            }
            
        except Exception as e:
            print(f"Get customer statistics error: {e}")
            return {'success': False, 'message': 'Failed to retrieve statistics'}
    
    def get_dashboard_statistics(self):
        """Get dashboard statistics for customer admin users"""
        try:
            current_user = self.auth.get_current_user()
            if not current_user or not current_user.role.startswith('customer_'):
                return {'success': False, 'message': 'Only customer users can view dashboard'}
            
            customer_id = current_user.customer_id
            
            # Get basic statistics
            stats = self.get_customer_statistics_internal(customer_id)
            
            # Add role-specific statistics
            if current_user.role == 'customer_hr_admin':
                # HR admin sees all organization stats
                pass  # stats already contains all org data
                
            elif current_user.role == 'customer_dept_head':
                # Department head sees department-specific stats
                dept_stats = self.get_department_statistics(current_user.department_id)
                stats.update(dept_stats)
                
            return {
                'success': True,
                'statistics': stats
            }
            
        except Exception as e:
            print(f"Get dashboard statistics error: {e}")
            return {'success': False, 'message': 'Failed to retrieve dashboard statistics'}
    
    def get_employee_dashboard_statistics(self):
        """Get dashboard statistics for customer employees"""
        try:
            current_user = self.auth.get_current_user()
            if not current_user or current_user.role != 'customer_employee':
                return {'success': False, 'message': 'Only customer employees can view this dashboard'}
            
            # Get employee's personal order statistics
            orders = Order.get_by_user_id(current_user.user_id)
            
            total_orders = len(orders)
            pending_orders = len([o for o in orders if o.status in ['pending_dept_approval', 'pending_hr_approval']])
            approved_orders = len([o for o in orders if o.status in ['approved', 'packed', 'ready_for_dispatch']])
            delivered_orders = len([o for o in orders if o.status == 'dispatched'])
            rejected_orders = len([o for o in orders if o.status == 'rejected'])
            
            # Calculate total spent
            total_spent = sum(o.total_amount for o in orders if o.status == 'dispatched')
            
            return {
                'success': True,
                'statistics': {
                    'total_orders': total_orders,
                    'pending_orders': pending_orders,
                    'approved_orders': approved_orders,
                    'delivered_orders': delivered_orders,
                    'rejected_orders': rejected_orders,
                    'total_spent': total_spent
                }
            }
            
        except Exception as e:
            print(f"Get employee dashboard statistics error: {e}")
            return {'success': False, 'message': 'Failed to retrieve statistics'}
    
    # Helper methods
    
    def get_customer_statistics_internal(self, customer_id):
        """Internal method to get customer statistics"""
        try:
            # Get orders for this customer
            orders = Order.get_by_customer_id(customer_id)
            
            total_orders = len(orders)
            pending_dept_approval = len([o for o in orders if o.status == 'pending_dept_approval'])
            pending_hr_approval = len([o for o in orders if o.status == 'pending_hr_approval'])
            approved_orders = len([o for o in orders if o.status in ['approved', 'packed', 'ready_for_dispatch']])
            completed_orders = len([o for o in orders if o.status == 'dispatched'])
            
            # Calculate total spent (completed orders only)
            total_spent = sum(o.total_amount for o in orders if o.status == 'dispatched')
            
            # Get active users count
            users = User.get_by_customer_id(customer_id)
            active_users = len([u for u in users if u.is_active])
            
            # Get departments count
            departments = Department.get_by_customer_id(customer_id)
            departments_count = len([d for d in departments if d.is_active])
            
            # Calculate this month's orders
            thirty_days_ago = datetime.now() - timedelta(days=30)
            recent_orders = [o for o in orders if o.created_at >= thirty_days_ago]
            orders_this_month = len(recent_orders)
            
            return {
                'total_orders': total_orders,
                'pending_dept_approval': pending_dept_approval,
                'pending_hr_approval': pending_hr_approval,
                'approved_orders': approved_orders,
                'completed_orders': completed_orders,
                'total_spent': total_spent,
                'active_users': active_users,
                'departments': departments_count,
                'orders_this_month': orders_this_month
            }
            
        except Exception as e:
            print(f"Get customer statistics internal error: {e}")
            return {
                'total_orders': 0,
                'pending_dept_approval': 0,
                'pending_hr_approval': 0,
                'approved_orders': 0,
                'completed_orders': 0,
                'total_spent': 0,
                'active_users': 0,
                'departments': 0,
                'orders_this_month': 0
            }
    
    def get_department_statistics(self, department_id):
        """Get statistics for a specific department"""
        try:
            # Get orders for this department
            from config import config
            db = config.get_db()
            
            docs = db.collection('orders').where('department_id', '==', department_id).get()
            orders = [Order.from_dict(doc.to_dict()) for doc in docs]
            
            total_dept_orders = len(orders)
            pending_dept_orders = len([o for o in orders if o.status == 'pending_dept_approval'])
            
            # Get department users
            users_docs = db.collection('users').where('department_id', '==', department_id).get()
            dept_users = len([doc for doc in users_docs if doc.to_dict().get('is_active', True)])
            
            return {
                'dept_total_orders': total_dept_orders,
                'dept_pending_orders': pending_dept_orders,
                'dept_users': dept_users
            }
            
        except Exception as e:
            print(f"Get department statistics error: {e}")
            return {
                'dept_total_orders': 0,
                'dept_pending_orders': 0,
                'dept_users': 0
            }
    
    def upload_agreement_file(self, file, customer_id):
        """Upload agreement file to local or Firebase Storage"""
        try:
            # Validate file
            if not file or not file.filename:
                return None
            
            # Check file type
            allowed_extensions = {'pdf', 'jpg', 'jpeg', 'png'}
            file_extension = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
            
            if file_extension not in allowed_extensions:
                return None
            
            # Generate unique filename
            filename = f"agreement_{customer_id}_{uuid.uuid4().hex}.{file_extension}"
            
            # Get storage handler
            storage_handler = config.get_storage()
            
            if config.use_local_storage:
                # Local storage
                file_path = f"agreements/{filename}"
                full_path = os.path.join('uploads', file_path)
                
                # Ensure directory exists
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                
                # Save file
                file.save(full_path)
                
                return f"/uploads/{file_path}"
            else:
                # Firebase Storage
                blob = storage_handler.blob(f"agreements/{filename}")
                blob.upload_from_file(file.stream, content_type=file.content_type)
                blob.make_public()
                
                return blob.public_url
            
        except Exception as e:
            print(f"Upload agreement file error: {e}")
            return None
    
    def deactivate_customer(self, customer_id):
        """Deactivate customer (Vendor SuperAdmin only)"""
        try:
            current_user = self.auth.get_current_user()
            if not current_user or current_user.role != 'vendor_superadmin':
                return {'success': False, 'message': 'Only SuperAdmin can deactivate customers'}
            
            customer = Customer.get_by_id(customer_id)
            if not customer:
                return {'success': False, 'message': 'Customer not found'}
            
            # Deactivate customer
            customer.is_active = False
            
            # Deactivate all customer users
            users = User.get_by_customer_id(customer_id)
            for user in users:
                user.is_active = False
                user.save()
            
            if customer.save():
                return {
                    'success': True,
                    'message': 'Customer deactivated successfully'
                }
            else:
                return {'success': False, 'message': 'Failed to deactivate customer'}
                
        except Exception as e:
            print(f"Deactivate customer error: {e}")
            return {'success': False, 'message': 'Failed to deactivate customer'}
    
    def reactivate_customer(self, customer_id):
        """Reactivate customer (Vendor SuperAdmin only)"""
        try:
            current_user = self.auth.get_current_user()
            if not current_user or current_user.role != 'vendor_superadmin':
                return {'success': False, 'message': 'Only SuperAdmin can reactivate customers'}
            
            customer = Customer.get_by_id(customer_id)
            if not customer:
                return {'success': False, 'message': 'Customer not found'}
            
            # Reactivate customer
            customer.is_active = True
            
            if customer.save():
                return {
                    'success': True,
                    'message': 'Customer reactivated successfully'
                }
            else:
                return {'success': False, 'message': 'Failed to reactivate customer'}
                
        except Exception as e:
            print(f"Reactivate customer error: {e}")
            return {'success': False, 'message': 'Failed to reactivate customer'}

# Global customer controller instance
customer_controller = CustomerController()