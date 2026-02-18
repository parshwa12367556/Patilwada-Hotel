# HotelServe - Online Food Ordering System

A complete Flask-based web application for hotel in-room dining and food ordering. This system allows guests to browse menus, place orders, and request hotel services, while providing administrators with tools to manage the entire workflow, including a Kitchen Display System (KDS).

## Features

### 👤 Guest / User
*   **Digital Menu**: Browse food items by category (Breakfast, Main Course, etc.) with search functionality.
*   **Cart & Checkout**: Add items, add special instructions, and choose payment methods (Cash, Card, Room Charge).
*   **Order Tracking**: View order history and live status updates.
*   **Service Requests**: Request housekeeping, water refills, or manager assistance directly from the app.
*   **Coupons**: Apply discount codes for percentage or fixed-amount savings.

### 🛡️ Administrator
*   **Dashboard**: Visual analytics for sales, order counts, and recent activity.
*   **Food Management**: Add, edit, delete, and toggle availability of menu items.
*   **Order Management**: Update order statuses (Pending → Preparing → Delivered) and print receipts.
*   **Kitchen Display System (KDS)**: A dedicated auto-refreshing view for kitchen staff to track active orders.
*   **User Management**: Manage registered users and admin privileges.
*   **Coupon System**: Create and manage promotional codes.
*   **Reports**: Export sales data and newsletter subscribers to CSV.

## Tech Stack

*   **Backend**: Python, Flask
*   **Database**: SQLite (SQLAlchemy ORM)
*   **Frontend**: HTML5, Bootstrap 5, JavaScript (jQuery)
*   **Forms**: Flask-WTF

## Installation & Setup

1.  **Clone the repository**
    ```bash
    git clone <your-repo-url>
    cd "Online food system"
    ```

2.  **Create a Virtual Environment**
    ```bash
    # Windows
    python -m venv venv
    venv\Scripts\activate

    # Mac/Linux
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  **Install Dependencies**
    ```bash
    pip install flask flask-sqlalchemy flask-login flask-wtf email_validator werkzeug
    ```

4.  **Run the Application**
    ```bash
    python app.py
    ```
    The database will be created automatically on the first run.

5.  **Access the App**
    Open your browser and navigate to: `http://127.0.0.1:5000`

## Default Admin Credentials

When you run the app for the first time, a default admin account is created automatically:

*   **Email**: `admin@foodapp.com`
*   **Password**: `admin123`

## Project Structure

*   `app.py`: Main application logic and routes.
*   `models.py`: Database schema definitions.
*   `forms.py`: Form validation classes.
*   `config.py`: App configuration.
*   `templates/`: HTML files (Jinja2).
*   `static/`: CSS, JS, and uploaded images.
*   `instance/`: Contains the `food_system.db` database file.