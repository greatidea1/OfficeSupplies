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
        """Get products list with customer-specific pricing"""
        try:
            current_user = self.auth.get_current_user()
            if not current_user:
                return {'success': False, 'message': 'Authentication required'}
            
            # Get query parameters
            search = request.args.get('search', '')
            category = request.args.get('category', '')
            sort_by = request.args.get('sort', 'name_asc')
            page = int(request.args.get('page', 1))
            per_page = int(request.args.get('per_page', 20))
            
            # Get all active products
            if search or category:
                products = Product.search_products(search, category)
            else:
                products = Product.get_all_active()
            
            # Apply sorting
            if sort_by == 'name_asc':
                products.sort(key=lambda p: p.product_name.lower())
            elif sort_by == 'name_desc':
                products.sort(key=lambda p: p.product_name.lower(), reverse=True)
            elif sort_by == 'price_asc':
                products.sort(key=lambda p: p.price)
            elif sort_by == 'price_desc':
                products.sort(key=lambda p: p.price, reverse=True)
            elif sort_by == 'stock_asc':
                products.sort(key=lambda p: p.quantity)
            elif sort_by == 'stock_desc':
                products.sort(key=lambda p: p.quantity, reverse=True)
            
            # Apply pagination
            total_products = len(products)
            start_idx = (page - 1) * per_page
            end_idx = start_idx + per_page
            paginated_products = products[start_idx:end_idx]
            
            # Convert to dict and add additional info
            product_list = []
            for product in paginated_products:
                product_dict = product.to_dict()
                
                # Add computed fields
                product_dict['is_low_stock'] = product.is_low_stock()
                product_dict['gst_amount'] = (product.price * product.gst_rate) / 100
                product_dict['price_including_gst'] = product.price + product_dict['gst_amount']
                
                # For customer users, get their custom pricing
                if current_user.role.startswith('customer_') and current_user.customer_id:
                    custom_price = self.get_customer_pricing(product.product_id, current_user.customer_id)
                    if custom_price is not None:
                        product_dict['custom_price'] = custom_price
                        product_dict['gst_amount'] = (custom_price * product.gst_rate) / 100
                        product_dict['price_including_gst'] = custom_price + product_dict['gst_amount']
                
                product_list.append(product_dict)
            
            # Get categories for filtering
            categories = self.get_product_categories()
            
            return {
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
                    'sort_by': sort_by
                }
            }
            
        except Exception as e:
            print(f"Get products error: {e}")
            return {'success': False, 'message': 'Failed to retrieve products'}

    def upload_product_image(self, file, product_id):
        """Upload and resize product image"""
        try:
            # Validate file
            if not file or not file.filename:
                return None
            
            # Check file type
            allowed_extensions = {'jpg', 'jpeg', 'png', 'gif'}
            file_extension = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
            
            if file_extension not in allowed_extensions:
                return None
            
            # Generate unique filename
            import uuid
            filename = f"product_{product_id}_{uuid.uuid4().hex[:8]}.{file_extension}"
            
            # Resize image to 800x800
            from PIL import Image
            import io
            
            # Open and process image
            image = Image.open(file.stream)
            
            # Convert to RGB if needed (for PNG with transparency)
            if image.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', image.size, (255, 255, 255))
                if image.mode == 'P':
                    image = image.convert('RGBA')
                background.paste(image, mask=image.split()[-1] if image.mode == 'RGBA' else None)
                image = background
            
            # Resize to 800x800 maintaining aspect ratio
            image.thumbnail((800, 800), Image.Resampling.LANCZOS)
            
            # Create a new 800x800 image with white background
            new_image = Image.new('RGB', (800, 800), (255, 255, 255))
            
            # Calculate position to center the image
            x = (800 - image.width) // 2
            y = (800 - image.height) // 2
            new_image.paste(image, (x, y))
            
            # Save to bytes
            img_bytes = io.BytesIO()
            new_image.save(img_bytes, format='JPEG', quality=85, optimize=True)
            img_bytes.seek(0)
            
            # Get storage handler
            storage_handler = config.get_storage()
            
            if config.use_local_storage:
                # Local storage
                import os
                file_path = f"products/{filename}"
                full_path = os.path.join('uploads', file_path)
                
                # Ensure directory exists
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                
                # Save file
                with open(full_path, 'wb') as f:
                    f.write(img_bytes.getvalue())
                
                return f"/uploads/{file_path}"
            else:
                # Firebase Storage
                blob = storage_handler.blob(f"products/{filename}")
                blob.upload_from_file(img_bytes, content_type='image/jpeg')
                blob.make_public()
                
                return blob.public_url
            
        except Exception as e:
            print(f"Upload product image error: {e}")
            return None

    def create_product(self):
        """Create new product (Vendor only) - FIXED VERSION WITHOUT PRICE REQUIREMENT"""
        try:
            current_user = self.auth.get_current_user()
            if not current_user or not current_user.role.startswith('vendor_'):
                return {'success': False, 'message': 'Only vendor users can create products'}
            
            # Handle both form data and JSON
            if request.content_type and request.content_type.startswith('multipart/form-data'):
                data = request.form.to_dict()
            else:
                data = request.get_json()
            
            # Validate required fields (price removed from requirements)
            required_fields = ['item_no', 'product_name', 'category', 'quantity']
            for field in required_fields:
                if field not in data or not data[field]:
                    return {'success': False, 'message': f'{field.replace("_", " ").title()} is required'}
            
            # Check if item number already exists
            existing_product = Product.get_by_item_no(data['item_no'])
            if existing_product:
                return {'success': False, 'message': 'Item number already exists'}
            
            # Create new product
            product = Product()
            product.item_no = data['item_no']
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
                    'message': 'Product created successfully',
                    'product_id': product.product_id
                }
            else:
                return {'success': False, 'message': 'Failed to create product'}
                
        except Exception as e:
            print(f"Create product error: {e}")
            import traceback
            traceback.print_exc()
            return {'success': False, 'message': 'Failed to create product'}
    
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
        """Update existing product (Vendor only)"""
        try:
            current_user = self.auth.get_current_user()
            if not current_user or not current_user.role.startswith('vendor_'):
                return {'success': False, 'message': 'Only vendor users can update products'}
            
            product = Product.get_by_id(product_id)
            if not product:
                return {'success': False, 'message': 'Product not found'}
            
            data = request.get_json() if request.is_json else request.form.to_dict()
            
            # Update allowed fields
            updateable_fields = [
                'category', 'product_name', 'product_make', 'product_model',
                'description', 'price', 'quantity', 'gst_rate', 'hsn_code',
                'low_stock_threshold', 'is_active'
            ]
            
            for field in updateable_fields:
                if field in data:
                    if field in ['price', 'gst_rate']:
                        setattr(product, field, float(data[field]))
                    elif field in ['quantity', 'low_stock_threshold']:
                        setattr(product, field, int(data[field]))
                    elif field == 'is_active':
                        setattr(product, field, bool(data[field]))
                    else:
                        setattr(product, field, data[field])
            
            # Handle specifications
            if 'specifications' in data:
                product.product_specifications = data['specifications']
            
            if product.save():
                return {
                    'success': True,
                    'message': 'Product updated successfully'
                }
            else:
                return {'success': False, 'message': 'Failed to update product'}
                
        except Exception as e:
            print(f"Update product error: {e}")
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
        """Get available product categories"""
        try:
            db = config.get_db()
            doc = db.collection('product_categories').document('default').get()
            
            if doc.exists:
                return doc.to_dict().get('categories', [])
            else:
                # Return default categories
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
                
        except Exception as e:
            print(f"Get categories error: {e}")
            return []
    
    def update_product_categories(self, categories):
        """Update product categories (Vendor SuperAdmin only)"""
        try:
            current_user = self.auth.get_current_user()
            if not current_user or current_user.role != 'vendor_superadmin':
                return {'success': False, 'message': 'Only SuperAdmin can update categories'}
            
            db = config.get_db()
            doc_ref = db.collection('product_categories').document('default')
            doc_ref.set({
                'categories': categories,
                'updated_at': db.SERVER_TIMESTAMP
            })
            
            return {
                'success': True,
                'message': 'Categories updated successfully'
            }
            
        except Exception as e:
            print(f"Update categories error: {e}")
            return {'success': False, 'message': 'Failed to update categories'}
    
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