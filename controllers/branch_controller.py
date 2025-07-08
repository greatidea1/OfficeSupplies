# Branch Controller - Handle branch management operations
from flask import request, session
from models import Branch, User, Department
from controllers.auth_controller import auth_controller
from config import config

class BranchController:
    """Handle branch management operations"""
    
    def __init__(self):
        self.auth = auth_controller
    
    def get_branches(self):
        """Get branches for current customer (HR Admin only)"""
        try:
            current_user = self.auth.get_current_user()
            if not current_user or current_user.role != 'customer_hr_admin':
                return {'success': False, 'message': 'Only HR admins can manage branches'}
            
            branches = Branch.get_by_customer_id(current_user.customer_id)
            
            branch_list = []
            for branch in branches:
                branch_dict = branch.to_dict()
                
                # Add user and department counts
                users = User.get_by_branch_id(branch.branch_id)
                departments = Department.get_by_branch_id(branch.branch_id)
                
                branch_dict['user_count'] = len([u for u in users if u.is_active])
                branch_dict['department_count'] = len([d for d in departments if d.is_active])
                
                branch_list.append(branch_dict)
            
            return {
                'success': True,
                'branches': branch_list
            }
            
        except Exception as e:
            print(f"Get branches error: {e}")
            import traceback
            traceback.print_exc()
            return {'success': False, 'message': 'Failed to retrieve branches'}
    
    def get_branch(self, branch_id):
        """Get single branch details"""
        try:
            current_user = self.auth.get_current_user()
            if not current_user or current_user.role != 'customer_hr_admin':
                return {'success': False, 'message': 'Only HR admins can view branch details'}
            
            branch = Branch.get_by_id(branch_id)
            if not branch or branch.customer_id != current_user.customer_id:
                return {'success': False, 'message': 'Branch not found'}
            
            branch_dict = branch.to_dict()
            
            # Add detailed information
            users = User.get_by_branch_id(branch_id)
            departments = Department.get_by_branch_id(branch_id)
            
            branch_dict['users'] = [
                {
                    'user_id': u.user_id,
                    'username': u.username,
                    'full_name': u.full_name,
                    'email': u.email,
                    'role': u.role,
                    'is_active': u.is_active,
                    'department_id': u.department_id
                } for u in users
            ]
            
            branch_dict['departments'] = [
                {
                    'department_id': d.department_id,
                    'name': d.name,
                    'description': d.description,
                    'is_active': d.is_active
                } for d in departments
            ]
            
            return {
                'success': True,
                'branch': branch_dict
            }
            
        except Exception as e:
            print(f"Get branch error: {e}")
            return {'success': False, 'message': 'Failed to retrieve branch'}
    
    def create_branch(self):
        """Create new branch (HR Admin only)"""
        try:
            current_user = self.auth.get_current_user()
            if not current_user or current_user.role != 'customer_hr_admin':
                return {'success': False, 'message': 'Only HR admins can create branches'}
            
            data = request.get_json()
            
            # Validate required fields
            required_fields = ['name', 'address', 'pincode']
            for field in required_fields:
                if field not in data or not data[field]:
                    return {'success': False, 'message': f'{field.replace("_", " ").title()} is required'}
            
            # Validate pincode (6 digits only)
            pincode = data['pincode'].strip()
            if not pincode.isdigit() or len(pincode) != 6:
                return {'success': False, 'message': 'Pincode must be exactly 6 digits'}
            
            # Check if branch name already exists for this customer
            existing_branches = Branch.get_by_customer_id(current_user.customer_id)
            for branch in existing_branches:
                if branch.name.lower() == data['name'].lower():
                    return {'success': False, 'message': 'Branch name already exists'}
            
            branch = Branch()
            branch.customer_id = current_user.customer_id
            branch.name = data['name']
            branch.address = data['address']
            branch.pincode = pincode
            branch.phone = data.get('phone', '')
            branch.email = data.get('email', '')
            branch.manager_name = data.get('manager_name', '')
            
            if branch.save():
                return {
                    'success': True,
                    'message': 'Branch created successfully',
                    'branch_id': branch.branch_id
                }
            else:
                return {'success': False, 'message': 'Failed to create branch'}
                
        except Exception as e:
            print(f"Create branch error: {e}")
            import traceback
            traceback.print_exc()
            return {'success': False, 'message': 'Failed to create branch'}

    def update_branch(self, branch_id):
        """Update branch information (HR Admin only)"""
        try:
            current_user = self.auth.get_current_user()
            if not current_user or current_user.role != 'customer_hr_admin':
                return {'success': False, 'message': 'Only HR admins can update branches'}
            
            branch = Branch.get_by_id(branch_id)
            if not branch or branch.customer_id != current_user.customer_id:
                return {'success': False, 'message': 'Branch not found'}
            
            data = request.get_json()
            
            # Validate pincode if provided
            if 'pincode' in data and data['pincode']:
                pincode = data['pincode'].strip()
                if not pincode.isdigit() or len(pincode) != 6:
                    return {'success': False, 'message': 'Pincode must be exactly 6 digits'}
            
            # Update allowed fields
            updateable_fields = ['name', 'address', 'pincode', 'phone', 'email', 'manager_name', 'is_active']
            
            for field in updateable_fields:
                if field in data:
                    if field == 'is_active':
                        setattr(branch, field, bool(data[field]))
                    elif field == 'pincode' and data[field]:
                        setattr(branch, field, data[field].strip())
                    else:
                        setattr(branch, field, data[field])
            
            if branch.save():
                return {
                    'success': True,
                    'message': 'Branch updated successfully'
                }
            else:
                return {'success': False, 'message': 'Failed to update branch'}
                
        except Exception as e:
            print(f"Update branch error: {e}")
            return {'success': False, 'message': 'Failed to update branch'}
    
    def delete_branch(self, branch_id):
        """Delete branch and unassign users/departments (HR Admin only)"""
        try:
            current_user = self.auth.get_current_user()
            if not current_user or current_user.role != 'customer_hr_admin':
                return {'success': False, 'message': 'Only HR admins can delete branches'}
            
            branch = Branch.get_by_id(branch_id)
            if not branch or branch.customer_id != current_user.customer_id:
                return {'success': False, 'message': 'Branch not found'}
            
            # Get users and departments in this branch and unassign them
            users_in_branch = User.get_by_branch_id(branch_id)
            departments_in_branch = Department.get_by_branch_id(branch_id)
            
            for user in users_in_branch:
                user.branch_id = None
                user.save()
            
            for department in departments_in_branch:
                department.branch_id = None
                department.save()
            
            # Delete the branch (hard delete from database)
            try:
                from config import config
                db = config.get_db()
                db.collection('branches').document(branch_id).delete()
                
                return {
                    'success': True,
                    'message': f'Branch deleted successfully. {len(users_in_branch)} users and {len(departments_in_branch)} departments have been unassigned.'
                }
            except Exception as e:
                print(f"Error deleting branch from database: {e}")
                return {'success': False, 'message': 'Failed to delete branch'}
                
        except Exception as e:
            print(f"Delete branch error: {e}")
            import traceback
            traceback.print_exc()
            return {'success': False, 'message': 'Failed to delete branch'}
    
    def get_company_info(self):
        """Get company information for current customer"""
        try:
            current_user = self.auth.get_current_user()
            if not current_user or not current_user.role.startswith('customer_'):
                return {'success': False, 'message': 'Only customer users can view company info'}
            
            from models import Customer
            customer = Customer.get_by_id(current_user.customer_id)
            if not customer:
                return {'success': False, 'message': 'Customer not found'}
            
            return {
                'success': True,
                'company': {
                    'customer_id': customer.customer_id,
                    'company_name': customer.company_name,
                    'company_alias': getattr(customer, 'company_alias', ''),
                    'email': customer.email,
                    'postal_address': customer.postal_address,
                    'primary_phone': customer.primary_phone
                }
            }
            
        except Exception as e:
            print(f"Get company info error: {e}")
            return {'success': False, 'message': 'Failed to retrieve company information'}
    
    def update_company_info(self):
        """Update company alias (HR Admin only)"""
        try:
            current_user = self.auth.get_current_user()
            if not current_user or current_user.role != 'customer_hr_admin':
                return {'success': False, 'message': 'Only HR admins can update company information'}
            
            from models import Customer
            customer = Customer.get_by_id(current_user.customer_id)
            if not customer:
                return {'success': False, 'message': 'Customer not found'}
            
            data = request.get_json()
            company_alias = data.get('company_alias', '')
            
            # Update company alias
            customer.company_alias = company_alias
            
            if customer.save():
                return {
                    'success': True,
                    'message': 'Company information updated successfully'
                }
            else:
                return {'success': False, 'message': 'Failed to update company information'}
                
        except Exception as e:
            print(f"Update company info error: {e}")
            return {'success': False, 'message': 'Failed to update company information'}

# Global branch controller instance
branch_controller = BranchController()