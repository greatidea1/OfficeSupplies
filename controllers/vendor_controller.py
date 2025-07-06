# Enhanced Vendor Settings Controller - Handle vendor configuration with improved email settings
from flask import session, request, jsonify
from models import VendorSettings
from controllers.auth_controller import auth_controller

class VendorController:
    """Handle vendor settings and configuration"""
    
    def __init__(self):
        self.auth = auth_controller
    
    def get_vendor_settings(self):
        """Get vendor settings (Vendor users only)"""
        try:
            current_user = self.auth.get_current_user()
            if not current_user or current_user.role not in ['vendor_superadmin', 'vendor_admin', 'vendor_normal']:
                return {'success': False, 'message': 'Only vendor users can view settings'}
            
            settings = VendorSettings.get_settings()
            
            # Prepare settings data based on user role
            settings_data = {
                'company_name': settings.company_name,
                'postal_address': settings.postal_address,
                'primary_contact_name': settings.primary_contact_name,
                'primary_contact_phone': settings.primary_contact_phone,
                'alternate_contact_name': settings.alternate_contact_name,
                'alternate_contact_phone': settings.alternate_contact_phone,
                'email_address': settings.email_address
            }
            
            # Include email settings for SuperAdmin
            if current_user.role == 'vendor_superadmin':
                settings_data.update({
                    'email_server_url': settings.email_server_url,
                    'email_port': settings.email_port,
                    'email_username': settings.email_username,
                    'email_use_tls': settings.email_use_tls,
                    'email_use_ssl': getattr(settings, 'email_use_ssl', False),
                    'email_timeout': getattr(settings, 'email_timeout', 30),
                    'email_from_name': getattr(settings, 'email_from_name', settings.company_name or 'Office Supplies System')
                })
            
            return {
                'success': True,
                'settings': settings_data
            }
            
        except Exception as e:
            print(f"Get vendor settings error: {e}")
            return {'success': False, 'message': 'Failed to retrieve vendor settings'}
    
    def update_vendor_settings(self, updates):
        """Update vendor settings (SuperAdmin only)"""
        try:
            current_user = self.auth.get_current_user()
            if not current_user or current_user.role != 'vendor_superadmin':
                return {'success': False, 'message': 'Only SuperAdmin can update vendor settings'}
            
            settings = VendorSettings.get_settings()
            
            # Update allowed fields
            allowed_fields = [
                'company_name', 'postal_address', 'primary_contact_name',
                'primary_contact_phone', 'alternate_contact_name', 'alternate_contact_phone',
                'email_address', 'email_username', 'email_password', 'email_server_url',
                'email_port', 'email_use_tls', 'email_use_ssl', 'email_timeout', 'email_from_name'
            ]
            
            for field, value in updates.items():
                if field in allowed_fields:
                    if field == 'email_port':
                        setattr(settings, field, int(value) if value else 587)
                    elif field in ['email_use_tls', 'email_use_ssl']:
                        setattr(settings, field, bool(value))
                    elif field == 'email_timeout':
                        setattr(settings, field, int(value) if value else 30)
                    else:
                        setattr(settings, field, value)
            
            if settings.save():
                return {
                    'success': True,
                    'message': 'Vendor settings updated successfully'
                }
            else:
                return {'success': False, 'message': 'Failed to update vendor settings'}
                
        except Exception as e:
            print(f"Update vendor settings error: {e}")
            return {'success': False, 'message': 'Failed to update vendor settings'}
    
    def test_email_configuration(self):
        """Test email configuration with enhanced message (SuperAdmin only) - FIXED VERSION"""
        try:
            current_user = self.auth.get_current_user()
            if not current_user or current_user.role != 'vendor_superadmin':
                return {'success': False, 'message': 'Only SuperAdmin can test email configuration'}
            
            settings = VendorSettings.get_settings()
            
            if not settings.email_address or not settings.email_password:
                return {'success': False, 'message': 'Email configuration is incomplete. Please configure email address and password.'}
            
            if not settings.email_server_url:
                return {'success': False, 'message': 'Email server URL is required for email configuration.'}
            
            # Enhanced test email content - FIXED HTML formatting
            test_subject = "Successful Email tested from Office Supplies Application"
            
            # Simplified HTML to avoid formatting issues
            company_name = settings.company_name or 'Office Supplies System'
            
            test_body = f"""<!DOCTYPE html>
                            <html>
                            <head>
                                <meta charset="UTF-8">
                                <style>
                                    body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5; }}
                                    .container {{ max-width: 600px; margin: 0 auto; background-color: white; padding: 40px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                                    .header {{ text-align: center; margin-bottom: 30px; }}
                                    .logo {{ font-size: 24px; font-weight: bold; color: #2563eb; margin-bottom: 10px; }}
                                    .success-icon {{ font-size: 48px; color: #10b981; margin-bottom: 20px; }}
                                    .message {{ font-size: 16px; line-height: 1.6; color: #374151; margin-bottom: 30px; }}
                                    .footer {{ margin-top: 30px; padding-top: 20px; border-top: 1px solid #e5e7eb; color: #6b7280; font-size: 14px; text-align: center; }}
                                    .link {{ color: #2563eb; text-decoration: none; }}
                                </style>
                            </head>
                            <body>
                                <div class="container">
                                    <div class="header">
                                        <div class="success-icon">✅</div>
                                        <div class="logo">{company_name}</div>
                                        <h2 style="color: #10b981; margin: 0;">Email Test Successful!</h2>
                                    </div>
                                    
                                    <div class="message">
                                        <p><strong>Congratulations!</strong></p>
                                        <p>Your email sender configuration is working perfectly from the Office Supplies application.</p>
                                        <p>This test confirms that:</p>
                                        <ul>
                                            <li>SMTP server connection is successful</li>
                                            <li>Authentication credentials are valid</li>
                                            <li>Email delivery is functional</li>
                                        </ul>
                                        <p>You can now send automated notifications, welcome emails, and order updates to your customers.</p>
                                    </div>
                                    
                                    <div class="footer">
                                        <p>This is an automated test message from {company_name}</p>
                                        <p>Office Supplies application powered by <a href="https://quadrang.com" class="link">Quadrang Systems</a></p>
                                    </div>
                                </div>
                            </body>
                            </html>"""
            
            # Send enhanced test email
            email_sent = self.auth.send_email_notification(
                settings.email_address,
                test_subject,
                test_body,
                True
            )
            
            if email_sent:
                return {
                    'success': True,
                    'message': f'Test email sent successfully to {settings.email_address}'
                }
            else:
                return {
                    'success': False,
                    'message': 'Failed to send test email. Please check your email configuration settings.'
                }
                
        except Exception as e:
            print(f"Test email error: {e}")
            import traceback
            traceback.print_exc()
            return {'success': False, 'message': f'Failed to test email configuration: {str(e)}'}
    
    def validate_email_configuration(self):
        """Validate email configuration without sending email"""
        try:
            current_user = self.auth.get_current_user()
            if not current_user or current_user.role != 'vendor_superadmin':
                return {'success': False, 'message': 'Only SuperAdmin can validate email configuration'}
            
            settings = VendorSettings.get_settings()
            
            validation_results = {
                'email_address_valid': bool(settings.email_address and '@' in settings.email_address),
                'password_provided': bool(settings.email_password),
                'server_url_provided': bool(settings.email_server_url),
                'port_valid': bool(settings.email_port and 1 <= settings.email_port <= 65535),
                'username_provided': bool(settings.email_username)
            }
            
            all_valid = all(validation_results.values())
            
            return {
                'success': True,
                'validation': validation_results,
                'is_complete': all_valid,
                'message': 'Email configuration is complete' if all_valid else 'Email configuration is incomplete'
            }
            
        except Exception as e:
            print(f"Validate email error: {e}")
            return {'success': False, 'message': 'Failed to validate email configuration'}
    
    # ... (rest of the existing methods remain the same)
    
    def get_dashboard_statistics(self):
        """Get dashboard statistics for vendor users"""
        try:
            current_user = self.auth.get_current_user()
            if not current_user or current_user.role not in ['vendor_superadmin', 'vendor_admin', 'vendor_normal']:
                return {'success': False, 'message': 'Only vendor users can view dashboard'}
            
            from config import config
            from datetime import datetime, timedelta
            
            db = config.get_db()
            
            # Get order statistics
            total_orders = len(list(db.collection('orders').get()))
            
            # Pending orders (waiting for vendor action)
            pending_orders = len(list(db.collection('orders').where('status', '==', 'approved').get()))
            
            # Orders ready for dispatch
            ready_for_dispatch = len(list(db.collection('orders').where('status', '==', 'ready_for_dispatch').get()))
            
            # Orders this month
            thirty_days_ago = datetime.now() - timedelta(days=30)
            recent_orders = list(db.collection('orders')
                               .where('created_at', '>=', thirty_days_ago)
                               .get())
            
            # Active customers
            active_customers = len(list(db.collection('customers').where('is_active', '==', True).get()))
            
            # Total products
            total_products = len(list(db.collection('products').where('is_active', '==', True).get()))
            
            # Low stock products (quantity < 10)
            low_stock_products = []
            products = db.collection('products').where('is_active', '==', True).get()
            for product_doc in products:
                product_data = product_doc.to_dict()
                if product_data.get('quantity', 0) < 10:
                    low_stock_products.append({
                        'product_id': product_data['product_id'],
                        'product_name': product_data['product_name'],
                        'quantity': product_data['quantity']
                    })
            
            # Calculate total revenue (completed orders)
            total_revenue = 0
            completed_orders = db.collection('orders').where('status', '==', 'dispatched').get()
            for order_doc in completed_orders:
                order_data = order_doc.to_dict()
                total_revenue += order_data.get('total_amount', 0)
            
            return {
                'success': True,
                'statistics': {
                    'total_orders': total_orders,
                    'pending_orders': pending_orders,
                    'ready_for_dispatch': ready_for_dispatch,
                    'orders_this_month': len(recent_orders),
                    'active_customers': active_customers,
                    'total_products': total_products,
                    'low_stock_count': len(low_stock_products),
                    'total_revenue': total_revenue,
                    'low_stock_products': low_stock_products[:5]  # Top 5 low stock items
                }
            }
            
        except Exception as e:
            print(f"Get dashboard statistics error: {e}")
            return {'success': False, 'message': 'Failed to retrieve dashboard statistics'}
    
    def get_customer_dropdown_data(self):
        """Get customer data for dropdown selection (SuperAdmin/Admin only)"""
        try:
            current_user = self.auth.get_current_user()
            if not current_user or current_user.role not in ['vendor_superadmin', 'vendor_admin']:
                return {'success': False, 'message': 'Access denied'}
            
            from models import Customer
            customers = Customer.get_all_active()
            
            customer_list = []
            for customer in customers:
                customer_list.append({
                    'customer_id': customer.customer_id,
                    'company_name': customer.company_name
                })
            
            return {
                'success': True,
                'customers': customer_list
            }
            
        except Exception as e:
            print(f"Get customer dropdown error: {e}")
            return {'success': False, 'message': 'Failed to retrieve customer data'}
    
    def get_system_health(self):
        """Get system health status (SuperAdmin only)"""
        try:
            current_user = self.auth.get_current_user()
            if not current_user or current_user.role != 'vendor_superadmin':
                return {'success': False, 'message': 'Only SuperAdmin can view system health'}
            
            from config import config
            
            # Check database connectivity
            db_healthy = True
            try:
                config.get_db().collection('vendor_settings').limit(1).get()
            except Exception:
                db_healthy = False
            
            # Check storage connectivity
            storage_healthy = True
            try:
                config.get_storage().list_blobs(max_results=1)
            except Exception:
                storage_healthy = False
            
            # Check email configuration
            settings = VendorSettings.get_settings()
            email_configured = bool(settings.email_address and settings.email_password and settings.email_server_url)
            
            # Get error logs count (if implemented)
            error_count = 0  # Placeholder - implement error logging as needed
            
            return {
                'success': True,
                'health': {
                    'database_healthy': db_healthy,
                    'storage_healthy': storage_healthy,
                    'email_configured': email_configured,
                    'recent_errors': error_count,
                    'overall_status': 'healthy' if (db_healthy and storage_healthy) else 'issues'
                }
            }
            
        except Exception as e:
            print(f"Get system health error: {e}")
            return {'success': False, 'message': 'Failed to retrieve system health'}
    
    def export_data(self, export_type, date_range=None):
        """Export system data (SuperAdmin only)"""
        try:
            current_user = self.auth.get_current_user()
            if not current_user or current_user.role != 'vendor_superadmin':
                return {'success': False, 'message': 'Only SuperAdmin can export data'}
            
            from config import config
            import json
            from datetime import datetime
            
            db = config.get_db()
            export_data = {}
            
            if export_type == 'orders':
                orders = []
                docs = db.collection('orders').get()
                for doc in docs:
                    order_data = doc.to_dict()
                    # Convert datetime objects to strings for JSON serialization
                    for key, value in order_data.items():
                        if isinstance(value, datetime):
                            order_data[key] = value.isoformat()
                    orders.append(order_data)
                export_data['orders'] = orders
                
            elif export_type == 'customers':
                customers = []
                docs = db.collection('customers').get()
                for doc in docs:
                    customer_data = doc.to_dict()
                    for key, value in customer_data.items():
                        if isinstance(value, datetime):
                            customer_data[key] = value.isoformat()
                    customers.append(customer_data)
                export_data['customers'] = customers
                
            elif export_type == 'products':
                products = []
                docs = db.collection('products').get()
                for doc in docs:
                    product_data = doc.to_dict()
                    for key, value in product_data.items():
                        if isinstance(value, datetime):
                            product_data[key] = value.isoformat()
                    products.append(product_data)
                export_data['products'] = products
            
            return {
                'success': True,
                'export_data': export_data,
                'export_timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            print(f"Export data error: {e}")
            return {'success': False, 'message': 'Failed to export data'}

# Global vendor controller instance
vendor_controller = VendorController()