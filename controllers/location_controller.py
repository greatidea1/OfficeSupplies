# Location Controller - Handle vendor store locations
from flask import request, session
from models import Location
from controllers.auth_controller import auth_controller
from config import config

class LocationController:
    """Handle vendor store location management"""
    
    def __init__(self):
        self.auth = auth_controller
    
    def get_locations(self):
        """Get locations list (Vendor users only)"""
        try:
            current_user = self.auth.get_current_user()
            if not current_user or not current_user.role.startswith('vendor_'):
                return {'success': False, 'message': 'Only vendor users can view locations'}
            
            locations = Location.get_all_active()
            
            location_list = []
            for location in locations:
                location_dict = location.to_dict()
                location_list.append(location_dict)
            
            return {
                'success': True,
                'locations': location_list
            }
            
        except Exception as e:
            print(f"Get locations error: {e}")
            return {'success': False, 'message': 'Failed to retrieve locations'}
    
    def create_location(self):
        """Create new location (SuperAdmin/Admin only)"""
        try:
            current_user = self.auth.get_current_user()
            if not current_user or current_user.role not in ['vendor_superadmin', 'vendor_admin']:
                return {'success': False, 'message': 'Only SuperAdmin/Admin can create locations'}
            
            data = request.get_json()
            
            # Validate required fields
            required_fields = ['name', 'address', 'pincode']
            for field in required_fields:
                if field not in data or not data[field].strip():
                    return {'success': False, 'message': f'{field.replace("_", " ").title()} is required'}
            
            # Validate pincode (6 digits only)
            pincode = data['pincode'].strip()
            if not pincode.isdigit() or len(pincode) != 6:
                return {'success': False, 'message': 'Pincode must be exactly 6 digits'}
            
            # Check if location name already exists
            existing_location = Location.get_by_name(data['name'].strip())
            if existing_location:
                return {'success': False, 'message': 'Location name already exists'}
            
            # Create new location
            location = Location()
            location.name = data['name'].strip()
            location.address = data['address'].strip()
            location.pincode = pincode
            location.phone = data.get('phone', '').strip()
            location.manager_name = data.get('manager_name', '').strip()
            location.description = data.get('description', '').strip()
            
            if location.save():
                return {
                    'success': True,
                    'message': 'Location created successfully',
                    'location_id': location.location_id
                }
            else:
                return {'success': False, 'message': 'Failed to create location'}
                
        except Exception as e:
            print(f"Create location error: {e}")
            return {'success': False, 'message': 'Failed to create location'}
    
    def get_location(self, location_id):
        """Get single location details"""
        try:
            current_user = self.auth.get_current_user()
            if not current_user or not current_user.role.startswith('vendor_'):
                return {'success': False, 'message': 'Only vendor users can view location details'}
            
            location = Location.get_by_id(location_id)
            if not location:
                return {'success': False, 'message': 'Location not found'}
            
            return {
                'success': True,
                'location': location.to_dict()
            }
            
        except Exception as e:
            print(f"Get location error: {e}")
            return {'success': False, 'message': 'Failed to retrieve location'}
    
    def update_location(self, location_id):
        """Update existing location (SuperAdmin/Admin only)"""
        try:
            current_user = self.auth.get_current_user()
            if not current_user or current_user.role not in ['vendor_superadmin', 'vendor_admin']:
                return {'success': False, 'message': 'Only SuperAdmin/Admin can update locations'}
            
            location = Location.get_by_id(location_id)
            if not location:
                return {'success': False, 'message': 'Location not found'}
            
            data = request.get_json()
            
            # Validate pincode if provided
            if 'pincode' in data and data['pincode']:
                pincode = data['pincode'].strip()
                if not pincode.isdigit() or len(pincode) != 6:
                    return {'success': False, 'message': 'Pincode must be exactly 6 digits'}
            
            # Update allowed fields
            updateable_fields = ['name', 'address', 'pincode', 'phone', 'manager_name', 'description', 'is_active']
            
            for field in updateable_fields:
                if field in data:
                    if field == 'is_active':
                        setattr(location, field, bool(data[field]))
                    elif field == 'pincode' and data[field]:
                        setattr(location, field, data[field].strip())
                    else:
                        setattr(location, field, data[field].strip() if isinstance(data[field], str) else data[field])
            
            # Check for duplicate name (excluding current location)
            if 'name' in data:
                existing_location = Location.get_by_name(data['name'].strip())
                if existing_location and existing_location.location_id != location_id:
                    return {'success': False, 'message': 'Location name already exists'}
            
            if location.save():
                return {
                    'success': True,
                    'message': 'Location updated successfully'
                }
            else:
                return {'success': False, 'message': 'Failed to update location'}
                
        except Exception as e:
            print(f"Update location error: {e}")
            return {'success': False, 'message': 'Failed to update location'}
    
    def delete_location(self, location_id):
        """Soft delete location (SuperAdmin only)"""
        try:
            current_user = self.auth.get_current_user()
            if not current_user or current_user.role != 'vendor_superadmin':
                return {'success': False, 'message': 'Only SuperAdmin can delete locations'}
            
            location = Location.get_by_id(location_id)
            if not location:
                return {'success': False, 'message': 'Location not found'}
            
            # Check if location has products
            from models import Product
            products = Product.get_by_location_id(location_id)
            if products:
                return {'success': False, 'message': f'Cannot delete location. {len(products)} products are associated with this location.'}
            
            # Soft delete by setting is_active to False
            location.is_active = False
            
            if location.save():
                return {
                    'success': True,
                    'message': 'Location deleted successfully'
                }
            else:
                return {'success': False, 'message': 'Failed to delete location'}
                
        except Exception as e:
            print(f"Delete location error: {e}")
            return {'success': False, 'message': 'Failed to delete location'}
    
    def get_locations_dropdown(self):
        """Get locations for dropdown selection with pincode display"""
        try:
            current_user = self.auth.get_current_user()
            if not current_user or not current_user.role.startswith('vendor_'):
                return {'success': False, 'message': 'Access denied'}
            
            locations = Location.get_all_active()
            
            location_list = []
            for location in locations:
                # Include pincode in display name
                display_name = location.name
                if hasattr(location, 'pincode') and location.pincode:
                    display_name += f" ({location.pincode})"
                
                location_list.append({
                    'location_id': location.location_id,
                    'name': location.name,
                    'display_name': display_name,
                    'pincode': getattr(location, 'pincode', None)
                })
            
            return {
                'success': True,
                'locations': location_list
            }
            
        except Exception as e:
            print(f"Get locations dropdown error: {e}")
            return {'success': False, 'message': 'Failed to retrieve locations'}

# Global location controller instance
location_controller = LocationController()