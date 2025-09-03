# Baking Sales Dashboard

A web-based dashboard designed to provide comprehensive sales analytics by securely pulling data from a private Google Sheet. The application is built with Python (Flask) and deployed as a container on Google Cloud Run. It features a responsive, dark-themed UI built with Tailwind CSS.

## Live Demo

[\[Link to your deployed Cloud Run service]](https://baking-dashboard-197494690319.asia-south1.run.app/login)

---

## Features

* **Secure Google Authentication**: Users log in via Google OAuth 2.0. Access is restricted to a predefined list of authorized email addresses.
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

---

## Technology Stack

* **Backend**: Python 3, Flask
* **Data Analysis**: Pandas
* **Chart Generation**: Matplotlib
* **Frontend**: HTML, Tailwind CSS, Alpine.js
* **Authentication**: Google OAuth 2.0 (via `google-auth-oauthlib`)
* **Deployment**: Docker, Google Cloud Run, Google Secret Manager
* **WSGI Server**: Gunicorn

---

## Setup and Local Development

Follow these steps to run the application on your local machine for development and testing.

### Prerequisites

* Python 3.9+
* A Google Cloud Platform project

### Steps

1. **Clone the Repository**

   ```bash
   git clone [your-repository-url]
   cd [repository-name]
   ```

2. **Set Up Google Cloud Project**

   * Go to the [Google Cloud Console](https://console.cloud.google.com/).
   * Enable the **Google Drive API**.
   * Go to **APIs & Services > Credentials**.
   * Create an OAuth 2.0 Client ID. Select **Web application** as the type.
   * Under "Authorized redirect URIs," add:

     * `http://127.0.0.1:5000/callback`
     * `http://localhost:5000/callback` (for local testing)

3. **Set Up Virtual Environment & Install Dependencies**

   ```bash
   # Create and activate a virtual environment
   python -m venv venv
   source venv/bin/activate

   # Install the required packages
   pip install -r requirements.txt
   ```

4. **Configure Environment Variables**

   The application requires several environment variables to run. Set them in your terminal session:

   ```bash
   # Get these from your Google OAuth Client ID settings
   export GOOGLE_CLIENT_ID="YOUR_CLIENT_ID.apps.googleusercontent.com"
   export GOOGLE_CLIENT_SECRET="YOUR_CLIENT_SECRET"

   # Generate a strong random key for Flask sessions
   export FLASK_SECRET_KEY="your-own-strong-random-secret-key"

   # Required for local testing over HTTP with Google OAuth
   export OAUTHLIB_INSECURE_TRANSPORT=1
   ```

5. **Run the Application**

   ```bash
   python cookies_webapp.py
   ```

   The application will be available at `http://127.0.0.1:5000`.

---

## Deployment to Google Cloud Run

This application is designed to be deployed as a container on Google Cloud Run.

### 1. Set Up Secret Manager

For security, all secrets are managed in Google Secret Manager and are not stored in the code.

* Go to the **Secret Manager** page in your Google Cloud Console.
* Create the following three secrets with their corresponding values:

  * `GOOGLE_CLIENT_ID`
  * `GOOGLE_CLIENT_SECRET`
  * `flask-secret-key`

### 2. Grant Permissions

Ensure your Cloud Run service account (or the Compute Engine default service account) has the **Secret Manager Secret Accessor** role in IAM.

### 3. Deploy to Cloud Run

Run the following command from your project's root directory. This will build the container, push it to the Artifact Registry, and deploy it to Cloud Run, securely connecting the secrets as environment variables:

```bash
gcloud run deploy baking-dashboard \
  --source . \
  --region [YOUR_PREFERRED_REGION] \
  --allow-unauthenticated \
  --set-secrets="GOOGLE_CLIENT_ID=GOOGLE_CLIENT_ID:latest,GOOGLE_CLIENT_SECRET=GOOGLE_CLIENT_SECRET:latest,FLASK_SECRET_KEY=flask-secret-key:latest"
```

Remember to add your deployed application's URL to the "Authorized redirect URIs" in your Google OAuth settings.

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## Acknowledgments

* [Flask](https://flask.palletsprojects.com/)
* [Google Cloud](https://cloud.google.com/)
* [Tailwind CSS](https://tailwindcss.com/)
* [Matplotlib](https://matplotlib.org/)
* [Google OAuth 2.0](https://developers.google.com/identity/protocols/oauth2)
