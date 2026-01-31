@echo off
echo Installing Inventory Management System with Tally Integration...
echo.

echo Creating Python virtual environment...
python -m venv venv
call venv\Scripts\activate.bat

echo.
echo Upgrading pip and installing dependencies...
pip install --upgrade pip
pip install Flask==2.3.3 Flask-SQLAlchemy==3.0.5 Flask-Login==0.6.3 Werkzeug==2.3.7 pandas openpyxl==3.0.10 requests==2.28.2

echo.
echo Creating necessary directories...
if not exist "templates" mkdir templates
if not exist "backups" mkdir backups
if not exist "static" mkdir static

echo.
echo Running database setup...
python migrate_database.py

echo.
echo Running schema migration...
python migration_add_tally_guid.py

echo.
echo Installation complete!
echo.
echo To run the system:
echo 1. venv\Scripts\activate.bat
echo 2. python app.py
echo.
echo The application will be available at: http://localhost:5000
echo.
echo Default Login Credentials:
echo Admin: admin / admin123
echo Manager: manager / manager123
echo.
echo Tally Integration Features:
echo - Import items, suppliers, customers from Tally
echo - Export data to Tally
echo - Bulk sync operations
echo.
pause