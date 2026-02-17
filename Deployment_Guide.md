# Deployment Guide for AI MASTER PRO on PythonAnywhere

This guide provides step-by-step instructions to deploy the AI MASTER PRO application on PythonAnywhere's free tier.

## 1. Prepare your PythonAnywhere Account

1.  **Create an account:** If you don't have one, sign up for a free PythonAnywhere account at [www.pythonanywhere.com](https://www.pythonanywhere.com/).
2.  **Start a new web app:** Go to the "Web" tab and click "Add a new web app".
3.  **Choose Flask:** Select "Flask" as your web framework.
4.  **Python version:** Choose Python 3.9 or higher.

## 2. Upload Project Files

1.  **Open a Bash console:** Go to the "Consoles" tab and start a new "Bash" console.
2.  **Navigate to your web app directory:** Your web app will be located at `/home/your_username/your_domain.pythonanywhere.com/`. Use `cd` to navigate into this directory.
3.  **Upload files:** You can upload your project files in a few ways:
    *   **Using `git clone`:** If your project is in a Git repository, you can clone it directly into your web app directory:
        ```bash
        git clone <your_repository_url> .
        ```
        (The `.` at the end means clone into the current directory).
    *   **Manual upload:** Use the "Files" tab on PythonAnywhere to upload your `Trading_ai_system` folder and its contents. Ensure the structure matches the blueprint:
        ```
        /home/your_username/your_domain.pythonanywhere.com/
        ├── app.py
        ├── database.db
        ├── config.py
        ├── models/
        │   ├── model_a_core.py
        │   └── model_b_shadow.py
        ├── static/
        │   ├── css/style.css
        │   └── js/dashboard.js
        ├── templates/
        │   ├── user/dashboard.html
        │   └── admin/panel.html
        └── utils/
            ├── db_manager.py
            └── auth_helper.py
        ├── init_db.py
        ├── requirements.txt
        └── Deployment_Guide.md
        ```

## 3. Set up Virtual Environment and Install Dependencies

1.  **Create a virtual environment:** In your Bash console, navigate to your web app directory and run:
    ```bash
    python3.9 -m venv venv
    source venv/bin/activate
    ```
    (Replace `python3.9` with your chosen Python version if different).
2.  **Install dependencies:** With the virtual environment activated, install the required packages:
    ```bash
    pip install -r requirements.txt
    ```

## 4. Initialize the Database

1.  **Run `init_db.py`:** In your Bash console (with the virtual environment activated), execute the database initialization script:
    ```bash
    python init_db.py
    ```
    This will create the `database.db` file in your project root.

## 5. Configure the Web App

1.  **Go to the "Web" tab:** Click on your web app.
2.  **Virtualenv:** Under "Virtualenv", enter the path to your virtual environment (e.g., `/home/your_username/your_domain.pythonanywhere.com/venv/`).
3.  **WSGI configuration file:** Click on the link next to "WSGI configuration file". This will open a file named `wsgi.py`.
4.  **Edit `wsgi.py`:** Replace the existing content with the following:
    ```python
    import sys
    import os

    # Add your project directory to the sys.path
    project_home = u'/home/your_username/your_domain.pythonanywhere.com'
    if project_home not in sys.path:
        sys.path.insert(0, project_home)

    # Set environment variables (optional, but good practice for SECRET_KEY)
    os.environ["SECRET_KEY"] = "your_strong_secret_key_here"
    os.environ["ADMIN_PASSWORD"] = "your_admin_password_here"
    os.environ["GOOGLE_API_KEY"] = "your_google_ai_api_key_here"

    # Import your Flask app
    from app import app as application  # noqa
    ```
    **Important:**
    *   Replace `your_username` with your PythonAnywhere username.
    *   Replace `your_domain.pythonanywhere.com` with your actual web app domain.
    *   **Change `your_strong_secret_key_here` to a strong, unique secret key.**
    *   **Change `your_admin_password_here` to a strong password for your admin panel.**

## 6. Reload and Test

1.  **Reload the web app:** Go back to the "Web" tab and click the "Reload" button for your web app.
2.  **Visit your site:** Click the link to your web app (e.g., `your_domain.pythonanywhere.com`) to see your application live.
3.  **Access Admin Panel:** Navigate to `/admin-secure-portal` to access the admin panel.

## Troubleshooting

*   **Check server log:** If your app isn't working, check the "Error log" and "Server log" links on the "Web" tab for clues.
*   **Console errors:** Use the browser's developer console to check for frontend errors.
*   **PythonAnywhere forums:** The PythonAnywhere forums are a great resource for common deployment issues.

---

**Author:** Manus AI
**Date:** February 13, 2026
