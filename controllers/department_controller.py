# Department Controller - Handle department management operations
from flask import request, session
from models import Department, User
from controllers.auth_controller import auth_controller
from config import config

class DepartmentController:
    """Handle department management operations"""
    
    def __init__(self):
        self.auth = auth_controller
    
    def get_departments(self):
        """Get departments for current customer (HR Admin only)"""
        try:
            current_user = self.auth.get_current_user()
            if not current_user or current_user.role != 'customer_hr_admin':
                return {'success': False, 'message': 'Only HR admins can manage departments'}
            
            departments = Department.get_by_customer_id(current_user.customer_id)
            
            dept_list = []
            for dept in departments:
                dept_dict = dept.to_dict()
                
                # Add user information
                users = User.get_by_department_id(dept.department_id)
                dept_dict['users'] = [
                    {
                        'user_id': u.user_id,
                        'username': u.username,
                        'full_name': u.full_name,
                        'email': u.email,
                        'role': u.role,
                        'is_active': u.is_active
                    } for u in users if u.is_active
                ]
                
                dept_dict['user_count'] = len(dept_dict['users'])
                dept_dict['active_users'] = len([u for u in dept_dict['users'] if u['is_active']])
                
                dept_list.append(dept_dict)
            
            return {
                'success': True,
                'departments': dept_list
            }
            
        except Exception as e:
            print(f"Get departments error: {e}")
            return {'success': False, 'message': 'Failed to retrieve departments'}
    
    def get_department(self, department_id):
        """Get single department details"""
        try:
            current_user = self.auth.get_current_user()
            if not current_user or current_user.role != 'customer_hr_admin':
                return {'success': False, 'message': 'Only HR admins can view department details'}
            
            department = Department.get_by_id(department_id)
            if not department or department.customer_id != current_user.customer_id:
                return {'success': False, 'message': 'Department not found'}
            
            dept_dict = department.to_dict()
            
            # Add detailed user information
            users = User.get_by_department_id(department_id)
            dept_dict['users'] = [
                {
                    'user_id': u.user_id,
                    'username': u.username,
                    'full_name': u.full_name,
                    'email': u.email,
                    'role': u.role,
                    'is_active': u.is_active
                } for u in users
            ]
            
            # Add statistics
            dept_dict['user_count'] = len(users)
            dept_dict['active_users'] = len([u for u in users if u.is_active])
            
            # Add order statistics (placeholder for now)
            dept_dict['total_orders'] = 0  # Can be implemented later
            
            return {
                'success': True,
                'department': dept_dict
            }
            
        except Exception as e:
            print(f"Get department error: {e}")
            return {'success': False, 'message': 'Failed to retrieve department'}
        
    def get_departments(self):
        """Get departments for current customer (HR Admin only) - FIXED VERSION"""
        try:
            current_user = self.auth.get_current_user()
            if not current_user or current_user.role != 'customer_hr_admin':
                return {'success': False, 'message': 'Only HR admins can manage departments'}
            
            departments = Department.get_by_customer_id(current_user.customer_id)
            
            dept_list = []
            for dept in departments:
                dept_dict = dept.to_dict()
                
                # Add user information - FIXED: Use the correct method
                users = User.get_by_department_id(dept.department_id)
                dept_dict['users'] = [
                    {
                        'user_id': u.user_id,
                        'username': u.username,
                        'full_name': u.full_name,
                        'email': u.email,
                        'role': u.role,
                        'is_active': u.is_active
                    } for u in users if u.is_active
                ]
                
                dept_dict['user_count'] = len(dept_dict['users'])
                dept_dict['active_users'] = len([u for u in dept_dict['users'] if u['is_active']])
                
                dept_list.append(dept_dict)
            
            return {
                'success': True,
                'departments': dept_list
            }
            
        except Exception as e:
            print(f"Get departments error: {e}")
            import traceback
            traceback.print_exc()
            return {'success': False, 'message': 'Failed to retrieve departments'}
    
    def create_department(self):
        """Create new department (HR Admin only)"""
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
    
    def update_department(self, department_id):
        """Update department and assign users (HR Admin only)"""
        try:
            current_user = self.auth.get_current_user()
            if not current_user or current_user.role != 'customer_hr_admin':
                return {'success': False, 'message': 'Only HR admins can update departments'}
            
            department = Department.get_by_id(department_id)
            if not department or department.customer_id != current_user.customer_id:
                return {'success': False, 'message': 'Department not found'}
            
            data = request.get_json()
            
            # Update department info
            department.name = data.get('name', department.name)
            department.description = data.get('description', department.description)
            
            if department.save():
                # Handle user assignments
                if 'user_assignments' in data:
                    self.update_user_assignments(department_id, data['user_assignments'], current_user.customer_id)
                
                return {
                    'success': True,
                    'message': 'Department updated successfully'
                }
            else:
                return {'success': False, 'message': 'Failed to update department'}
                
        except Exception as e:
            print(f"Update department error: {e}")
            return {'success': False, 'message': 'Failed to update department'}
    
    def update_user_assignments(self, department_id, assigned_user_ids, customer_id):
        """Update user assignments for a department"""
        try:
            # Get all users in the customer organization
            all_users = User.get_by_customer_id(customer_id)
            
            for user in all_users:
                # Only update employees and department heads
                if user.role in ['customer_employee', 'customer_dept_head']:
                    if user.user_id in assigned_user_ids:
                        # Assign user to this department
                        user.department_id = department_id
                    elif user.department_id == department_id:
                        # Remove user from this department
                        user.department_id = None
                    
                    user.save()
            
            return True
            
        except Exception as e:
            print(f"Update user assignments error: {e}")
            return False
    
    def delete_department(self, department_id):
        """Deactivate department (HR Admin only)"""
        try:
            current_user = self.auth.get_current_user()
            if not current_user or current_user.role != 'customer_hr_admin':
                return {'success': False, 'message': 'Only HR admins can delete departments'}
            
            department = Department.get_by_id(department_id)
            if not department or department.customer_id != current_user.customer_id:
                return {'success': False, 'message': 'Department not found'}
            
            # Check if department has users
            users = User.get_by_department_id(department_id)
            if users:
                return {'success': False, 'message': 'Cannot delete department with assigned users. Please reassign users first.'}
            
            # Soft delete by deactivating
            department.is_active = False
            
            if department.save():
                return {
                    'success': True,
                    'message': 'Department deactivated successfully'
                }
            else:
                return {'success': False, 'message': 'Failed to delete department'}
                
        except Exception as e:
            print(f"Delete department error: {e}")
            return {'success': False, 'message': 'Failed to delete department'}

# Global department controller instance
department_controller = DepartmentController()