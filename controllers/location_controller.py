# Updated Location Controller in location_controller.py
from flask import request, session
from models import Location
from controllers.auth_controller import auth_controller
from config import config

class LocationController:
    """Handle vendor store location management with pincode delivery zones"""
    
    def __init__(self):
        self.auth = auth_controller
        
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
                # Add serviceable states count for display
                location_dict['serviceable_states_count'] = len(location.serviceable_states) if location.serviceable_states else 0
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
            
            # Validate serviceable states
            serviceable_states = data.get('serviceable_states', [])
            if not serviceable_states:
                return {'success': False, 'message': 'At least one serviceable state must be selected'}
            
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
            location.serviceable_states = serviceable_states
            location.serviceable_pincodes = data.get('serviceable_pincodes', [])
            
            # Generate serviceable pincodes from states if not provided
            if not location.serviceable_pincodes:
                location.serviceable_pincodes = self.generate_pincodes_from_states(serviceable_states)
            
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
            
            # Update serviceable states and pincodes
            if 'serviceable_states' in data:
                location.serviceable_states = data['serviceable_states']
                
                # Regenerate serviceable pincodes if states changed
                if 'serviceable_pincodes' not in data:
                    location.serviceable_pincodes = self.generate_pincodes_from_states(data['serviceable_states'])
            
            if 'serviceable_pincodes' in data:
                location.serviceable_pincodes = data['serviceable_pincodes']
            
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
        """Get locations for dropdown selection WITHOUT pincode display"""
        try:
            current_user = self.auth.get_current_user()
            if not current_user or not current_user.role.startswith('vendor_'):
                return {'success': False, 'message': 'Access denied'}
            
            locations = Location.get_all_active()
            
            location_list = []
            for location in locations:
                location_list.append({
                    'location_id': location.location_id,
                    'name': location.name,
                    'pincode': getattr(location, 'pincode', None),
                    'serviceable_states': getattr(location, 'serviceable_states', []),
                    'serviceable_states_count': len(getattr(location, 'serviceable_states', []))
                })
            
            return {
                'success': True,
                'locations': location_list
            }
            
        except Exception as e:
            print(f"Get locations dropdown error: {e}")
            return {'success': False, 'message': 'Failed to retrieve locations'}
    
    def get_serviceable_locations_for_user(self, user_pincode):
        """Get locations that can deliver to user's pincode"""
        try:
            current_user = self.auth.get_current_user()
            if not current_user:
                return {'success': False, 'message': 'Authentication required'}
            
            if not user_pincode or len(user_pincode) != 6:
                return {'success': False, 'message': 'Valid 6-digit pincode required'}
            
            serviceable_locations = Location.get_locations_for_pincode(user_pincode)
            
            location_list = []
            for location in serviceable_locations:
                location_list.append({
                    'location_id': location.location_id,
                    'name': location.name,
                    'pincode': location.pincode,
                    'address': location.address
                })
            
            return {
                'success': True,
                'locations': location_list,
                'user_pincode': user_pincode
            }
            
        except Exception as e:
            print(f"Get serviceable locations error: {e}")
            return {'success': False, 'message': 'Failed to retrieve serviceable locations'}
    
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
    
    def get_states_list(self):
        """Get list of all states grouped by pincode zones"""
        try:
            current_user = self.auth.get_current_user()
            if not current_user or not current_user.role.startswith('vendor_'):
                return {'success': False, 'message': 'Access denied'}
            
            return {
                'success': True,
                'states_by_zone': self.pincode_states,
                'all_states': [state for states in self.pincode_states.values() for state in states]
            }
            
        except Exception as e:
            print(f"Get states list error: {e}")
            return {'success': False, 'message': 'Failed to retrieve states list'}
    
    def generate_pincodes_from_states(self, selected_states):
        """Generate list of pincode patterns from selected states"""
        try:
            serviceable_zones = []
            
            for zone, states in self.pincode_states.items():
                if any(state in selected_states for state in states):
                    serviceable_zones.append(zone)
            
            # This is a simplified approach - in a real system, you'd have a comprehensive pincode database
            # For now, we'll just return the zone patterns
            return serviceable_zones
            
        except Exception as e:
            print(f"Generate pincodes from states error: {e}")
            return []

# Global location controller instance
location_controller = LocationController()