# Product Controller - Handle product management and catalog with differential pricing
from flask import request, session
from models import Product, User
from controllers.auth_controller import auth_controller
from config import config

class ProductController:
    """Handle product management operations with customer-specific pricing"""
    
    def __init__(self):
        self.auth = auth_controller
    
    def get_products(self):
        """Get products list with customer-specific pricing and multi-location support"""
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
            
            # Fetch products with location filter and proper error handling
            try:
                if location_id:
                    products = Product.get_all_active_with_location(location_id)
                else:
                    products = Product.get_all_active()
                
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
                
            except Exception as e:
                print(f"Error fetching products: {e}")
                return {'success': False, 'message': 'Failed to fetch products from database'}
            
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
                        from models import Location
                        
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
        
    @classmethod  
    def get_products_by_location_ids(cls, location_ids):
        """Get products that are available at any of the specified locations"""
        try:
            db = config.get_db()
            products = []
            
            # Get all active products
            docs = db.collection('products').where('is_active', '==', True).get()
            
            for doc in docs:
                product_data = doc.to_dict()
                product = cls.from_dict(product_data)
                
                # Check if product is in any of the specified locations
                product_locations = getattr(product, 'location_ids', [])
                if not product_locations and hasattr(product, 'location_id') and product.location_id:
                    # Backward compatibility
                    product_locations = [product.location_id]
                
                if any(loc_id in location_ids for loc_id in product_locations):
                    products.append(product)
            
            return products
        except Exception as e:
            print(f"Error getting products by location IDs: {e}")
            return []

    def upload_product_image(self, file, product_id):
        """Upload product image - SIMPLIFIED VERSION"""
        try:
            print(f"=== SIMPLIFIED IMAGE UPLOAD ===")
            print(f"Product ID: {product_id}")
            print(f"File: {file.filename}")
            
            if not file or not file.filename:
                print("No file provided")
                return None
            
            # Reset file stream
            file.stream.seek(0)
            
            # Read the file content
            file_content = file.stream.read()
            file_size = len(file_content)
            print(f"File size: {file_size} bytes")
            
            if file_size == 0:
                print("File is empty")
                return None
            
            # Generate simple filename
            import uuid, os
            file_extension = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else 'jpg'
            filename = f"product_{product_id}_{uuid.uuid4().hex[:8]}.{file_extension}"
            
            # Create directory path
            upload_dir = os.path.join('uploads', 'products')
            os.makedirs(upload_dir, exist_ok=True)
            print(f"Upload directory: {upload_dir}")
            
            # Full file path
            full_path = os.path.join(upload_dir, filename)
            print(f"Saving to: {full_path}")
            
            # Save file
            with open(full_path, 'wb') as f:
                f.write(file_content)
            
            # Verify file was saved
            if os.path.exists(full_path):
                saved_size = os.path.getsize(full_path)
                print(f"✅ File saved successfully: {saved_size} bytes")
                
                # Return the URL path
                return f"/uploads/products/{filename}"
            else:
                print("❌ File was not saved")
                return None
                
        except Exception as e:
            print(f"ERROR in simplified upload: {e}")
            import traceback
            traceback.print_exc()
            return None

    def create_product(self):
        """Create new product (Vendor only) - UPDATED WITH MULTI-LOCATION SUPPORT"""
        try:
            current_user = self.auth.get_current_user()
            if not current_user or not current_user.role.startswith('vendor_'):
                return {'success': False, 'message': 'Only vendor users can create products'}
            
            # Handle both form data and JSON
            if request.content_type and request.content_type.startswith('multipart/form-data'):
                data = request.form.to_dict()
                # Handle multiple location selections from form
                location_ids = request.form.getlist('location_ids')
            else:
                data = request.get_json()
                location_ids = data.get('location_ids', [])
            
            # Validate required fields
            required_fields = ['product_name', 'category', 'quantity']
            for field in required_fields:
                if field not in data or not data[field]:
                    return {'success': False, 'message': f'{field.replace("_", " ").title()} is required'}
            
            # Validate at least one location is selected
            if not location_ids or len(location_ids) == 0:
                return {'success': False, 'message': 'At least one location must be selected'}
            
            # Validate all selected locations exist
            from models import Location
            for location_id in location_ids:
                location = Location.get_by_id(location_id)
                if not location:
                    return {'success': False, 'message': f'Invalid location selected: {location_id}'}
            
            # Generate auto item number
            item_no = self.generate_item_number()
            if not item_no:
                return {'success': False, 'message': 'Failed to generate item number'}
            
            # Create new product
            product = Product()
            product.item_no = item_no
            product.category = data['category']
            product.product_name = data['product_name']
            product.product_make = data.get('product_make', '')
            product.product_model = data.get('product_model', '')
            product.description = data.get('description', '')
            product.price = 0.0  # Set default price to 0, pricing will be set per customer
            product.quantity = int(data['quantity'])
            product.gst_rate = float(data.get('gst_rate', 18.0))
            product.hsn_code = data.get('hsn_code', '')
            product.low_stock_threshold = int(data.get('low_stock_threshold', 10))
            
            # Set multiple locations
            product.location_ids = location_ids
            # Set primary location for backward compatibility
            product.location_id = location_ids[0] if location_ids else None
            
            # Handle product specifications
            if 'specifications' in data:
                product.product_specifications = data['specifications']
            
            # Save product first to get product_id
            if product.save():
                # Handle image upload
                if 'product_image' in request.files:
                    file = request.files['product_image']
                    if file and file.filename:
                        image_url = self.upload_product_image(file, product.product_id)
                        if image_url:
                            product.image_urls = [image_url]
                            product.save()  # Update with image URL
                
                return {
                    'success': True,
                    'message': f'Product created successfully with Item Number: {item_no}',
                    'product_id': product.product_id,
                    'item_no': item_no
                }
            else:
                return {'success': False, 'message': 'Failed to create product'}
                
        except Exception as e:
            print(f"Create product error: {e}")
            import traceback
            traceback.print_exc()
            return {'success': False, 'message': 'Failed to create product'}
        
    def generate_item_number(self):
        """Generate auto-incremented item number in format itxxxxx"""
        try:
            from config import config
            from datetime import datetime
            
            db = config.get_db()
            
            # Get the current counter from a dedicated collection
            counter_doc_ref = db.collection('counters').document('item_number')
            counter_doc = counter_doc_ref.get()
            
            if counter_doc.exists:
                # Get current counter value
                current_counter = counter_doc.to_dict().get('value', 0)
                new_counter = current_counter + 1
            else:
                # Initialize counter if it doesn't exist
                new_counter = 1
            
            # Update the counter
            counter_doc_ref.set({
                'value': new_counter,
                'updated_at': datetime.now()
            })
            
            # Generate item number in format itxxxxx
            item_no = f"it{new_counter}"
            
            # Double-check that this item number doesn't already exist
            existing_product = Product.get_by_item_no(item_no)
            if existing_product:
                # If it exists, try the next number
                print(f"Item number {item_no} already exists, trying next number")
                return self.generate_item_number()
            
            print(f"Generated item number: {item_no}")
            return item_no
            
        except Exception as e:
            print(f"Error generating item number: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def get_product(self, product_id):
        """Get single product details"""
        try:
            current_user = self.auth.get_current_user()
            if not current_user:
                return {'success': False, 'message': 'Authentication required'}
            
            product = Product.get_by_id(product_id)
            if not product:
                return {'success': False, 'message': 'Product not found'}
            
            product_dict = product.to_dict()
            
            # Add computed fields
            product_dict['is_low_stock'] = product.is_low_stock()
            product_dict['gst_amount'] = (product.price * product.gst_rate) / 100
            product_dict['price_including_gst'] = product.price + product_dict['gst_amount']
            
            # For customer users, check custom pricing
            if current_user.role.startswith('customer_'):
                custom_price = self.get_customer_pricing(product.product_id, current_user.customer_id)
                if custom_price is not None:
                    product_dict['custom_price'] = custom_price
                    product_dict['gst_amount'] = (custom_price * product.gst_rate) / 100
                    product_dict['price_including_gst'] = custom_price + product_dict['gst_amount']
            
            return {
                'success': True,
                'product': product_dict
            }
            
        except Exception as e:
            print(f"Get product error: {e}")
            return {'success': False, 'message': 'Failed to retrieve product'}
    
    def update_product(self, product_id):
        """Update existing product (Vendor only) - FIXED WITH MULTI-LOCATION SUPPORT"""
        try:
            current_user = self.auth.get_current_user()
            if not current_user or not current_user.role.startswith('vendor_'):
                return {'success': False, 'message': 'Only vendor users can update products'}
            
            product = Product.get_by_id(product_id)
            if not product:
                return {'success': False, 'message': 'Product not found'}
            
            # Handle both form data (with image) and JSON
            if request.content_type and request.content_type.startswith('multipart/form-data'):
                print("Processing multipart form data (with potential image upload)")
                data = request.form.to_dict()
                # Handle multiple location selections from form
                location_ids = request.form.getlist('location_ids')
                has_image = 'product_image' in request.files and request.files['product_image'].filename
            else:
                print("Processing JSON data (no image)")
                data = request.get_json()
                location_ids = data.get('location_ids', [])
                has_image = False
            
            print(f"Update data received: {data}")
            print(f"Location IDs received: {location_ids}")
            
            # Validate at least one location is selected
            if not location_ids or len(location_ids) == 0:
                return {'success': False, 'message': 'At least one location must be selected'}
            
            # Validate all selected locations exist
            from models import Location
            for location_id in location_ids:
                location = Location.get_by_id(location_id)
                if not location:
                    return {'success': False, 'message': f'Invalid location selected: {location_id}'}
            
            # Update allowed fields
            updateable_fields = [
                'category', 'product_name', 'product_make', 'product_model',
                'description', 'price', 'quantity', 'gst_rate', 'hsn_code',
                'low_stock_threshold', 'is_active'
            ]
            
            for field in updateable_fields:
                if field in data and data[field] is not None:
                    if field in ['price', 'gst_rate']:
                        setattr(product, field, float(data[field]) if data[field] else 0.0)
                    elif field in ['quantity', 'low_stock_threshold']:
                        setattr(product, field, int(data[field]) if data[field] else 0)
                    elif field == 'is_active':
                        setattr(product, field, bool(data[field]))
                    else:
                        setattr(product, field, data[field])
            
            # Update multiple locations - THIS IS THE KEY FIX
            product.location_ids = location_ids
            # Set primary location for backward compatibility
            product.location_id = location_ids[0] if location_ids else None
            
            print(f"Setting product locations to: {location_ids}")
            print(f"Setting primary location to: {product.location_id}")
            
            # Handle specifications
            if 'specifications' in data:
                product.product_specifications = data['specifications']
            
            # Handle image upload for multipart requests
            if has_image:
                print("Processing image upload...")
                file = request.files['product_image']
                if file and file.filename:
                    image_url = self.upload_product_image(file, product.product_id)
                    if image_url:
                        product.image_urls = [image_url]
                        print(f"Image uploaded successfully: {image_url}")
                    else:
                        return {'success': False, 'message': 'Failed to upload product image'}
            
            # Save the updated product
            print("Saving updated product...")
            if product.save():
                print("Product updated successfully in database")
                return {
                    'success': True,
                    'message': 'Product updated successfully'
                }
            else:
                print("Failed to save product to database")
                return {'success': False, 'message': 'Failed to update product'}
                
        except Exception as e:
            print(f"Update product error: {e}")
            import traceback
            traceback.print_exc()
            return {'success': False, 'message': 'Failed to update product'}
    
    def delete_product(self, product_id):
        """Soft delete product (Vendor SuperAdmin only)"""
        try:
            current_user = self.auth.get_current_user()
            if not current_user or current_user.role != 'vendor_superadmin':
                return {'success': False, 'message': 'Only SuperAdmin can delete products'}
            
            product = Product.get_by_id(product_id)
            if not product:
                return {'success': False, 'message': 'Product not found'}
            
            # Soft delete by setting is_active to False
            product.is_active = False
            
            if product.save():
                return {
                    'success': True,
                    'message': 'Product deleted successfully'
                }
            else:
                return {'success': False, 'message': 'Failed to delete product'}
                
        except Exception as e:
            print(f"Delete product error: {e}")
            return {'success': False, 'message': 'Failed to delete product'}
    
    def get_product_categories(self):
        """Get available product categories - FIXED FOR FIRESTORE"""
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
            # Return default categories as fallback
            return [
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
    
    def update_product_categories(self, categories):
        """Update product categories - FIXED FOR FIRESTORE"""
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
            
            # Update with timestamp - FIXED to use datetime.now()
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
        
    # Helper method to check Firestore connection
    def test_firestore_connection(self):
        """Test Firestore connection and permissions"""
        try:
            from datetime import datetime
            db = config.get_db()
            
            # Test read
            test_doc = db.collection('product_categories').document('default').get()
            can_read = True
            
            # Test write
            try:
                db.collection('test_connection').document('test').set({
                    'test': True,
                    'timestamp': datetime.now()
                })
                can_write = True
                
                # Clean up test document
                db.collection('test_connection').document('test').delete()
            except Exception as write_error:
                can_write = False
                print(f"Write test failed: {write_error}")
            
            return {
                'success': True,
                'can_read': can_read,
                'can_write': can_write,
                'doc_exists': test_doc.exists if can_read else False,
                'message': 'Connection test completed'
            }
            
        except Exception as e:
            print(f"Firestore connection test error: {e}")
            return {
                'success': False,
                'error': str(e),
                'message': 'Connection test failed'
            }
    
    def get_customer_pricing(self, product_id, customer_id):
        """Get custom pricing for customer - FIXED VERSION"""
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
    
    def set_customer_pricing(self, product_id, customer_id, custom_price):
        """Set custom pricing for customer (Vendor SuperAdmin/Admin only)"""
        try:
            current_user = self.auth.get_current_user()
            if not current_user or current_user.role not in ['vendor_superadmin', 'vendor_admin']:
                return {'success': False, 'message': 'Insufficient permissions'}
            
            # Check if product and customer exist
            product = Product.get_by_id(product_id)
            if not product:
                return {'success': False, 'message': 'Product not found'}
            
            from models import Customer
            customer = Customer.get_by_id(customer_id)
            if not customer:
                return {'success': False, 'message': 'Customer not found'}
            
            # Save custom pricing
            db = config.get_db()
            pricing_doc = {
                'customer_id': customer_id,
                'product_id': product_id,
                'custom_price': float(custom_price),
                'created_by': current_user.user_id,
                'created_at': db.SERVER_TIMESTAMP,
                'updated_at': db.SERVER_TIMESTAMP
            }
            
            # Use combination of customer_id and product_id as document ID
            doc_id = f"{customer_id}_{product_id}"
            db.collection('customer_pricing').document(doc_id).set(pricing_doc)
            
            return {
                'success': True,
                'message': 'Custom pricing set successfully'
            }
            
        except Exception as e:
            print(f"Set customer pricing error: {e}")
            return {'success': False, 'message': 'Failed to set custom pricing'}
    
    def remove_customer_pricing(self, product_id, customer_id):
        """Remove custom pricing for customer (revert to base price)"""
        try:
            current_user = self.auth.get_current_user()
            if not current_user or current_user.role not in ['vendor_superadmin', 'vendor_admin']:
                return {'success': False, 'message': 'Insufficient permissions'}
            
            # Delete the custom pricing document
            db = config.get_db()
            doc_id = f"{customer_id}_{product_id}"
            db.collection('customer_pricing').document(doc_id).delete()
            
            return {
                'success': True,
                'message': 'Custom pricing removed successfully'
            }
            
        except Exception as e:
            print(f"Remove customer pricing error: {e}")
            return {'success': False, 'message': 'Failed to remove custom pricing'}
    
    def get_customer_pricing_list(self, customer_id):
        """Get all custom pricing for a specific customer"""
        try:
            current_user = self.auth.get_current_user()
            if not current_user or current_user.role not in ['vendor_superadmin', 'vendor_admin']:
                return {'success': False, 'message': 'Insufficient permissions'}
            
            db = config.get_db()
            docs = db.collection('customer_pricing').where('customer_id', '==', customer_id).get()
            
            pricing_list = []
            for doc in docs:
                pricing_data = doc.to_dict()
                
                # Get product details
                product = Product.get_by_id(pricing_data['product_id'])
                if product:
                    pricing_item = {
                        'product_id': pricing_data['product_id'],
                        'product_name': product.product_name,
                        'product_make': product.product_make,
                        'base_price': product.price,
                        'custom_price': pricing_data['custom_price'],
                        'savings': product.price - pricing_data['custom_price'],
                        'created_at': pricing_data.get('created_at'),
                        'updated_at': pricing_data.get('updated_at')
                    }
                    pricing_list.append(pricing_item)
            
            return {
                'success': True,
                'pricing': pricing_list
            }
            
        except Exception as e:
            print(f"Get customer pricing list error: {e}")
            return {'success': False, 'message': 'Failed to retrieve customer pricing'}
    
    def get_low_stock_products(self):
        """Get products with low stock (Vendor only)"""
        try:
            current_user = self.auth.get_current_user()
            if not current_user or not current_user.role.startswith('vendor_'):
                return {'success': False, 'message': 'Only vendor users can view low stock products'}
            
            low_stock_products = Product.get_low_stock_products()
            
            product_list = []
            for product in low_stock_products:
                product_dict = product.to_dict()
                product_dict['is_low_stock'] = True
                product_list.append(product_dict)
            
            return {
                'success': True,
                'products': product_list,
                'count': len(product_list)
            }
            
        except Exception as e:
            print(f"Get low stock products error: {e}")
            return {'success': False, 'message': 'Failed to retrieve low stock products'}
    
    def bulk_update_stock(self, updates):
        """Bulk update product stock levels (Vendor only)"""
        try:
            current_user = self.auth.get_current_user()
            if not current_user or not current_user.role.startswith('vendor_'):
                return {'success': False, 'message': 'Only vendor users can update stock'}
            
            updated_count = 0
            errors = []
            
            for update in updates:
                try:
                    product_id = update.get('product_id')
                    new_quantity = int(update.get('quantity', 0))
                    
                    product = Product.get_by_id(product_id)
                    if product:
                        product.quantity = new_quantity
                        if product.save():
                            updated_count += 1
                        else:
                            errors.append(f"Failed to update {product.product_name}")
                    else:
                        errors.append(f"Product not found: {product_id}")
                        
                except Exception as e:
                    errors.append(f"Error updating product {update.get('product_id', 'unknown')}: {str(e)}")
            
            return {
                'success': True,
                'message': f'Updated {updated_count} products',
                'updated_count': updated_count,
                'errors': errors
            }
            
        except Exception as e:
            print(f"Bulk update stock error: {e}")
            return {'success': False, 'message': 'Failed to update stock levels'}

# Global product controller instance
product_controller = ProductController()