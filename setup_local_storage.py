#!/usr/bin/env python3
"""
Setup script for local storage directories
Run this script to create the required upload directories
"""

import os

def setup_directories():
    """Create upload directories with .gitkeep files"""
    
    directories = [
        'uploads',
        'uploads/agreements',
        'uploads/products', 
        'uploads/avatars',
        'uploads/temp'
    ]
    
    print("Setting up local storage directories...")
    
    for directory in directories:
        try:
            # Create directory
            os.makedirs(directory, exist_ok=True)
            print(f"✅ Created directory: {directory}")
            
            # Create .gitkeep file
            gitkeep_path = os.path.join(directory, '.gitkeep')
            if not os.path.exists(gitkeep_path):
                with open(gitkeep_path, 'w') as f:
                    f.write('# This file ensures the directory is tracked by git\n')
                print(f"✅ Created .gitkeep: {gitkeep_path}")
            
        except Exception as e:
            print(f"❌ Error creating {directory}: {e}")
    
    print("\n🎉 Local storage setup complete!")
    print("\nDirectory structure:")
    print("uploads/")
    print("├── agreements/    # Customer agreement documents")
    print("├── products/      # Product images")
    print("├── avatars/       # User profile pictures")
    print("└── temp/          # Temporary files")
    
    print("\n📝 Don't forget to add 'uploads/*' to your .gitignore!")

if __name__ == "__main__":
    setup_directories()