# Office Supplies Vendor System

A comprehensive Flask-based web application for managing office supply ordering between vendors and customers, featuring multi-tier user roles, order approval workflows, and Firebase integration.

## Features

### Vendor Features
- **Multi-tier User Roles**: SuperAdmin, Admin, and Normal users
- **Customer Management**: Register and manage customer organizations
- **Product Catalog**: Manage products with categories, pricing, and inventory
- **Order Processing**: Handle orders through approval workflows
- **Dashboard Analytics**: View system statistics and metrics
- **Email Notifications**: Automated notifications for order updates

### Customer Features
- **Organization Structure**: HR Admin, Department Head, and Employee roles
- **Department Management**: Organize users by departments
- **Product Browsing**: Browse vendor's product catalog
- **Shopping Cart**: Add products and manage orders
- **Approval Workflow**: Three-tier approval process (Employee → Dept Head → HR Admin)
- **Order Tracking**: Track order status from creation to dispatch

### Technical Features
- **Firebase Integration**: Firestore database and Storage for file uploads
- **Responsive Design**: Modern, mobile-friendly interface
- **Security**: Role-based access control and secure authentication
- **File Uploads**: Support for agreement documents and product images
- **API Architecture**: RESTful API with comprehensive error handling

## System Architecture

### User Hierarchy

**Vendor Side:**
- SuperAdmin: Full system control, customer management
- Admin: Product and order management, user management (except SuperAdmin)
- Normal: Order processing and inventory management

**Customer Side:**
- HR Admin: Organization management, user creation, final order approval
- Department Head: Department management, order approval
- Employee: Product browsing, order creation

### Order Workflow
1. Employee creates order → Pending Department Approval
2. Department Head reviews → Pending HR Approval  
3. HR Admin approves → Approved (sent to vendor)
4. Vendor processes → Packed → Ready for Dispatch → Dispatched

## Prerequisites

- Python 3.8 or higher
- Firebase Project with Firestore and Storage enabled
- SMTP server for email notifications (optional)

## Installation

### 1. Clone the Repository

```bash
git clone <repository-url>
cd office-supplies-system
```

### 2. Create Virtual Environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Firebase Setup

