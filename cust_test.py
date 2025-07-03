# Test script to create a customer and employee user for testing
# Run this script to create test data

from models import Customer, User, Department
from config import config
import uuid

def create_test_customer_and_employee():
    """Create a test customer with an employee user for testing login"""
    
    # Initialize config (make sure Firebase is set up)
    try:
        # Create test customer
        customer = Customer()
        customer.customer_id = "12345"  # Fixed customer ID for testing
        customer.company_name = "Test Company Ltd"
        customer.email = "hr@testcompany.com"
        customer.postal_address = "123 Test Street, Test City, Test State"
        customer.primary_phone = "+91-9876543210"
        customer.is_active = True
        
        if customer.save():
            print(f"✅ Created test customer: {customer.customer_id}")
            
            # Create HR Admin user
            hr_user = User.create_customer_hr_admin(
                username="12345_hr",
                email="hr@testcompany.com", 
                password="password123",
                customer_id="12345",
                full_name="HR Administrator"
            )
            hr_user.is_first_login = False  # For testing, disable first login
            hr_user.password_reset_required = False
            
            if hr_user.save():
                print(f"✅ Created HR admin user: {hr_user.username}")
                print(f"   Email: {hr_user.email}")
                print(f"   Password: password123")
            
            # Create a test department
            department = Department()
            department.customer_id = "12345"
            department.name = "IT Department"
            department.description = "Information Technology Department"
            
            if department.save():
                print(f"✅ Created department: {department.name}")
                
                # Create test employee user
                employee_user = User(
                    username="john.doe@testcompany.com",
                    email="john.doe@testcompany.com",
                    password_hash=User.hash_password("employee123"),
                    role="customer_employee"
                )
                employee_user.full_name = "John Doe"
                employee_user.customer_id = "12345"
                employee_user.department_id = department.department_id
                employee_user.is_first_login = False  # For testing
                employee_user.password_reset_required = False
                
                if employee_user.save():
                    print(f"✅ Created employee user: {employee_user.username}")
                    print(f"   Email: {employee_user.email}")
                    print(f"   Password: employee123")
                    print(f"   Customer ID: {employee_user.customer_id}")
                    print(f"   Role: {employee_user.role}")
                    
                    print("\n🎉 Test data created successfully!")
                    print("\nYou can now test login with:")
                    print("Customer ID: 12345")
                    print("Email: john.doe@testcompany.com")
                    print("Password: employee123")
                    
                    return True
        
        print("❌ Failed to create test data")
        return False
        
    except Exception as e:
        print(f"❌ Error creating test data: {e}")
        return False

if __name__ == "__main__":
    # You need to initialize your Flask app context for this to work
    print("Creating test customer and employee...")
    create_test_customer_and_employee()