# Product Controller - Enhanced with location-based product filtering
from flask import request, session
from models import Product, User, Location
from controllers.auth_controller import auth_controller
from config import config
import uuid, random

class ProductController:
    """Handle product management operations with location-based filtering"""
    
    def __init__(self):
        self.auth = auth_controller
    
    def get_products(self):
        """Get products list with location-based filtering for customer users"""
        try:
            # Authentication check
            current_user = self.auth.get_current_user()
            if not current_user:
                return {'success': False, 'message': 'Authentication required'}
            
            print(f"User {current_user.username} with role {current_user.role} requesting products")
            
            # Get query parameters with defaults and proper error handling
            search = request.args.get('search', '') if request.args else ''
            category = request.args.get('category', '') if request.args else ''
            location_id = request.args.get('location_id', '') if request.args else ''
            sort_by = request.args.get('sort', 'name_asc') if request.args else 'name_asc'
            
            try:
                page = int(request.args.get('page', 1)) if request.args else 1
                per_page = int(request.args.get('per_page', 50)) if request.args else 50
            except (ValueError, TypeError):
                page = 1
                per_page = 50
            
            # For customer users, filter products based on their branch location
            if current_user.role.startswith('customer_'):
                products = self.get_location_filtered_products(current_user)
            else:
                # Vendor users see all products with optional location filter
                try:
                    if location_id:
                        products = Product.get_all_active_with_location(location_id)
                    else:
                        products = Product.get_all_active()
                except Exception as e:
                    print(f"Error fetching products: {e}")
                    return {'success': False, 'message': 'Failed to fetch products from database'}
            
            # Apply search and category filters
            if search or category:
                filtered_products = []
                for product in products:
                    match = True
                    
                    # Search filter - comprehensive search across multiple fields
                    if search:
                        search_lower = search.lower()
                        match = (
                            search_lower in (product.product_name or '').lower() or
                            search_lower in (product.product_make or '').lower() or
                            search_lower in (product.product_model or '').lower() or
                            search_lower in (product.category or '').lower() or
                            search_lower in (product.description or '').lower()
                        )
                    
                    # Category filter
                    if match and category:
                        match = product.category == category
                    
                    if match:
                        filtered_products.append(product)
                
                products = filtered_products
            
            print(f"Found {len(products)} products after filtering")
            
            # Handle empty results
            if not products:
                return {
                    'success': True,
                    'products': [],
                    'categories': [],
                    'pagination': {'page': 1, 'per_page': per_page, 'total': 0, 'pages': 0},
                    'filters': {'search': search, 'category': category, 'location_id': location_id, 'sort_by': sort_by}
                }
            
            # Apply sorting with proper error handling
            try:
                if sort_by == 'name_asc':
                    products.sort(key=lambda p: (p.product_name or '').lower())
                elif sort_by == 'name_desc':
                    products.sort(key=lambda p: (p.product_name or '').lower(), reverse=True)
                elif sort_by == 'price_asc':
                    products.sort(key=lambda p: p.price or 0)
                elif sort_by == 'price_desc':
                    products.sort(key=lambda p: p.price or 0, reverse=True)
                elif sort_by == 'stock_asc':
                    products.sort(key=lambda p: p.quantity or 0)
                elif sort_by == 'stock_desc':
                    products.sort(key=lambda p: p.quantity or 0, reverse=True)
            except Exception as e:
                print(f"Error sorting products: {e}")
            
            # Apply pagination
            total_products = len(products)
            start_idx = (page - 1) * per_page
            end_idx = start_idx + per_page
            paginated_products = products[start_idx:end_idx]
            
            # Convert to dict and add additional info with multi-location support
            product_list = []
            for product in paginated_products:
                try:
                    product_dict = product.to_dict()
                    
                    # Ensure required fields exist with defaults
                    product_dict['price'] = product_dict.get('price', 0)
                    product_dict['gst_rate'] = product_dict.get('gst_rate', 18.0)
                    
                    # Add computed fields
                    product_dict['is_low_stock'] = product.is_low_stock() if hasattr(product, 'is_low_stock') else False
                    
                    # Calculate pricing with GST
                    base_price = product_dict['price']
                    gst_rate = product_dict['gst_rate']
                    
                    product_dict['gst_amount'] = (base_price * gst_rate) / 100
                    product_dict['price_including_gst'] = base_price + product_dict['gst_amount']
                    
                    # Handle multiple locations with enhanced display
                    location_names = []
                    try:
                        if hasattr(product, 'location_ids') and product.location_ids:
                            # Multi-location support
                            for location_id in product.location_ids:
                                location = Location.get_by_id(location_id)
                                if location:
                                    location_display = location.name
                                    if hasattr(location, 'pincode') and location.pincode:
                                        location_display += f" ({location.pincode})"
                                    location_names.append(location_display)
                            product_dict['location_names'] = location_names
                            product_dict['location_ids'] = product.location_ids
                            
                        elif hasattr(product, 'location_id') and product.location_id:
                            # Backward compatibility for single location
                            location = Location.get_by_id(product.location_id)
                            if location:
                                location_display = location.name
                                if hasattr(location, 'pincode') and location.pincode:
                                    location_display += f" ({location.pincode})"
                                location_names.append(location_display)
                            product_dict['location_names'] = location_names
                            product_dict['location_ids'] = [product.location_id] if product.location_id else []
                            
                        else:
                            # No location data
                            product_dict['location_names'] = []
                            product_dict['location_ids'] = []
                            
                    except Exception as location_error:
                        print(f"Error processing location data for product {product.product_id}: {location_error}")
                        product_dict['location_names'] = []
                        product_dict['location_ids'] = []
                    
                    # Handle customer-specific pricing
                    if current_user.role.startswith('customer_') and current_user.customer_id:
                        try:
                            custom_price = self.get_customer_pricing(product.product_id, current_user.customer_id)
                            if custom_price is not None and custom_price > 0:
                                product_dict['custom_price'] = custom_price
                                product_dict['gst_amount'] = (custom_price * gst_rate) / 100
                                product_dict['price_including_gst'] = custom_price + product_dict['gst_amount']
                                print(f"Applied custom price {custom_price} for product {product.product_id}")
                        except Exception as pricing_error:
                            print(f"Error getting custom pricing for product {product.product_id}: {pricing_error}")
                    
                    # Role-based product filtering
                    if current_user.role.startswith('vendor_'):
                        # Vendors see all products
                        product_list.append(product_dict)
                    elif current_user.role.startswith('customer_'):
                        # Customers only see products with valid pricing
                        effective_price = product_dict.get('custom_price', product_dict.get('price', 0))
                        if effective_price > 0:
                            product_list.append(product_dict)
                    
                except Exception as product_error:
                    print(f"Error processing product {getattr(product, 'product_id', 'unknown')}: {product_error}")
                    continue
            
            # Get categories for filtering with error handling
            try:
                categories = self.get_product_categories()
            except Exception as category_error:
                print(f"Error getting categories: {category_error}")
                categories = []
            
            # Prepare final result
            result = {
                'success': True,
                'products': product_list,
                'categories': categories,
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total': total_products,
                    'pages': (total_products + per_page - 1) // per_page
                },
                'filters': {
                    'search': search,
                    'category': category,
                    'location_id': location_id,
                    'sort_by': sort_by
                }
            }
            
            print(f"Returning {len(product_list)} products to {current_user.role} user")
            return result
            
        except Exception as e:
            print(f"Get products error: {e}")
            import traceback
            traceback.print_exc()
            return {'success': False, 'message': f'Failed to retrieve products: {str(e)}'}
    

    def create_product(self):
        """Create new product with multi-location support and image upload"""
        try:
            current_user = self.auth.get_current_user()
            if not current_user or not current_user.role.startswith('vendor_'):
                return {'success': False, 'message': 'Only vendor users can create products'}
            
            # Handle form data (multipart for image upload)
            data = request.form.to_dict()
            
            # Validate required fields
            required_fields = ['product_name', 'category', 'quantity']
            for field in required_fields:
                if not data.get(field):
                    return {'success': False, 'message': f'{field.replace("_", " ").title()} is required'}
            
            # Get selected locations from multi-select
            location_ids = request.form.getlist('location_ids')
            if not location_ids:
                return {'success': False, 'message': 'At least one location must be selected'}
            
            # Validate locations exist
            from models import Location
            valid_locations = []
            for location_id in location_ids:
                location = Location.get_by_id(location_id)
                if location and location.is_active:
                    valid_locations.append(location_id)
                else:
                    return {'success': False, 'message': f'Location {location_id} not found or inactive'}
            
            if not valid_locations:
                return {'success': False, 'message': 'No valid locations selected'}
            
            # Validate category exists
            categories = self.get_product_categories()
            if data['category'] not in categories:
                return {'success': False, 'message': 'Invalid category selected'}
            
            # Create new product
            from models import Product
            product = Product()
            
            # Generate item number
            product.item_no = self.generate_item_number()
            
            # Set basic fields
            product.product_name = data['product_name']
            product.category = data['category']
            product.product_make = data.get('product_make', '')
            product.product_model = data.get('product_model', '')
            product.description = data.get('description', '')
            
            # Set numeric fields with validation
            try:
                product.quantity = int(data.get('quantity', 0))
                product.low_stock_threshold = int(data.get('low_stock_threshold', 10))
                product.price = float(data.get('price', 0))
                product.gst_rate = float(data.get('gst_rate', 18))
            except (ValueError, TypeError):
                return {'success': False, 'message': 'Invalid numeric values provided'}
            
            # Set other fields
            product.hsn_code = data.get('hsn_code', '')
            
            # Set locations
            product.location_ids = valid_locations
            product.location_id = valid_locations[0]  # Backward compatibility
            
            # Handle image upload
            image_urls = []
            if 'product_image' in request.files:
                image_file = request.files['product_image']
                if image_file and image_file.filename:
                    image_url = self.upload_product_image(image_file, product.product_id)
                    if image_url:
                        image_urls.append(image_url)
                    else:
                        return {'success': False, 'message': 'Failed to upload product image'}
            
            product.image_urls = image_urls
            
            # Save product
            if product.save():
                print(f"Product created successfully: {product.product_name} (ID: {product.product_id})")
                
                return {
                    'success': True,
                    'message': 'Product created successfully',
                    'product_id': product.product_id,
                    'item_no': product.item_no,
                    'product': product.to_dict()
                }
            else:
                return {'success': False, 'message': 'Failed to save product to database'}
                
        except Exception as e:
            print(f"Create product error: {e}")
            import traceback
            traceback.print_exc()
            return {'success': False, 'message': f'Failed to create product: {str(e)}'}
        
    def generate_item_number(self):
        """Generate unique item number in format itXXX"""
        try:
            from models import Product
            import random
            
            # Generate a random 3-digit number
            for _ in range(100):  # Try up to 100 times
                number = random.randint(100, 999)
                item_no = f"it{number}"
                
                # Check if item number already exists
                existing_product = Product.get_by_item_no(item_no)
                if not existing_product:
                    return item_no
            
            # If we couldn't generate a unique number, use timestamp
            from datetime import datetime
            timestamp = datetime.now().strftime('%H%M%S')
            return f"it{timestamp}"
            
        except Exception as e:
            print(f"Generate item number error: {e}")
            # Fallback to timestamp-based generation
            from datetime import datetime
            timestamp = datetime.now().strftime('%H%M%S')
            return f"it{timestamp}"

    def update_product(self, product_id):
        """Update product with support for both JSON and multipart form data"""
        try:
            current_user = self.auth.get_current_user()
            if not current_user or not current_user.role.startswith('vendor_'):
                return {'success': False, 'message': 'Only vendor users can update products'}
            
            from models import Product
            product = Product.get_by_id(product_id)
            if not product:
                return {'success': False, 'message': 'Product not found'}
            
            # Handle both form data and JSON
            if request.content_type and request.content_type.startswith('multipart/form-data'):
                # Handle multipart form data (with file upload)
                data = request.form.to_dict()
                
                # Handle image upload
                if 'product_image' in request.files:
                    image_file = request.files['product_image']
                    if image_file and image_file.filename:
                        # Upload image and get URL
                        image_url = self.upload_product_image(image_file, product_id)
                        if image_url:
                            product.image_urls = [image_url]
                        else:
                            return {'success': False, 'message': 'Failed to upload product image'}
                
                # Handle location_ids from form data
                location_ids = request.form.getlist('location_ids')
                if location_ids:
                    data['location_ids'] = location_ids
                    
            else:
                # Handle JSON data
                data = request.get_json()
                if not data:
                    return {'success': False, 'message': 'No data provided'}
            
            # Update basic fields
            updateable_fields = [
                'product_name', 'category', 'product_make', 'product_model',
                'description', 'price', 'quantity', 'gst_rate', 'hsn_code',
                'low_stock_threshold'
            ]
            
            for field in updateable_fields:
                if field in data:
                    if field in ['price', 'quantity', 'gst_rate', 'low_stock_threshold']:
                        # Convert to appropriate numeric type
                        try:
                            if field == 'quantity' or field == 'low_stock_threshold':
                                setattr(product, field, int(data[field]) if data[field] else 0)
                            else:
                                setattr(product, field, float(data[field]) if data[field] else 0.0)
                        except (ValueError, TypeError):
                            return {'success': False, 'message': f'Invalid value for {field}'}
                    else:
                        setattr(product, field, data[field])
            
            # Handle location_ids (multi-location support)
            if 'location_ids' in data:
                location_ids = data['location_ids']
                if isinstance(location_ids, str):
                    # Single location ID as string
                    location_ids = [location_ids] if location_ids else []
                elif not isinstance(location_ids, list):
                    return {'success': False, 'message': 'location_ids must be a list'}
                
                # Validate locations exist
                from models import Location
                valid_locations = []
                for location_id in location_ids:
                    location = Location.get_by_id(location_id)
                    if location:
                        valid_locations.append(location_id)
                    else:
                        return {'success': False, 'message': f'Location {location_id} not found'}
                
                product.location_ids = valid_locations
                
                # For backward compatibility, set location_id to first location
                if valid_locations:
                    product.location_id = valid_locations[0]
                else:
                    product.location_id = None
            
            # Validate required fields
            if not product.product_name or not product.category:
                return {'success': False, 'message': 'Product name and category are required'}
            
            if not product.location_ids and not product.location_id:
                return {'success': False, 'message': 'At least one location must be selected'}
            
            # Save updated product
            if product.save():
                return {
                    'success': True,
                    'message': 'Product updated successfully',
                    'product': product.to_dict()
                }
            else:
                return {'success': False, 'message': 'Failed to update product'}
                
        except Exception as e:
            print(f"Update product error: {e}")
            import traceback
            traceback.print_exc()
            return {'success': False, 'message': f'Failed to update product: {str(e)}'}

    def upload_product_image(self, image_file, product_id):
        """Upload product image and return URL"""
        try:
            import os
            from werkzeug.utils import secure_filename
            import uuid
            
            # Validate file type
            allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
            filename = secure_filename(image_file.filename)
            
            if not filename or '.' not in filename:
                return None
            
            file_extension = filename.rsplit('.', 1)[1].lower()
            if file_extension not in allowed_extensions:
                return None
            
            # Validate file size (16MB max)
            image_file.seek(0, os.SEEK_END)
            file_size = image_file.tell()
            image_file.seek(0)
            
            if file_size > 16 * 1024 * 1024:  # 16MB
                return None
            
            # Generate unique filename
            unique_filename = f"{product_id}_{uuid.uuid4().hex[:8]}.{file_extension}"
            
            # Create upload directory if it doesn't exist
            upload_dir = os.path.join('uploads', 'products')
            os.makedirs(upload_dir, exist_ok=True)
            
            # Save file
            file_path = os.path.join(upload_dir, unique_filename)
            image_file.save(file_path)
            
            print(f"Product image uploaded successfully: {file_path}")
            
            # Return relative URL
            return f"/uploads/products/{unique_filename}"
            
        except Exception as e:
            print(f"Upload product image error: {e}")
            return None
    
    def get_location_filtered_products(self, current_user):
        """Get products filtered by user's branch location and delivery zones"""
        try:
            print(f"Filtering products for customer user: {current_user.username}")
            
            # Get user's branch information
            user_branch = None
            user_pincode = None
            
            if hasattr(current_user, 'branch_id') and current_user.branch_id:
                from models import Branch
                user_branch = Branch.get_by_id(current_user.branch_id)
                if user_branch and user_branch.pincode:
                    user_pincode = user_branch.pincode
                    print(f"User branch: {user_branch.name}, Pincode: {user_pincode}")
            
            if not user_pincode:
                print("No pincode found for user branch, returning all products")
                return Product.get_all_active()
            
            # Get locations that can deliver to user's pincode
            serviceable_locations = Location.get_locations_for_pincode(user_pincode)
            
            if not serviceable_locations:
                print(f"No serviceable locations found for pincode {user_pincode}")
                return []
            
            print(f"Found {len(serviceable_locations)} serviceable locations for pincode {user_pincode}")
            
            # Get location IDs
            serviceable_location_ids = [loc.location_id for loc in serviceable_locations]
            
            # Get products from serviceable locations
            deliverable_products = []
            all_products = Product.get_all_active()
            
            for product in all_products:
                # Check if product is available from any serviceable location
                product_locations = getattr(product, 'location_ids', [])
                if not product_locations and hasattr(product, 'location_id') and product.location_id:
                    # Backward compatibility
                    product_locations = [product.location_id]
                
                # Check if any of the product's locations are serviceable
                if any(loc_id in serviceable_location_ids for loc_id in product_locations):
                    deliverable_products.append(product)
            
            print(f"Found {len(deliverable_products)} deliverable products")
            return deliverable_products
            
        except Exception as e:
            print(f"Error filtering products by location: {e}")
            import traceback
            traceback.print_exc()
            return Product.get_all_active()  # Fallback to all products
    
    def get_customer_pricing(self, product_id, customer_id):
        """Get custom pricing for customer"""
        try:
            db = config.get_db()
            doc_id = f"{customer_id}_{product_id}"
            doc = db.collection('customer_pricing').document(doc_id).get()
            
            if doc.exists:
                pricing_data = doc.to_dict()
                return pricing_data.get('custom_price')
            
            return None
            
        except Exception as e:
            print(f"Get customer pricing error: {e}")
            return None
    
    def get_product_categories(self):
        """Get available product categories"""
        try:
            from datetime import datetime
            db = config.get_db()
            doc = db.collection('product_categories').document('default').get()
            
            if doc.exists:
                data = doc.to_dict()
                categories = data.get('categories', [])
                print(f"Retrieved {len(categories)} categories from database")
                return categories
            else:
                # Return and create default categories
                default_categories = [
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
                ]
                
                # Save default categories to database
                try:
                    db.collection('product_categories').document('default').set({
                        'categories': default_categories,
                        'created_at': datetime.now(),
                        'updated_at': datetime.now()
                    })
                    print("Created default categories in database")
                except Exception as e:
                    print(f"Error creating default categories: {e}")
                
                return default_categories
                
        except Exception as e:
            print(f"Get categories error: {e}")
            import traceback
            traceback.print_exc()
            return []
        
    
    def update_product_categories(self, categories):
        """Update product categories"""
        try:
            from datetime import datetime
            
            current_user = self.auth.get_current_user()
            if not current_user or current_user.role not in ['vendor_superadmin', 'vendor_admin']:
                return {'success': False, 'message': 'Only SuperAdmin/Admin can update categories'}
            
            # Validate categories input
            if not isinstance(categories, list):
                return {'success': False, 'message': 'Categories must be a list'}
            
            # Clean and validate each category
            cleaned_categories = []
            for category in categories:
                if isinstance(category, str) and category.strip():
                    cleaned_categories.append(category.strip())
            
            if not cleaned_categories:
                return {'success': False, 'message': 'At least one valid category is required'}
            
            # Remove duplicates while preserving order
            seen = set()
            unique_categories = []
            for category in cleaned_categories:
                if category.lower() not in seen:
                    seen.add(category.lower())
                    unique_categories.append(category)
            
            print(f"Updating categories: {unique_categories}")
            
            db = config.get_db()
            doc_ref = db.collection('product_categories').document('default')
            
            # Update with timestamp
            update_data = {
                'categories': unique_categories,
                'updated_at': datetime.now(),
                'updated_by': current_user.user_id
            }
            
            # Check if document exists
            if doc_ref.get().exists:
                # Update existing document
                doc_ref.update(update_data)
            else:
                # Create new document
                update_data['created_at'] = datetime.now()
                doc_ref.set(update_data)
            
            print("Categories updated successfully in database")
            
            return {
                'success': True,
                'message': 'Categories updated successfully',
                'categories': unique_categories
            }
            
        except Exception as e:
            print(f"Update categories error: {e}")
            import traceback
            traceback.print_exc()
            return {'success': False, 'message': f'Failed to update categories: {str(e)}'}
    
    # Additional methods for product management would go here...
    # (create_product, update_product, delete_product, etc.)
    # These would be similar to the existing implementation but with 
    # location-aware functionality

# Global product controller instance
product_controller = ProductController()