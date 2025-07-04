# Order Controller - Handle order management and workflow with customer pricing
from flask import request, session
from datetime import datetime
from models import Order, Product, User, Customer
from controllers.auth_controller import auth_controller
from config import config

class OrderController:
    """Handle order management operations and approval workflow with customer pricing"""
    
    def __init__(self):
        self.auth = auth_controller
    
    def get_orders(self):
        """Get orders list based on user role and filters"""
        try:
            current_user = self.auth.get_current_user()
            if not current_user:
                return {'success': False, 'message': 'Authentication required'}
            
            # Get query parameters
            status = request.args.get('status', '')
            customer_id = request.args.get('customer_id', '')
            date_range = request.args.get('date_range', '')
            page = int(request.args.get('page', 1))
            per_page = int(request.args.get('per_page', 20))
            
            # Get orders based on user role
            if current_user.role in ['vendor_superadmin', 'vendor_admin', 'vendor_normal']:
                orders = self.get_vendor_orders(status, customer_id)
            elif current_user.role == 'customer_hr_admin':
                orders = self.get_customer_hr_orders(current_user.customer_id, status)
            elif current_user.role == 'customer_dept_head':
                orders = self.get_dept_head_orders(current_user)
            elif current_user.role == 'customer_employee':
                orders = self.get_employee_orders(current_user.user_id, status)
            else:
                return {'success': False, 'message': 'Invalid user role'}
            
            # Apply date filtering if specified
            if date_range:
                orders = self.filter_orders_by_date(orders, date_range)
            
            # Sort orders by creation date (newest first)
            orders.sort(key=lambda o: o.created_at, reverse=True)
            
            # Apply pagination
            total_orders = len(orders)
            start_idx = (page - 1) * per_page
            end_idx = start_idx + per_page
            paginated_orders = orders[start_idx:end_idx]
            
            # Convert to dict and add additional info
            order_list = []
            for order in paginated_orders:
                order_dict = order.to_dict()
                
                # Add computed fields
                order_dict['items_count'] = len(order.items)
                order_dict['can_approve'] = self.can_user_approve_order(current_user, order)
                order_dict['can_edit'] = self.can_user_edit_order(current_user, order)
                order_dict['customer_name'] = self.get_customer_name(order.customer_id)
                
                # Add product details for items with pricing information
                order_dict['items_with_details'] = []
                for item in order.items:
                    product = Product.get_by_id(item['product_id'])
                    if product:
                        item_detail = item.copy()
                        item_detail['product_name'] = product.product_name
                        item_detail['product_make'] = product.product_make
                        item_detail['category'] = product.category
                        
                        # Add pricing information
                        item_detail['base_price'] = product.price
                        item_detail['used_price'] = item['price']
                        item_detail['is_custom_price'] = item['price'] != product.price
                        item_detail['savings_per_unit'] = product.price - item['price'] if item['price'] != product.price else 0
                        item_detail['total_savings'] = item_detail['savings_per_unit'] * item['quantity']
                        
                        order_dict['items_with_details'].append(item_detail)
                
                # Calculate total savings for the order
                total_savings = sum(item.get('total_savings', 0) for item in order_dict['items_with_details'])
                order_dict['total_savings'] = total_savings
                
                order_list.append(order_dict)
            
            return {
                'success': True,
                'orders': order_list,
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total': total_orders,
                    'pages': (total_orders + per_page - 1) // per_page
                },
                'filters': {
                    'status': status,
                    'customer_id': customer_id,
                    'date_range': date_range
                }
            }
            
        except Exception as e:
            print(f"Get orders error: {e}")
            return {'success': False, 'message': 'Failed to retrieve orders'}
    
    def get_order(self, order_id):
        """Get single order details - UPDATED WITH PRICING INFO"""
        try:
            current_user = self.auth.get_current_user()
            if not current_user:
                return {'success': False, 'message': 'Authentication required'}
            
            order = Order.get_by_id(order_id)
            if not order:
                return {'success': False, 'message': 'Order not found'}
            
            # Check if user can view this order
            if not self.can_user_view_order(current_user, order):
                return {'success': False, 'message': 'Access denied'}
            
            order_dict = order.to_dict()
            
            # Add computed fields
            order_dict['items_count'] = len(order.items)
            order_dict['can_approve'] = self.can_user_approve_order(current_user, order)
            order_dict['can_edit'] = self.can_user_edit_order(current_user, order)
            order_dict['customer_name'] = self.get_customer_name(order.customer_id)
            
            # Add detailed product information with pricing details
            order_dict['items_with_details'] = []
            for item in order.items:
                product = Product.get_by_id(item['product_id'])
                if product:
                    item_detail = item.copy()
                    item_detail['product_name'] = product.product_name
                    item_detail['product_make'] = product.product_make
                    item_detail['product_model'] = product.product_model
                    item_detail['category'] = product.category
                    item_detail['hsn_code'] = product.hsn_code
                    item_detail['gst_rate'] = product.gst_rate
                    
                    # Add pricing information
                    item_detail['base_price'] = product.price
                    item_detail['used_price'] = item['price']
                    item_detail['is_custom_price'] = item['price'] != product.price
                    item_detail['savings_per_unit'] = product.price - item['price'] if item['price'] != product.price else 0
                    item_detail['total_savings'] = item_detail['savings_per_unit'] * item['quantity']
                    
                    order_dict['items_with_details'].append(item_detail)
            
            # Calculate total savings for the order
            total_savings = sum(item.get('total_savings', 0) for item in order_dict['items_with_details'])
            order_dict['total_savings'] = total_savings
            
            # Add user information for comments
            for comment in order_dict.get('comments', []):
                user = User.get_by_id(comment['user_id'])
                if user:
                    comment['user_name'] = user.full_name or user.username
                    comment['user_role'] = user.role
            
            return {
                'success': True,
                'order': order_dict
            }
            
        except Exception as e:
            print(f"Get order error: {e}")
            return {'success': False, 'message': 'Failed to retrieve order'}
        
    def get_order_pricing_summary(self, order):
        """Get pricing summary for an order showing base vs custom pricing"""
        try:
            summary = {
                'total_base_price': 0,
                'total_custom_price': 0,
                'total_savings': 0,
                'items_with_custom_pricing': 0,
                'total_items': len(order.items)
            }
            
            for item in order.items:
                product = Product.get_by_id(item['product_id'])
                if product:
                    base_total = product.price * item['quantity']
                    custom_total = item['price'] * item['quantity']
                    
                    summary['total_base_price'] += base_total
                    summary['total_custom_price'] += custom_total
                    
                    if item['price'] != product.price:
                        summary['items_with_custom_pricing'] += 1
            
            summary['total_savings'] = summary['total_base_price'] - summary['total_custom_price']
            summary['savings_percentage'] = (summary['total_savings'] / summary['total_base_price'] * 100) if summary['total_base_price'] > 0 else 0
            
            return summary
            
        except Exception as e:
            print(f"Error calculating pricing summary: {e}")
            return {
                'total_base_price': 0,
                'total_custom_price': 0,
                'total_savings': 0,
                'items_with_custom_pricing': 0,
                'total_items': 0,
                'savings_percentage': 0
            }
    
    def create_order(self):
        """Create new order (Customer employees only) - UPDATED FOR CUSTOMER PRICING"""
        try:
            current_user = self.auth.get_current_user()
            if not current_user or current_user.role != 'customer_employee':
                return {'success': False, 'message': 'Only customer employees can create orders'}
            
            data = request.get_json()
            items = data.get('items', [])
            
            if not items:
                return {'success': False, 'message': 'Order must contain at least one item'}
            
            # Validate items and check stock with customer pricing
            validated_items = []
            for item in items:
                product_id = item.get('product_id')
                quantity = int(item.get('quantity', 0))
                
                if quantity <= 0:
                    return {'success': False, 'message': 'Invalid quantity'}
                
                product = Product.get_by_id(product_id)
                if not product or not product.is_active:
                    return {'success': False, 'message': f'Product not found: {product_id}'}
                
                if product.quantity < quantity:
                    return {'success': False, 'message': f'Insufficient stock for {product.product_name}'}
                
                # Get customer-specific price or base price
                from controllers.product_controller import product_controller
                custom_price = product_controller.get_customer_pricing(product_id, current_user.customer_id)
                price = custom_price if custom_price is not None else product.price
                
                validated_items.append({
                    'product_id': product_id,
                    'quantity': quantity,
                    'price': price,
                    'is_custom_price': custom_price is not None
                })
            
            # Create order
            order = Order()
            order.customer_id = current_user.customer_id
            order.user_id = current_user.user_id
            order.department_id = current_user.department_id
            order.status = 'pending_dept_approval'  # Skip draft, go directly to approval
            
            # Add items with customer-specific pricing
            for item in validated_items:
                order.add_item(item['product_id'], item['quantity'], item['price'])
            
            # Add metadata about pricing
            order.pricing_metadata = {
                'customer_id': current_user.customer_id,
                'has_custom_pricing': any(item['is_custom_price'] for item in validated_items),
                'created_with_custom_rates': True
            }
            
            # Add initial comment
            pricing_note = " (with custom pricing)" if order.pricing_metadata['has_custom_pricing'] else ""
            order.add_comment(
                current_user.user_id,
                current_user.role,
                'created',
                f'Order created and submitted for department approval{pricing_note}'
            )
            
            if order.save():
                # Reduce product quantities
                for item in validated_items:
                    product = Product.get_by_id(item['product_id'])
                    product.reduce_quantity(item['quantity'])
                
                # Send notification to department head
                self.send_order_notification(order, 'approval_required')
                
                return {
                    'success': True,
                    'message': 'Order created successfully',
                    'order_id': order.order_id,
                    'pricing_info': {
                        'has_custom_pricing': order.pricing_metadata['has_custom_pricing'],
                        'total_amount': order.total_amount
                    }
                }
            else:
                return {'success': False, 'message': 'Failed to create order'}
                
        except Exception as e:
            print(f"Create order error: {e}")
            return {'success': False, 'message': 'Failed to create order'}
    
    def process_dept_approval(self, order_id):
        """Process department head approval"""
        try:
            current_user = self.auth.get_current_user()
            if not current_user or current_user.role != 'customer_dept_head':
                return {'success': False, 'message': 'Only department heads can approve orders'}
            
            order = Order.get_by_id(order_id)
            if not order:
                return {'success': False, 'message': 'Order not found'}
            
            if not order.can_be_approved_by_dept_head(current_user):
                return {'success': False, 'message': 'Cannot approve this order'}
            
            data = request.get_json()
            action = data.get('action')  # 'approve' or 'reject'
            comments = data.get('comments', '')
            
            if action == 'approve':
                order.update_status('pending_hr_approval', current_user.user_id, f"Approved by department head. {comments}")
                
                # Send notification to HR admin
                self.send_order_notification(order, 'approval_required')
                
                return {
                    'success': True,
                    'message': 'Order approved and sent to HR for final approval'
                }
                
            elif action == 'reject':
                order.update_status('rejected', current_user.user_id, f"Rejected by department head. {comments}")
                
                # Restore product quantities
                self.restore_product_quantities(order)
                
                # Send notification to employee
                self.send_order_notification(order, 'order_rejected')
                
                return {
                    'success': True,
                    'message': 'Order rejected'
                }
            else:
                return {'success': False, 'message': 'Invalid action'}
                
        except Exception as e:
            print(f"Department approval error: {e}")
            return {'success': False, 'message': 'Failed to process approval'}
    
    def process_hr_approval(self, order_id):
        """Process HR admin approval"""
        try:
            current_user = self.auth.get_current_user()
            if not current_user or current_user.role != 'customer_hr_admin':
                return {'success': False, 'message': 'Only HR admins can approve orders'}
            
            order = Order.get_by_id(order_id)
            if not order:
                return {'success': False, 'message': 'Order not found'}
            
            if not order.can_be_approved_by_hr(current_user):
                return {'success': False, 'message': 'Cannot approve this order'}
            
            data = request.get_json()
            action = data.get('action')  # 'approve' or 'reject'
            comments = data.get('comments', '')
            
            if action == 'approve':
                order.update_status('approved', current_user.user_id, f"Final approval by HR admin. {comments}")
                
                # Send notification to vendor
                self.send_order_notification(order, 'order_approved')
                
                return {
                    'success': True,
                    'message': 'Order approved and sent to vendor for processing'
                }
                
            elif action == 'reject':
                order.update_status('rejected', current_user.user_id, f"Rejected by HR admin. {comments}")
                
                # Restore product quantities
                self.restore_product_quantities(order)
                
                # Send notification to employee
                self.send_order_notification(order, 'order_rejected')
                
                return {
                    'success': True,
                    'message': 'Order rejected'
                }
            else:
                return {'success': False, 'message': 'Invalid action'}
                
        except Exception as e:
            print(f"HR approval error: {e}")
            return {'success': False, 'message': 'Failed to process approval'}
    
    def pack_order(self, order_id):
        """Mark order items as packed (Vendor users)"""
        try:
            current_user = self.auth.get_current_user()
            if not current_user or not current_user.role.startswith('vendor_'):
                return {'success': False, 'message': 'Only vendor users can pack orders'}
            
            order = Order.get_by_id(order_id)
            if not order:
                return {'success': False, 'message': 'Order not found'}
            
            if order.status != 'approved':
                return {'success': False, 'message': 'Order is not ready for packing'}
            
            data = request.get_json()
            packed_items = data.get('packed_items', {})
            
            # Update packed items
            order.packed_items = packed_items
            
            # Check if all items are packed
            all_packed = True
            for i, item in enumerate(order.items):
                if str(i) not in packed_items or not packed_items[str(i)]:
                    all_packed = False
                    break
            
            if all_packed:
                order.update_status('packed', current_user.user_id, 'All items packed and ready for dispatch approval')
            else:
                order.add_comment(current_user.user_id, current_user.role, 'packed_partial', 'Some items packed')
            
            if order.save():
                return {
                    'success': True,
                    'message': 'Packing status updated' if not all_packed else 'Order fully packed'
                }
            else:
                return {'success': False, 'message': 'Failed to update packing status'}
                
        except Exception as e:
            print(f"Pack order error: {e}")
            return {'success': False, 'message': 'Failed to pack order'}
    
    def approve_dispatch(self, order_id):
        """Approve order for dispatch (Vendor admin/superadmin only)"""
        try:
            current_user = self.auth.get_current_user()
            if not current_user or current_user.role not in ['vendor_superadmin', 'vendor_admin']:
                return {'success': False, 'message': 'Only vendor admins can approve dispatch'}
            
            order = Order.get_by_id(order_id)
            if not order:
                return {'success': False, 'message': 'Order not found'}
            
            if order.status != 'packed':
                return {'success': False, 'message': 'Order is not ready for dispatch approval'}
            
            data = request.get_json()
            action = data.get('action', 'approve')
            comments = data.get('comments', '')
            
            if action == 'approve':
                order.dispatch_approved_by = current_user.user_id
                order.update_status('ready_for_dispatch', current_user.user_id, f"Dispatch approved. {comments}")
                
                return {
                    'success': True,
                    'message': 'Dispatch approved, order ready for shipping'
                }
            else:
                order.update_status('approved', current_user.user_id, f"Dispatch approval rejected. {comments}")
                
                return {
                    'success': True,
                    'message': 'Dispatch approval rejected, order sent back for re-packing'
                }
                
        except Exception as e:
            print(f"Approve dispatch error: {e}")
            return {'success': False, 'message': 'Failed to approve dispatch'}
    
    def dispatch_order(self, order_id):
        """Mark order as dispatched (Vendor users)"""
        try:
            current_user = self.auth.get_current_user()
            if not current_user or not current_user.role.startswith('vendor_'):
                return {'success': False, 'message': 'Only vendor users can dispatch orders'}
            
            order = Order.get_by_id(order_id)
            if not order:
                return {'success': False, 'message': 'Order not found'}
            
            if order.status != 'ready_for_dispatch':
                return {'success': False, 'message': 'Order is not ready for dispatch'}
            
            order.dispatched_by = current_user.user_id
            order.dispatch_date = datetime.now()
            order.update_status('dispatched', current_user.user_id, 'Order dispatched successfully')
            
            # Send notification to customer
            self.send_order_notification(order, 'order_dispatched')
            
            return {
                'success': True,
                'message': 'Order marked as dispatched'
            }
                
        except Exception as e:
            print(f"Dispatch order error: {e}")
            return {'success': False, 'message': 'Failed to dispatch order'}
    
    # Helper methods
    
    def get_vendor_orders(self, status=None, customer_id=None):
        """Get orders for vendor users"""
        if status:
            orders = Order.get_by_status(status)
        else:
            # Get all orders for vendor
            from config import config
            db = config.get_db()
            docs = db.collection('orders').get()
            orders = [Order.from_dict(doc.to_dict()) for doc in docs]
        
        if customer_id:
            orders = [o for o in orders if o.customer_id == customer_id]
        
        return orders
    
    def get_customer_hr_orders(self, customer_id, status=None):
        """Get orders for customer HR admin"""
        orders = Order.get_by_customer_id(customer_id)
        
        if status:
            orders = [o for o in orders if o.status == status]
        
        return orders
    
    def get_dept_head_orders(self, user):
        """Get orders for department head"""
        # Get orders for user's department
        orders = Order.get_by_customer_id(user.customer_id)
        
        # Filter by department if user has department_id
        if user.department_id:
            orders = [o for o in orders if o.department_id == user.department_id]
        
        return orders
    
    def get_employee_orders(self, user_id, status=None):
        """Get orders for employee"""
        orders = Order.get_by_user_id(user_id)
        
        if status:
            orders = [o for o in orders if o.status == status]
        
        return orders
    
    def filter_orders_by_date(self, orders, date_range):
        """Filter orders by date range"""
        from datetime import datetime, timedelta
        
        now = datetime.now()
        
        if date_range == 'today':
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif date_range == 'week':
            start_date = now - timedelta(days=7)
        elif date_range == 'month':
            start_date = now - timedelta(days=30)
        elif date_range == 'quarter':
            start_date = now - timedelta(days=90)
        else:
            return orders
        
        return [o for o in orders if o.created_at >= start_date]
    
    def can_user_view_order(self, user, order):
        """Check if user can view order"""
        # Vendor users can view all orders
        if user.role.startswith('vendor_'):
            return True
        
        # Customer users can only view orders from their organization
        return user.customer_id == order.customer_id
    
    def can_user_approve_order(self, user, order):
        """Check if user can approve order"""
        if user.role == 'customer_dept_head':
            return order.can_be_approved_by_dept_head(user)
        elif user.role == 'customer_hr_admin':
            return order.can_be_approved_by_hr(user)
        
        return False
    
    def can_user_edit_order(self, user, order):
        """Check if user can edit order"""
        # Only order creator can edit, and only in draft status
        return (user.user_id == order.user_id and 
                order.status == 'draft')
    
    def get_customer_name(self, customer_id):
        """Get customer company name"""
        try:
            customer = Customer.get_by_id(customer_id)
            return customer.company_name if customer else 'Unknown Customer'
        except:
            return 'Unknown Customer'
    
    def restore_product_quantities(self, order):
        """Restore product quantities when order is rejected"""
        try:
            for item in order.items:
                product = Product.get_by_id(item['product_id'])
                if product:
                    product.quantity += item['quantity']
                    product.save()
        except Exception as e:
            print(f"Error restoring quantities: {e}")
    
    def send_order_notification(self, order, notification_type):
        """Send order notification emails"""
        try:
            # Get appropriate recipient based on notification type and order status
            if notification_type == 'approval_required':
                if order.status == 'pending_dept_approval':
                    # Send to department head
                    recipient = self.get_department_head_email(order.customer_id, order.department_id)
                elif order.status == 'pending_hr_approval':
                    # Send to HR admin
                    recipient = self.get_hr_admin_email(order.customer_id)
                else:
                    return
            
            elif notification_type in ['order_approved', 'order_dispatched']:
                # Send to order creator
                user = User.get_by_id(order.user_id)
                recipient = user.email if user else None
            
            elif notification_type == 'order_rejected':
                # Send to order creator
                user = User.get_by_id(order.user_id)
                recipient = user.email if user else None
            
            else:
                return
            
            if recipient:
                self.auth.send_order_notification(order, notification_type, recipient)
                
        except Exception as e:
            print(f"Send notification error: {e}")
    
    def get_department_head_email(self, customer_id, department_id):
        """Get department head email"""
        try:
            from config import config
            db = config.get_db()
            
            docs = db.collection('users').where('customer_id', '==', customer_id).where('role', '==', 'customer_dept_head').where('department_id', '==', department_id).limit(1).get()
            
            for doc in docs:
                user_data = doc.to_dict()
                return user_data.get('email')
            
            return None
        except:
            return None
    
    def get_hr_admin_email(self, customer_id):
        """Get HR admin email"""
        try:
            from config import config
            db = config.get_db()
            
            docs = db.collection('users').where('customer_id', '==', customer_id).where('role', '==', 'customer_hr_admin').limit(1).get()
            
            for doc in docs:
                user_data = doc.to_dict()
                return user_data.get('email')
            
            return None
        except:
            return None

# Global order controller instance
order_controller = OrderController()