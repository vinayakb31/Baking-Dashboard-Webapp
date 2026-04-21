# Bakelet Sales Dashboard

A web-based dashboard designed to provide comprehensive sales analytics by securely pulling data from a private Google Sheet. The application is built with Python (Flask) and deployed as a Docker container on Render. It features a responsive, dark-themed UI built with Tailwind CSS.

## Live Demo

https://baking-dashboard-webapp.onrender.com/
-----

## Features

  * **Secure Google Authentication**: Users log in via Google OAuth 2.0. Access is restricted to a predefined list of authorized email addresses. The login flow implements PKCE (Proof Key for Code Exchange) and strict cookie security for production environments.
  * **Responsive Design**: A clean, modern UI that works seamlessly on both desktop and mobile devices, featuring a hamburger menu for smaller screens.
  * **Multi-Tabbed Interface**: Data is organized into intuitive tabs for easy navigation:
      * **Monthwise**: View key sales metrics for a specific month, selectable via a dropdown.
      * **Total**: See all-time summary statistics, including total paid, due amounts, and sales for delivered orders. Features a Top 10 items pie chart and a Top 5 items sales summary.
      * **Customers**: A searchable list of all customers with their total orders and total amount spent.
      * **Items**: View statistics (total orders, total sales) for any individual item, selectable via a dropdown.
      * **Trends**: Visualize daily sales trends with a dynamic line chart. Filter data by presets like "This Month," "Last 3 Months," "Last 6 Months," and "All Time."
  * **Dynamic Chart Generation**: All charts (pie and line) are generated on the backend with Matplotlib, ensuring they always reflect the most current data.
  * **Manual Data Refresh**: A "Refresh" button allows users to manually clear the server-side cache and pull the latest data from the source Google Sheet.
  * **Optimized for Performance**: Utilizes server-side in-memory caching to ensure near-instantaneous response times after the initial data load. The cache automatically refreshes every 10 minutes.

-----

## Technology Stack

  * **Backend**: Python 3.13, Flask
  * **Data Analysis**: Pandas
  * **Chart Generation**: Matplotlib
  * **Frontend**: HTML, Tailwind CSS, Alpine.js
  * **Authentication**: Google OAuth 2.0 (via `google-auth-oauthlib`)
  * **Deployment**: Docker, Render
  * **WSGI Server**: Gunicorn

-----

## Setup and Local Development

Follow these steps to run the application on your local machine for development and testing.

### Prerequisites

  * Python 3.9+
  * A Google Cloud Platform project

### Steps

1.  **Clone the Repository**

    ```bash
    git clone [your-repository-url]
    cd [repository-name]
    ```

2.  **Set Up Google Cloud Project**

      * Go to the [Google Cloud Console](https://console.cloud.google.com/).
      * Enable the **Google Drive API**.
      * Go to **APIs & Services \> Credentials**.
      * Create an OAuth 2.0 Client ID. Select **Web application** as the type.
      * Under "Authorized redirect URIs", add:
          * `http://127.0.0.1:5000/callback`
          * `http://localhost:5000/callback` (for local testing)
          * `https://[your-render-app-name].onrender.com/callback` (for production)

3.  **Set Up Virtual Environment & Install Dependencies**

    ```bash
    # Create and activate a virtual environment
    python -m venv venv
    source venv/bin/activate

    # Install the required packages
    pip install -r requirements.txt
    ```

4.  **Configure Environment Variables**

    The application requires several environment variables to run locally. Set them in your terminal session:

    ```bash
    # Get these from your Google OAuth Client ID settings
    export GOOGLE_CLIENT_ID="YOUR_CLIENT_ID.apps.googleusercontent.com"
    export GOOGLE_CLIENT_SECRET="YOUR_CLIENT_SECRET"

    # Generate a strong random key for Flask sessions
    export FLASK_SECRET_KEY="your-own-strong-random-secret-key"

    # Required ONLY for local testing over HTTP with Google OAuth
    export OAUTHLIB_INSECURE_TRANSPORT=1
    ```

5.  **Run the Application**

    ```bash
    python main.py
    ```

    The application will be available at `http://127.0.0.1:5000`.

-----

## Deployment to Render

This application is containerized with a `Dockerfile` and configured for automatic deployment via Render.

### 1\. Create the Web Service

  * Log in to the [Render Dashboard](https://www.google.com/search?q=https://dashboard.render.com).
  * Click **New \> Web Service**.
  * Connect your GitHub repository containing this code.
  * Ensure the **Runtime** is set to `Docker`.

### 2\. Configure Environment Variables

Do not upload a `.env` file to your repository. Instead, navigate to the **Environment** tab in your Render Web Service dashboard and add the following keys:

  * `FLASK_SECRET_KEY`: Your 32-character secure hex string.
  * `GOOGLE_CLIENT_ID`: Your Google OAuth Client ID.
  * `GOOGLE_CLIENT_SECRET`: Your Google OAuth Client Secret.
  * `PORT`: `8080` (This matches the exposed port in the `Dockerfile`).

*Note: Ensure `OAUTHLIB_INSECURE_TRANSPORT` is strictly removed from the Render environment settings, as Render provides native HTTPS.*

### 3\. Deploy and Update OAuth

  * Click **Create Web Service** or **Save Changes** to trigger the build process. Render will automatically install Gunicorn and boot the application.
  * Once the service is live, copy your public Render URL.
  * Return to the **Google Cloud Console \> APIs & Services \> Credentials** and add your exact Render callback URL (e.g., `https://[your-render-app-name].onrender.com/callback`) to the **Authorized redirect URIs** list to enable production logins.

### 4\. Continuous Deployment

Render is configured to watch the `main` branch. Any new changes pushed to GitHub using `git push origin main` will automatically trigger a new Docker build and deployment.

-----

## License

This project is licensed under the MIT License. See the [LICENSE](https://www.google.com/search?q=LICENSE) file for details.