#### Create Firebase Project
1. Go to [Firebase Console](https://console.firebase.google.com/)
2. Create a new project
3. Enable Firestore Database (Start in test mode)
4. Enable Storage
5. Create a service account:
   - Go to Project Settings → Service Accounts
   - Click "Generate new private key"
   - Download the JSON file

#### Configure Firebase
1. Place the downloaded service account JSON file in your project root
2. Rename it to `firebase-credentials.json`

Or set environment variables:
```bash
export FIREBASE_CREDENTIALS_JSON='{"type": "service_account", ...}'
export FIREBASE_STORAGE_BUCKET='your-project-id.appspot.com'
```

### 5. Environment Configuration

Create a `.env` file in the project root:

```env
# Flask Configuration
SECRET_KEY=your-secret-key-here
FLASK_ENV=development

# Firebase Configuration (if not using JSON file)
FIREBASE_CREDENTIALS_PATH=firebase-credentials.json
FIREBASE_STORAGE_BUCKET=your-project-id.appspot.com

# Email Configuration (optional)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
```

### 6. Initialize Database

The application will automatically create initial data on first run:
- Default vendor settings
- SuperAdmin user (username: `superadmin`, password: `admin123`)
- Product categories

### 7. Run the Application

```bash
python app.py
```

The application will be available at `http://localhost:5000`

## Default Login Credentials

**Vendor SuperAdmin:**
- Username: `superadmin`
- Password: `admin123`
- Portal: `http://localhost:5000/vendor-login`

⚠️ **Important**: Change the default password immediately after first login!

## Usage Guide

### Initial Setup

1. **Login as SuperAdmin**
   - Access vendor portal and login with default credentials
   - Change default password in Settings

2. **Configure Vendor Settings**
   - Go to Settings → Vendor Configuration
   - Update company information and email settings

3. **Register First Customer**
   - Go to Customers → Register Customer
   - Fill in company details and upload agreement
   - HR Admin credentials will be auto-generated

4. **Add Products**
   - Go to Products → Add Product
   - Configure product details, pricing, and inventory

### Customer Onboarding

1. **HR Admin Setup**
   - Customer HR Admin receives login credentials
   - Login and change password
   - Update profile information

2. **Create Departments**
   - HR Admin creates organizational departments
   - Assign department heads

3. **Add Users**
   - Create department head and employee accounts
   - Assign users to appropriate departments

### Daily Operations

**For Employees:**
1. Browse product catalog
2. Add items to cart
3. Submit orders for approval

**For Department Heads:**
1. Review pending department orders
2. Approve or reject with comments

**For HR Admins:**
1. Final approval of orders
2. Manage organizational users
3. Monitor spending and orders

**For Vendors:**
1. Process approved orders
2. Update order status (packed, dispatched)
3. Manage inventory and pricing
4. Monitor customer relationships

## API Endpoints

### Authentication
- `POST /api/auth/login` - User login
- `POST /api/auth/logout` - User logout
- `PUT /api/auth/change-password` - Change password

### Products
- `GET /api/products` - List products
- `POST /api/products` - Create product (vendor only)
- `GET /api/products/{id}` - Get product details
- `PUT /api/products/{id}` - Update product (vendor only)

### Orders
- `GET /api/orders` - List orders
- `POST /api/orders` - Create order (employees only)
- `GET /api/orders/{id}` - Get order details
- `PUT /api/orders/{id}/dept-approval` - Department approval
- `PUT /api/orders/{id}/hr-approval` - HR approval
- `PUT /api/orders/{id}/pack` - Mark as packed (vendor)
- `PUT /api/orders/{id}/dispatch` - Mark as dispatched (vendor)

### Customers
- `GET /api/customers` - List customers (vendor only)
- `POST /api/customers` - Register customer (superadmin only)
- `GET /api/customers/{id}` - Get customer details

### Users
- `GET /api/users` - List users
- `POST /api/users` - Create user
- `PUT /api/users/{id}` - Update user
- `PUT /api/users/{id}/reset-password` - Reset password

## File Structure

```
office-supplies-system/
├── app.py                 # Main Flask application
├── config.py             # Firebase configuration
├── requirements.txt      # Python dependencies
├── README.md            # This file
├── models.py            # Data models
├── controllers/         # Business logic controllers
│   ├── auth_controller.py
│   ├── vendor_controller.py
│   ├── product_controller.py
│   ├── order_controller.py
│   ├── customer_controller.py
│   └── user_controller.py
├── templates/           # HTML templates
│   ├── base.html
│   ├── auth/
│   │   ├── login.html
│   │   └── vendor_login.html
│   ├── dashboards/
│   │   ├── vendor_dashboard.html
│   │   ├── customer_employee_dashboard.html
│   │   ├── customer_hr_dashboard.html
│   │   └── customer_dept_dashboard.html
│   ├── customers.html
│   ├── orders.html
│   ├── profile.html
│   └── errors/
│       ├── 404.html
│       └── 500.html
└── static/             # Static files (CSS, JS, images)
    ├── css/
    ├── js/
    └── images/
```

## Security Considerations

1. **Change Default Passwords**: Always change default credentials
2. **Environment Variables**: Use environment variables for sensitive data
3. **HTTPS**: Use HTTPS in production
4. **Firebase Rules**: Configure proper Firestore security rules
5. **Input Validation**: All user inputs are validated server-side
6. **Role-based Access**: Strict role-based access control implemented

## Deployment

### Production Setup

1. **Environment Variables**
   ```bash
   export FLASK_ENV=production
   export SECRET_KEY=your-production-secret-key
   ```

2. **Using Gunicorn**
   ```bash
   gunicorn -w 4 -b 0.0.0.0:8000 app:app
   ```

3. **Using Waitress (Windows)**
   ```bash
   waitress-serve --host=0.0.0.0 --port=8000 app:app
   ```

### Firebase Security Rules

Configure Firestore security rules for production:

```javascript
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    // Allow authenticated users to read/write their own data
    match /{document=**} {
      allow read, write: if request.auth != null;
    }
  }
}
```

## Troubleshooting

### Common Issues

1. **Firebase Connection Error**
   - Verify credentials file path
   - Check Firebase project configuration
   - Ensure Firestore and Storage are enabled

2. **Email Not Sending**
   - Verify SMTP settings
   - Check email credentials
   - Ensure "Less secure app access" is enabled (Gmail)

3. **Login Issues**
   - Verify user exists in database
   - Check password hash
   - Clear browser cache/cookies

4. **File Upload Errors**
   - Check Firebase Storage permissions
   - Verify file size limits
   - Ensure supported file types

### Debug Mode

Enable debug mode for development:
```bash
export FLASK_DEBUG=1
python app.py
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For support and questions:
1. Check the troubleshooting section
2. Review Firebase console for error logs
3. Check application logs for detailed error messages
4. Ensure all dependencies are properly installed

## Changelog

### Version 1.0.0
- Initial release
- Complete vendor and customer workflows
- Firebase integration
- Responsive web interface
- Multi-tier user authentication
- Order approval workflows
- Product catalog management
- Email notifications