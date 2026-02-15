import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'ai-master-pro-secure-key-2026')
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin123') # Default for owner
    DATABASE_PATH = 'database.db'
    DEBUG = True
