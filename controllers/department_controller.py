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
        """Get departments for current customer (HR Admin only) - FIXED WITH BRANCH INFO"""
        try:
            current_user = self.auth.get_current_user()
            if not current_user or current_user.role != 'customer_hr_admin':
                return {'success': False, 'message': 'Only HR admins can manage departments'}
            
            departments = Department.get_by_customer_id(current_user.customer_id)
            
            # Get branches for this customer to map branch names
            from models import Branch
            branches = Branch.get_by_customer_id(current_user.customer_id)
            branch_map = {branch.branch_id: branch for branch in branches}
            
            dept_list = []
            for dept in departments:
                dept_dict = dept.to_dict()
                
                # Add branch information
                if dept.branch_id and dept.branch_id in branch_map:
                    branch = branch_map[dept.branch_id]
                    dept_dict['branch_name'] = branch.name
                    dept_dict['branch_address'] = branch.address
                    dept_dict['branch_id'] = branch.branch_id
                else:
                    dept_dict['branch_name'] = None
                    dept_dict['branch_address'] = None
                    dept_dict['branch_id'] = None
                
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
            
            # Sort departments by branch (unassigned first, then by branch name)
            dept_list.sort(key=lambda d: (d['branch_name'] or 'ZZZ_Unassigned', d['name']))
            
            return {
                'success': True,
                'departments': dept_list
            }
            
        except Exception as e:
            print(f"Get departments error: {e}")
            import traceback
            traceback.print_exc()
            return {'success': False, 'message': 'Failed to retrieve departments'}
    
    def get_department(self, department_id):
        """Get single department details - ENHANCED WITH BRANCH INFO"""
        try:
            current_user = self.auth.get_current_user()
            if not current_user or current_user.role != 'customer_hr_admin':
                return {'success': False, 'message': 'Only HR admins can view department details'}
            
            department = Department.get_by_id(department_id)
            if not department or department.customer_id != current_user.customer_id:
                return {'success': False, 'message': 'Department not found'}
            
            dept_dict = department.to_dict()
            
            # Add branch information
            if department.branch_id:
                from models import Branch
                branch = Branch.get_by_id(department.branch_id)
                if branch:
                    dept_dict['branch_name'] = branch.name
                    dept_dict['branch_address'] = branch.address
                    dept_dict['branch_phone'] = branch.phone
                    dept_dict['branch_email'] = branch.email
                    dept_dict['branch_manager'] = branch.manager_name
                else:
                    dept_dict['branch_name'] = 'Branch not found'
            else:
                dept_dict['branch_name'] = None
            
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
        
    
    
    def create_department(self):
        """Create new department (HR Admin only) - FIXED VERSION"""
        try:
            current_user = self.auth.get_current_user()
            if not current_user or current_user.role != 'customer_hr_admin':
                return {'success': False, 'message': 'Only HR admins can create departments'}
            
            data = request.get_json()
            
            if not data.get('name'):
                return {'success': False, 'message': 'Department name is required'}
            
            # Check if department name already exists for this customer
            existing_departments = Department.get_by_customer_id(current_user.customer_id)
            for dept in existing_departments:
                if dept.name.lower() == data['name'].lower():
                    return {'success': False, 'message': 'Department name already exists'}
            
            department = Department()
            department.customer_id = current_user.customer_id
            department.name = data['name']
            department.description = data.get('description', '')

            # Set branch_id if provided
            if 'branch_id' in data and data['branch_id']:
                department.branch_id = data['branch_id']
            
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
        
    def get_branches_for_customer(self):
        """Get branches for current customer"""
        try:
            current_user = self.auth.get_current_user()
            if not current_user or current_user.role != 'customer_hr_admin':
                return {'success': False, 'message': 'Only HR admins can view branches'}
            
            from models import Branch
            branches = Branch.get_by_customer_id(current_user.customer_id)
            
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
            
            # Update department info - INCLUDING branch_id
            department.name = data.get('name', department.name)
            department.description = data.get('description', department.description)
            
            # Handle branch_id update
            if 'branch_id' in data:
                department.branch_id = data['branch_id'] if data['branch_id'] else None
            
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
            import traceback
            traceback.print_exc()
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
        
    def assign_department_head(self, department_id):
        """Assign department head to a department (HR Admin only)"""
        try:
            current_user = self.auth.get_current_user()
            if not current_user or current_user.role != 'customer_hr_admin':
                return {'success': False, 'message': 'Only HR admins can assign department heads'}
            
            department = Department.get_by_id(department_id)
            if not department or department.customer_id != current_user.customer_id:
                return {'success': False, 'message': 'Department not found'}
            
            data = request.get_json()
            new_head_id = data.get('department_head_id')
            
            if not new_head_id:
                return {'success': False, 'message': 'Department head ID is required'}
            
            # Get the new department head user
            new_head = User.get_by_id(new_head_id)
            if not new_head or new_head.customer_id != current_user.customer_id:
                return {'success': False, 'message': 'User not found'}
            
            if new_head.role != 'customer_dept_head':
                return {'success': False, 'message': 'User must have Department Head role'}
            
            # Remove current department head from this department
            current_users = User.get_by_department_id(department_id)
            for user in current_users:
                if user.role == 'customer_dept_head':
                    user.department_id = None
                    user.save()
            
            # Remove new head from any other department
            if new_head.department_id and new_head.department_id != department_id:
                new_head.department_id = None
                new_head.save()
            
            # Assign new head to this department
            new_head.department_id = department_id
            new_head.save()
            
            return {
                'success': True,
                'message': 'Department head assigned successfully'
            }
            
        except Exception as e:
            print(f"Assign department head error: {e}")
            import traceback
            traceback.print_exc()
            return {'success': False, 'message': 'Failed to assign department head'}
    
    def delete_department(self, department_id):
        """Delete department and unassign users (HR Admin only) - UPDATED VERSION"""
        try:
            current_user = self.auth.get_current_user()
            if not current_user or current_user.role != 'customer_hr_admin':
                return {'success': False, 'message': 'Only HR admins can delete departments'}
            
            department = Department.get_by_id(department_id)
            if not department or department.customer_id != current_user.customer_id:
                return {'success': False, 'message': 'Department not found'}
            
            # Get users in this department and unassign them
            users_in_dept = User.get_by_department_id(department_id)
            for user in users_in_dept:
                user.department_id = None
                user.save()
            
            # Delete the department (hard delete from database)
            try:
                from config import config
                db = config.get_db()
                db.collection('departments').document(department_id).delete()
                
                return {
                    'success': True,
                    'message': f'Department deleted successfully. {len(users_in_dept)} users have been unassigned.'
                }
            except Exception as e:
                print(f"Error deleting department from database: {e}")
                return {'success': False, 'message': 'Failed to delete department'}
                
        except Exception as e:
            print(f"Delete department error: {e}")
            import traceback
            traceback.print_exc()
            return {'success': False, 'message': 'Failed to delete department'}

# Global department controller instance
department_controller = DepartmentController()