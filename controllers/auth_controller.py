# Authentication Controller - Handle user authentication and session management
from flask import session, request
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import uuid
from models import User, VendorSettings

class AuthController:
    """Handle authentication and user session management"""
    
    def __init__(self):
        self.session_timeout = timedelta(hours=8)  # 8 hour session timeout
    
    def login(self, username_or_email, password, user_type='customer', customer_id=None):
        """Authenticate user and create session"""
        try:
            # For customer login, we need customer_id + email combination
            if user_type == 'customer':
                if not customer_id:
                    return {'success': False, 'message': 'Customer ID is required'}
                
                # Find user by customer_id and email - FIXED VERSION
                user = self.get_customer_user_by_email_and_customer_id(username_or_email, customer_id)
                
                if not user:
                    # Debug: Try to find what users exist for this customer
                    print(f"DEBUG: No user found for customer_id={customer_id}, email={username_or_email}")
                    # Try to find any users for this customer_id
                    from config import config
                    db = config.get_db()
                    debug_docs = db.collection('users').where('customer_id', '==', customer_id).get()
                    print(f"DEBUG: Found {len(list(debug_docs))} users for customer_id {customer_id}")
                    return {'success': False, 'message': 'Invalid login credentials'}
            else:
                # For vendor login, find by username
                user = User.get_by_username(username_or_email)
            
            if not user:
                return {'success': False, 'message': 'Invalid login credentials'}
            
            # Check if user is active
            if not user.is_active:
                return {'success': False, 'message': 'Account is deactivated'}
            
            # Verify password
            if not user.verify_password(password):
                print(f"DEBUG: Password verification failed for user {user.username}")
                return {'success': False, 'message': 'Invalid login credentials'}
            
            # Check user type matches role
            if user_type == 'vendor' and not user.role.startswith('vendor_'):
                return {'success': False, 'message': 'Invalid login type for this user'}
            
            if user_type == 'customer' and not user.role.startswith('customer_'):
                return {'success': False, 'message': 'Invalid login type for this user'}
            
            # Create session
            session['user_id'] = user.user_id
            session['username'] = user.username
            session['role'] = user.role
            session['login_time'] = datetime.now().isoformat()
            session['session_id'] = str(uuid.uuid4())
            
            # Update last login
            user.update_last_login()
            
            # Check if password reset is required
            password_reset_required = user.is_first_login or user.password_reset_required
            
            return {
                'success': True,
                'message': 'Login successful',
                'user': {
                    'user_id': user.user_id,
                    'username': user.username,
                    'role': user.role,
                    'full_name': user.full_name,
                    'email': user.email,
                    'customer_id': user.customer_id,
                    'department_id': user.department_id
                },
                'password_reset_required': password_reset_required,
                'redirect_url': self.get_default_redirect_url(user.role)
            }
            
        except Exception as e:
            print(f"Login error: {e}")
            import traceback
            traceback.print_exc()
            return {'success': False, 'message': 'Login failed'}
    
    def get_customer_user_by_email_and_customer_id(self, email, customer_id):
        """Get customer user by email and customer_id combination - DEBUG VERSION"""
        try:
            from config import config
            db = config.get_db()
            
            print(f"DEBUG: Looking for user with customer_id={customer_id}, email={email}")
            
            # Query users with customer_id first, then filter by email
            docs = db.collection('users').where('customer_id', '==', customer_id).get()
            
            print(f"DEBUG: Found {len(list(docs))} users with customer_id={customer_id}")
            
            # Re-query since docs iterator is consumed
            docs = db.collection('users').where('customer_id', '==', customer_id).get()
            
            for doc in docs:
                user_data = doc.to_dict()
                user = User.from_dict(user_data)
                
                print(f"DEBUG: Checking user:")
                print(f"  - username: {user.username}")
                print(f"  - email: {user.email}")
                print(f"  - role: {user.role}")
                print(f"  - is_active: {user.is_active}")
                print(f"  - is_first_login: {user.is_first_login}")
                print(f"  - password_reset_required: {user.password_reset_required}")
                
                # Check if email matches (either in email field or username field)
                if user.email == email or user.username == email:
                    if user.role.startswith('customer_'):
                        print(f"DEBUG: User match found: {user.username}")
                        return user
                    else:
                        print(f"DEBUG: User found but role is {user.role}, not customer role")
                else:
                    print(f"DEBUG: Email/username doesn't match. Looking for '{email}', found email='{user.email}', username='{user.username}'")
            
            print(f"DEBUG: No matching user found")
            return None
            
        except Exception as e:
            print(f"Error getting customer user: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def logout(self):
        """Clear user session"""
        try:
            # Clear all session data
            session.clear()
            
            return {
                'success': True,
                'message': 'Logged out successfully',
                'redirect_url': '/'
            }
            
        except Exception as e:
            print(f"Logout error: {e}")
            return {'success': False, 'message': 'Logout failed'}
    
    def get_current_user(self):
        """Get current authenticated user"""
        try:
            if 'user_id' not in session:
                return None
            
            # Check session timeout
            if 'login_time' in session:
                login_time = datetime.fromisoformat(session['login_time'])
                if datetime.now() - login_time > self.session_timeout:
                    session.clear()
                    return None
            
            # Get user from database
            user = User.get_by_id(session['user_id'])
            
            if not user or not user.is_active:
                session.clear()
                return None
            
            return user
            
        except Exception as e:
            print(f"Get current user error: {e}")
            return None
    
    def is_authenticated(self):
        """Check if user is authenticated"""
        return self.get_current_user() is not None
    
    def has_role(self, required_roles):
        """Check if current user has required role"""
        user = self.get_current_user()
        if not user:
            return False
        
        if isinstance(required_roles, str):
            required_roles = [required_roles]
        
        return user.role in required_roles
    
    def change_password(self, current_password, new_password):
        """Change user password"""
        try:
            user = self.get_current_user()
            if not user:
                return {'success': False, 'message': 'Authentication required'}
            
            # Verify current password
            if not user.verify_password(current_password):
                return {'success': False, 'message': 'Current password is incorrect'}
            
            # Validate new password
            validation_result = self.validate_password(new_password)
            if not validation_result['valid']:
                return {'success': False, 'message': validation_result['message']}
            
            # Change password
            if user.change_password(new_password):
                return {
                    'success': True,
                    'message': 'Password changed successfully'
                }
            else:
                return {'success': False, 'message': 'Failed to change password'}
                
        except Exception as e:
            print(f"Change password error: {e}")
            return {'success': False, 'message': 'Failed to change password'}
    
    def reset_password(self, user_id, new_password):
        """Reset user password (Admin only)"""
        try:
            current_user = self.get_current_user()
            if not current_user:
                return {'success': False, 'message': 'Authentication required'}
            
            # Check permissions
            if not self.can_manage_user(current_user, user_id):
                return {'success': False, 'message': 'Insufficient permissions'}
            
            # Get target user
            target_user = User.get_by_id(user_id)
            if not target_user:
                return {'success': False, 'message': 'User not found'}
            
            # Validate new password
            validation_result = self.validate_password(new_password)
            if not validation_result['valid']:
                return {'success': False, 'message': validation_result['message']}
            
            # Reset password
            target_user.password_hash = User.hash_password(new_password)
            target_user.password_reset_required = True
            target_user.is_first_login = True
            
            if target_user.save():
                return {
                    'success': True,
                    'message': 'Password reset successfully'
                }
            else:
                return {'success': False, 'message': 'Failed to reset password'}
                
        except Exception as e:
            print(f"Reset password error: {e}")
            return {'success': False, 'message': 'Failed to reset password'}
    
    def validate_password(self, password):
        """Validate password strength"""
        if len(password) < 8:
            return {'valid': False, 'message': 'Password must be at least 8 characters long'}
        
        if not any(c.isupper() for c in password):
            return {'valid': False, 'message': 'Password must contain at least one uppercase letter'}
        
        if not any(c.islower() for c in password):
            return {'valid': False, 'message': 'Password must contain at least one lowercase letter'}
        
        if not any(c.isdigit() for c in password):
            return {'valid': False, 'message': 'Password must contain at least one number'}
        
        return {'valid': True, 'message': 'Password is valid'}
    
    def can_manage_user(self, manager, target_user_id):
        """Check if manager can manage target user"""
        target_user = User.get_by_id(target_user_id)
        if not target_user:
            return False
        
        # Vendor SuperAdmin can manage all vendor users
        if manager.role == 'vendor_superadmin':
            return target_user.role.startswith('vendor_') or target_user.role.startswith('customer_')
        
        # Vendor Admin can manage vendor normal users and customer users
        if manager.role == 'vendor_admin':
            return (target_user.role == 'vendor_normal' or 
                   target_user.role.startswith('customer_'))
        
        # Customer HR Admin can manage users in their organization
        if manager.role == 'customer_hr_admin':
            return (target_user.customer_id == manager.customer_id and
                   target_user.role in ['customer_dept_head', 'customer_employee'])
        
        return False
    
    def get_default_redirect_url(self, role):
        """Get default redirect URL after login based on role"""
        role_redirects = {
            'vendor_superadmin': '/dashboard',
            'vendor_admin': '/dashboard',
            'vendor_normal': '/orders',
            'customer_hr_admin': '/dashboard',
            'customer_dept_head': '/orders',
            'customer_employee': '/products'
        }
        
        return role_redirects.get(role, '/dashboard')
    
    def send_email_notification(self, to_email, subject, body, is_html=False):
        """Send email notification using vendor email settings"""
        try:
            settings = VendorSettings.get_settings()
            
            if not settings.email_address or not settings.email_password:
                print("Email settings not configured")
                return False
            
            # Create message
            message = MIMEMultipart("alternative")
            message["Subject"] = subject
            message["From"] = settings.email_address
            message["To"] = to_email
            
            # Add body to email
            if is_html:
                body_part = MIMEText(body, "html")
            else:
                body_part = MIMEText(body, "plain")
            
            message.attach(body_part)
            
            # Create secure connection and send email
            context = ssl.create_default_context()
            
            with smtplib.SMTP(settings.email_server_url, settings.email_port) as server:
                if settings.email_use_tls:
                    server.starttls(context=context)
                
                server.login(settings.email_username or settings.email_address, settings.email_password)
                server.sendmail(settings.email_address, to_email, message.as_string())
            
            print(f"Email sent to {to_email}")
            return True
            
        except Exception as e:
            print(f"Email sending error: {e}")
            return False
    
    def send_welcome_email(self, user, temp_password):
        """Send welcome email to new user"""
        try:
            settings = VendorSettings.get_settings()
            
            subject = f"Welcome to {settings.company_name} - Office Supplies System"
            
            html_body = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5; }}
                    .container {{ max-width: 600px; margin: 0 auto; background-color: white; padding: 40px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                    .header {{ text-align: center; margin-bottom: 30px; }}
                    .logo {{ font-size: 24px; font-weight: bold; color: #2563eb; margin-bottom: 10px; }}
                    .title {{ font-size: 20px; color: #1f2937; margin-bottom: 10px; }}
                    .credentials {{ background-color: #f8fafc; padding: 20px; border-radius: 6px; margin: 20px 0; border-left: 4px solid #2563eb; }}
                    .footer {{ margin-top: 30px; padding-top: 20px; border-top: 1px solid #e5e7eb; color: #6b7280; font-size: 14px; }}
                    .warning {{ background-color: #fef3c7; padding: 15px; border-radius: 6px; border-left: 4px solid #f59e0b; margin: 20px 0; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <div class="logo">{settings.company_name}</div>
                        <div class="title">Welcome to Office Supplies System</div>
                    </div>
                    
                    <p>Hello {user.full_name or user.username},</p>
                    
                    <p>Your account has been created successfully. You can now access the Office Supplies System using the credentials below:</p>
                    
                    <div class="credentials">
                        <strong>Login Credentials:</strong><br>
                        <strong>Username:</strong> {user.username}<br>
                        <strong>Temporary Password:</strong> {temp_password}<br>
                        <strong>Role:</strong> {user.role.replace('_', ' ').title()}
                    </div>
                    
                    <div class="warning">
                        <strong>Important:</strong> Please change your password immediately after your first login for security purposes.
                    </div>
                    
                    <p><strong>Login URLs:</strong></p>
                    <ul>
                        <li><strong>Customer Portal:</strong> <a href="http://localhost:5000/login">http://localhost:5000/login</a></li>
                        <li><strong>Vendor Portal:</strong> <a href="http://localhost:5000/vendor-login">http://localhost:5000/vendor-login</a></li>
                    </ul>
                    
                    <p>If you have any questions or need assistance, please contact our support team.</p>
                    
                    <div class="footer">
                        <p>Best regards,<br>{settings.company_name} Team</p>
                        <p>This is an automated message. Please do not reply to this email.</p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            return self.send_email_notification(user.email, subject, html_body, True)
            
        except Exception as e:
            print(f"Welcome email error: {e}")
            return False
        
    
    def send_order_notification(self, order, notification_type, recipient_email):
        """Send order-related email notifications"""
        try:
            settings = VendorSettings.get_settings()
            
            notification_subjects = {
                'order_placed': 'Order Placed Successfully',
                'order_approved': 'Order Approved',
                'order_rejected': 'Order Rejected',
                'order_dispatched': 'Order Dispatched',
                'approval_required': 'Order Approval Required'
            }
            
            subject = f"{notification_subjects.get(notification_type, 'Order Update')} - #{order.order_id}"
            
            html_body = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5; }}
                    .container {{ max-width: 600px; margin: 0 auto; background-color: white; padding: 40px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                    .header {{ text-align: center; margin-bottom: 30px; }}
                    .order-info {{ background-color: #f8fafc; padding: 20px; border-radius: 6px; margin: 20px 0; }}
                    .footer {{ margin-top: 30px; padding-top: 20px; border-top: 1px solid #e5e7eb; color: #6b7280; font-size: 14px; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h2>{notification_subjects.get(notification_type, 'Order Update')}</h2>
                    </div>
                    
                    <div class="order-info">
                        <strong>Order Details:</strong><br>
                        <strong>Order ID:</strong> {order.order_id}<br>
                        <strong>Status:</strong> {order.status.replace('_', ' ').title()}<br>
                        <strong>Total Amount:</strong> ₹{order.total_amount:,.2f}<br>
                        <strong>Items:</strong> {len(order.items)} item(s)
                    </div>
                    
                    <p>Please login to the system to view complete order details and take any required actions.</p>
                    
                    <div class="footer">
                        <p>Best regards,<br>{settings.company_name} Team</p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            return self.send_email_notification(recipient_email, subject, html_body, True)
            
        except Exception as e:
            print(f"Order notification email error: {e}")
            return False
    
    def send_email_notification(self, to_email, subject, body, is_html=False):
        """Send email notification using enhanced vendor email settings - FIXED VERSION"""
        try:
            settings = VendorSettings.get_settings()
            
            # Validate email configuration
            if not settings.email_address or not settings.email_password:
                print("Email configuration incomplete: Missing email address or password")
                return False
                
            if not settings.email_server_url:
                print("Email configuration incomplete: Missing server URL")
                return False
            
            # Create message
            message = MIMEMultipart("alternative")
            message["Subject"] = subject
            
            # Set From field with display name if configured
            if getattr(settings, 'email_from_name', None):
                message["From"] = f"{settings.email_from_name} <{settings.email_address}>"
            else:
                message["From"] = settings.email_address
                
            message["To"] = to_email
            
            # Add body to email - Fix HTML formatting issues
            if is_html:
                # Clean the HTML body to avoid formatting issues
                cleaned_body = body.replace('\n', '').replace('  ', ' ')
                body_part = MIMEText(cleaned_body, "html", "utf-8")
            else:
                body_part = MIMEText(body, "plain", "utf-8")
            
            message.attach(body_part)
            
            # Create SMTP connection with enhanced configuration
            try:
                # Use SSL or TLS based on configuration
                if getattr(settings, 'email_use_ssl', False):
                    # Direct SSL connection (usually port 465)
                    context = ssl.create_default_context()
                    server = smtplib.SMTP_SSL(
                        settings.email_server_url, 
                        settings.email_port or 465,
                        timeout=getattr(settings, 'email_timeout', 30),
                        context=context
                    )
                else:
                    # Regular connection, optionally with STARTTLS
                    server = smtplib.SMTP(
                        settings.email_server_url, 
                        settings.email_port or 587,
                        timeout=getattr(settings, 'email_timeout', 30)
                    )
                    
                    if settings.email_use_tls:
                        context = ssl.create_default_context()
                        server.starttls(context=context)
                
                # Authenticate
                server.login(
                    settings.email_username or settings.email_address, 
                    settings.email_password
                )
                
                # Send email
                server.sendmail(settings.email_address, to_email, message.as_string())
                server.quit()
                
                print(f"Email sent successfully to {to_email}")
                return True
                
            except smtplib.SMTPAuthenticationError as e:
                print(f"SMTP Authentication failed: {e}")
                return False
            except smtplib.SMTPConnectError as e:
                print(f"SMTP Connection failed: {e}")
                return False
            except smtplib.SMTPRecipientsRefused as e:
                print(f"SMTP Recipients refused: {e}")
                return False
            except Exception as e:
                print(f"SMTP Error: {e}")
                return False
                
        except Exception as e:
            print(f"Email sending error: {e}")
            import traceback
            traceback.print_exc()
            return False
        
    def test_smtp_connection(self):
        """Test SMTP connection without sending email"""
        try:
            settings = VendorSettings.get_settings()
            
            if not settings.email_server_url:
                return {'success': False, 'message': 'Server URL is required'}
            
            try:
                if settings.email_use_ssl:
                    context = ssl.create_default_context()
                    server = smtplib.SMTP_SSL(
                        settings.email_server_url, 
                        settings.email_port or 465,
                        timeout=settings.email_timeout or 30,
                        context=context
                    )
                else:
                    server = smtplib.SMTP(
                        settings.email_server_url, 
                        settings.email_port or 587,
                        timeout=settings.email_timeout or 30
                    )
                    
                    if settings.email_use_tls:
                        context = ssl.create_default_context()
                        server.starttls(context=context)
                
                # Test authentication if credentials provided
                if settings.email_username and settings.email_password:
                    server.login(
                        settings.email_username or settings.email_address, 
                        settings.email_password
                    )
                
                server.quit()
                return {'success': True, 'message': 'SMTP connection successful'}
                
            except smtplib.SMTPAuthenticationError:
                return {'success': False, 'message': 'Authentication failed - check username/password'}
            except smtplib.SMTPConnectError:
                return {'success': False, 'message': 'Connection failed - check server URL and port'}
            except Exception as e:
                return {'success': False, 'message': f'Connection test failed: {str(e)}'}
                
        except Exception as e:
            return {'success': False, 'message': f'Test failed: {str(e)}'}

    def get_email_server_suggestions(self, email_address):
        """Get email server suggestions based on email domain"""
        if not email_address or '@' not in email_address:
            return {}
        
        domain = email_address.split('@')[1].lower()
        
        # Common email provider configurations
        provider_configs = {
            'gmail.com': {
                'server_url': 'smtp.gmail.com',
                'port_ssl': 465,
                'port_tls': 587,
                'use_tls': True,
                'use_ssl': False,
                'note': 'For Gmail, you may need to use App Passwords instead of your regular password'
            },
            'outlook.com': {
                'server_url': 'smtp-mail.outlook.com',
                'port_ssl': 587,
                'port_tls': 587,
                'use_tls': True,
                'use_ssl': False
            },
            'hotmail.com': {
                'server_url': 'smtp-mail.outlook.com',
                'port_ssl': 587,
                'port_tls': 587,
                'use_tls': True,
                'use_ssl': False
            },
            'yahoo.com': {
                'server_url': 'smtp.mail.yahoo.com',
                'port_ssl': 465,
                'port_tls': 587,
                'use_tls': True,
                'use_ssl': False
            },
            'icloud.com': {
                'server_url': 'smtp.mail.me.com',
                'port_ssl': 587,
                'port_tls': 587,
                'use_tls': True,
                'use_ssl': False
            }
        }
        
        return provider_configs.get(domain, {
            'note': 'Please contact your email provider for SMTP configuration details'
        })
# Global auth controller instance
auth_controller = AuthController()