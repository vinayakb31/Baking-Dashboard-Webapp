import os
import io
import uuid
import logging
import base64
import pandas as pd
import json
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.font_manager import findfont, FontProperties
from datetime import timedelta, datetime, date

from flask import Flask, render_template, request, session, redirect, url_for
from werkzeug.middleware.proxy_fix import ProxyFix
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

matplotlib.use("Agg")
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def load_authorized_users(filename="authorized_users.txt"):
    """Loads authorized user emails from a text file."""
    if not os.path.exists(filename):
        logging.warning(f"Authorization file '{filename}' not found. Creating a placeholder.")
        with open(filename, 'w') as f:
            f.write("# Add one authorized email per line\n")
        return []
    try:
        with open(filename, 'r') as f:
            # Read lines, strip whitespace, and ignore empty lines or comments
            users = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        logging.info(f"Loaded {len(users)} authorized users from '{filename}'.")
        return users
    except Exception as e:
        logging.error(f"Error reading authorization file '{filename}': {e}", exc_info=True)
        return []

# --- Flask App and Secret Key Initialization ---
try:
    app = Flask(__name__, template_folder='templates')
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)
    app.secret_key = os.environ.get("FLASK_SECRET_KEY")
    
    CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
    CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET")
    
    if not all([app.secret_key, CLIENT_ID, CLIENT_SECRET]):
        logging.critical("FATAL: Missing one or more required environment variables (FLASK_SECRET_KEY, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET).")
        raise ValueError("Missing required environment variables.")

    CLIENT_CONFIG = {
        "web": {
            "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["placeholder"]
        }
    }
    logging.info("Successfully loaded environment variables.")

except Exception as e:
    logging.critical("!!!!!!!!!! APPLICATION FAILED TO INITIALIZE !!!!!!!!!!")
    logging.critical(e, exc_info=True)
    raise

SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/drive.readonly"
]
# MODIFIED: Load authorized users from the new file
ALLOWED_USERS = load_authorized_users()
FILE_ID = "1tB8RDy8I8iQLn7WFfeNlauWcHlHr-Cy7"

data_cache = {
    'df': None, 'unique_months': None, 'all_items': None,
    'total_pie_chart': None, 'top_items': None, 'customer_data': None,
    'summary_stats': {}, 'last_updated': None
}
CACHE_TTL = timedelta(minutes=10)

def get_flow(state=None):
    redirect_uri = url_for("callback", _external=True)
    return Flow.from_client_config(
        CLIENT_CONFIG, scopes=SCOPES, state=state, redirect_uri=redirect_uri
    )

app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

def load_and_process_data():
    global data_cache
    now = datetime.utcnow()

    if data_cache['last_updated'] and (now - data_cache['last_updated'] < CACHE_TTL):
        logging.info("Serving data from fresh cache.")
        return data_cache['df'], None

    logging.info("Cache is stale or empty. Refreshing data from Google Drive...")
    try:
        credentials = Credentials.from_authorized_user_info(session['credentials'])
        drive_service = build("drive", "v3", credentials=credentials)
        request_file = drive_service.files().get_media(fileId=FILE_ID)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request_file)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        fh.seek(0)
        file_content = fh.read()

        try:
            df = pd.read_excel(io.BytesIO(file_content), sheet_name="Orders")
            summary_df = pd.read_excel(io.BytesIO(file_content), sheet_name="Orders", usecols="I", header=None, skiprows=1, nrows=6)
        except Exception as e:
            if "No sheet named 'Orders'" in str(e):
                 logging.warning("No sheet named 'Orders' found. Falling back to the first sheet.")
                 df = pd.read_excel(io.BytesIO(file_content))
                 summary_df = pd.read_excel(io.BytesIO(file_content), usecols="I", header=None, skiprows=1, nrows=6)
            else:
                raise e

        total_paid = summary_df.iloc[0, 0]
        pending_orders = summary_df.iloc[1, 0]
        total_delivered = summary_df.iloc[2, 0]
        total_sales_all_time = summary_df.iloc[3, 0]
        total_due = summary_df.iloc[4, 0]

        df['DATE'] = df['DATE'].ffill()
        df['DATE'] = pd.to_datetime(df['DATE'], errors='coerce')
        df.dropna(subset=['DATE'], inplace=True)
        df['AMOUNT'] = pd.to_numeric(df['AMOUNT'], errors='coerce').fillna(0)
        
        data_cache['df'] = df
        unique_months_dt = df['DATE'].dt.to_period('M').unique()
        sorted_months = sorted(unique_months_dt, reverse=True)
        data_cache['unique_months'] = [period.strftime('%B %Y') for period in sorted_months]
        data_cache['all_items'] = sorted(df['ITEM NAME'].dropna().unique())
        data_cache['summary_stats'] = {
            'total_paid': int(total_paid), 'total_due': int(total_due),
            'total_delivered': int(total_delivered), 'total_sales_all_time': int(total_sales_all_time),
            'pending_orders': int(pending_orders)
        }
        data_cache['total_pie_chart'] = create_pie_chart(df, "Item Share (All Time)", top_n=10)
        data_cache['top_items'] = get_top_items(df).to_dict(orient="records")
        
        # --- Load Customer Data ---
        # Tries to load from a dedicated "Customers" sheet first.
        # If it fails (e.g., sheet not found, columns are wrong), it falls back
        # to calculating the data from the "Orders" sheet for robustness.
        try:
            logging.info("Attempting to load data from 'Customers' sheet.")
            customers_fh = io.BytesIO(file_content)
            customer_df = pd.read_excel(customers_fh, sheet_name="Customers")
            
            # Validate that the required columns exist
            if 'ORDERED BY' not in customer_df.columns or 'TOTAL AMOUNT' not in customer_df.columns:
                 raise ValueError("The 'Customers' sheet must contain 'ORDERED BY' and 'TOTAL AMOUNT' columns.")

            # Select, rename, and process the columns to match the frontend's needs
            customer_df = customer_df[['ORDERED BY', 'TOTAL AMOUNT']].copy()
            customer_df.rename(columns={'TOTAL AMOUNT': 'TotalSpent'}, inplace=True)
            customer_df['TotalSpent'] = pd.to_numeric(customer_df['TotalSpent'], errors='coerce').fillna(0)
            customer_df.sort_values(by='TotalSpent', ascending=False, inplace=True)

            data_cache['customer_data'] = customer_df.to_dict(orient="records")
            logging.info("Successfully loaded customer data from 'Customers' sheet.")
        except Exception as e:
            logging.warning(f"Could not load from 'Customers' sheet: {e}. Falling back to calculating from 'Orders' sheet.")
            # Fallback to the original method if the 'Customers' sheet isn't available
            data_cache['customer_data'] = get_customer_data(df).to_dict(orient="records")
        data_cache['last_updated'] = now
        
        logging.info("Cache successfully refreshed.")
        return df, None
        
    except HttpError as error:
        if error.resp.status == 401 or 'invalid_grant' in str(error):
            logging.warning(f"Authentication error encountered (Status: {error.resp.status}). Forcing re-login.")
            return None, "re-login"
        return None, f"Drive Error: {error}"
    except Exception as e:
        logging.error(f"An error occurred during data processing: {e}", exc_info=True)
        return None, f"Error processing file: {e}"

def get_customer_data(df):
    if df is None: return pd.DataFrame()
    return df.groupby('ORDERED BY').agg(
        TotalOrders=('ORDERED BY', 'count'), TotalSpent=('AMOUNT', 'sum')
    ).sort_values(by='TotalSpent', ascending=False).reset_index()

def get_top_items(df):
    if df is None: return pd.DataFrame()
    item_summary = df.groupby('ITEM NAME').agg(
        count=('ITEM NAME', 'count'), TotalSales=('AMOUNT', 'sum')
    )
    return item_summary.nlargest(10, 'TotalSales').reset_index()

def get_extended_item_stats(df, selected_item):
    if df is None or selected_item is None:
        return {'order_count': 0, 'total_sales': 0, 'top_customers': [], 'recent_orders': []}
    
    item_df = df[df['ITEM NAME'] == selected_item].copy()
    if item_df.empty:
        return {'order_count': 0, 'total_sales': 0, 'top_customers': [], 'recent_orders': []}

    item_df['DATE_str'] = item_df['DATE'].dt.strftime('%d %b %Y')

    top_customers = item_df.groupby('ORDERED BY')['AMOUNT'].sum().nlargest(5).reset_index()
    recent_orders = item_df.nlargest(5, 'DATE')[['DATE_str', 'ORDERED BY', 'AMOUNT']]
    
    return {
        'order_count': len(item_df),
        'total_sales': item_df['AMOUNT'].sum(),
        'top_customers': top_customers.to_dict(orient='records'),
        'recent_orders': recent_orders.rename(columns={'DATE_str': 'DATE'}).to_dict(orient='records')
    }

def create_pie_chart(data, title, top_n=5):
    font_name = "Inter"
    try: findfont(FontProperties(family=font_name))
    except ValueError: font_name = None

    fig, ax = plt.subplots(figsize=(10, 7), dpi=100)
    bg_color = "#1a1a1a"; text_color = "#f9fafb"
    fig.patch.set_facecolor(bg_color); ax.set_facecolor(bg_color)

    if data.empty or data['ITEM NAME'].isnull().all() or data['AMOUNT'].sum() == 0:
        ax.text(0.5, 0.5, 'No sales data', ha='center', va='center', color=text_color, fontsize=14)
    else:
        item_sales = data.groupby('ITEM NAME')['AMOUNT'].sum().sort_values(ascending=False)
        chart_data = item_sales.head(top_n)
        if len(item_sales) > top_n:
            others_sum = item_sales.iloc[top_n:].sum()
            if others_sum > 0:
                others = pd.Series([others_sum], index=['Others'])
                chart_data = pd.concat([chart_data, others])
        
        chart_data = chart_data[chart_data > 0]
        if chart_data.empty:
            ax.text(0.5, 0.5, 'No sales data', ha='center', va='center', color=text_color, fontsize=14)
        else:
            wedges, _ = ax.pie(chart_data, startangle=140, wedgeprops=dict(width=0.4, edgecolor=bg_color))
            total_sales = chart_data.sum()
            labels = [f"{name} ({sales/total_sales:.1%})" for name, sales in chart_data.items()]
            legend_title = f"Top {top_n} Items by Sales"
            legend = ax.legend(wedges, labels, title=legend_title, loc="center left", bbox_to_anchor=(1, 0.5),
                               prop={'family': font_name, 'size': 14}, labelcolor=text_color, frameon=True)
            frame = legend.get_frame(); frame.set_facecolor('#1a1a1a'); frame.set_edgecolor('none')
            plt.setp(legend.get_title(), color=text_color, weight='bold', family=font_name, size=16)

    ax.set_title(title, color=text_color, fontfamily=font_name, fontsize=18, weight='bold')
    fig.tight_layout(rect=[0, 0, 0.75, 1])
    buf = io.BytesIO(); plt.savefig(buf, format='png', transparent=True); plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode('utf-8')

def create_sales_trend_chart(df, start_date, end_date):
    mask = (df['DATE'] >= start_date) & (df['DATE'] <= end_date)
    filtered_df = df.loc[mask]
    daily_sales = filtered_df.groupby(filtered_df['DATE'].dt.date)['AMOUNT'].sum()
    
    fig, ax = plt.subplots(figsize=(12, 6), dpi=100)
    bg_color = "#1a1a1a"; text_color = "#f9fafb"
    fig.patch.set_facecolor(bg_color); ax.set_facecolor(bg_color)
    
    ax.plot(daily_sales.index, daily_sales.values, marker='o', linestyle='-', color='#e5e7eb')
    
    ax.set_title('Daily Sales Trend', color=text_color, fontsize=18, weight='bold')
    ax.set_ylabel('Total Sales (₹)', color=text_color, fontsize=12)
    ax.tick_params(axis='x', colors=text_color, rotation=45); ax.tick_params(axis='y', colors=text_color)
    ax.grid(color='#374151', linestyle='--', linewidth=0.5)
    
    plt.gca().spines['top'].set_visible(False); plt.gca().spines['right'].set_visible(False)
    plt.gca().spines['left'].set_color(text_color); plt.gca().spines['bottom'].set_color(text_color)
    
    fig.tight_layout()
    buf = io.BytesIO(); plt.savefig(buf, format='png', transparent=True); plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode('utf-8')

@app.route("/")
def index():
    if "credentials" in session: return redirect(url_for("dashboard"))
    return render_template("index.html")

@app.route("/login")
def login():
    state = str(uuid.uuid4()); flow = get_flow(state=state)
    auth_url, _ = flow.authorization_url(access_type='offline', prompt='consent'); session["state"] = state
    return redirect(auth_url)

@app.route("/callback")
def callback():
    if 'state' not in session:
        logging.warning("Session state missing in callback. Redirecting to home.")
        return redirect(url_for('index'))
    
    flow = get_flow(state=session["state"])
    flow.fetch_token(authorization_response=request.url)
    credentials = flow.credentials
    request_adapter = google_requests.Request()
    idinfo = id_token.verify_oauth2_token(credentials.id_token, request_adapter, CLIENT_ID)
    user_email = idinfo.get("email")
    if user_email not in ALLOWED_USERS:
        session.clear()
        return render_template("unauthorized.html", email=user_email), 403
    
    session['credentials'] = json.loads(credentials.to_json())
    session["user_email"] = user_email; session.permanent = True
    return redirect(url_for("dashboard"))

@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    if "credentials" not in session: return redirect(url_for("index"))

    df_sales_data, error = load_and_process_data()
    
    if error == "re-login": 
        session.clear()
        return redirect(url_for("login"))
    if error: return f"<h1>Error</h1><p>{error}</p>"
        
    active_tab = request.form.get('active_tab', 'monthwise')

    # --- Monthwise Tab Data ---
    selected_month = request.form.get("month_selector", data_cache['unique_months'][0] if data_cache['unique_months'] else "")
    filtered_df = df_sales_data[df_sales_data["DATE"].dt.strftime("%B %Y") == selected_month]
    total_orders_month = filtered_df["ORDERED BY"].count()
    total_sales_month = filtered_df["AMOUNT"].sum()
    
    if not filtered_df.empty and filtered_df['AMOUNT'].sum() > 0:
        most_ordered_item = filtered_df.groupby('ITEM NAME')['AMOUNT'].sum().idxmax()
    else: most_ordered_item = "N/A"
        
    monthly_pie_chart = create_pie_chart(filtered_df, "Item Share This Month", top_n=5)
    
    # --- Items Tab Data ---
    default_item = data_cache['all_items'][0] if data_cache['all_items'] else None
    selected_item = request.form.get("item_selector", default_item)
    item_stats = get_extended_item_stats(df_sales_data, selected_item)

    # --- Trends Tab Data Logic ---
    today = date.today()
    date_range_preset = request.form.get('date_range_preset', 'this_month')
    
    def subtract_months(sourcedate, months):
        month = sourcedate.month - 1 - months
        year = sourcedate.year + month // 12
        month = month % 12 + 1
        return date(year, month, 1)

    if date_range_preset == 'this_month':
        start_date = today.replace(day=1)
        end_date = today
    elif date_range_preset == 'last_3_months':
        start_date = subtract_months(today, 2)
        end_date = today
    elif date_range_preset == 'last_6_months':
        start_date = subtract_months(today, 5)
        end_date = today
    elif date_range_preset == 'all_time':
        start_date = df_sales_data['DATE'].min()
        end_date = df_sales_data['DATE'].max()
    else:
        start_date = today.replace(day=1)
        end_date = today

    sales_trend_chart = create_sales_trend_chart(df_sales_data, pd.to_datetime(start_date), pd.to_datetime(end_date))

    print("--- DEBUG START ---")
    print("Type of customer_data:", type(data_cache['customer_data']))
    print("Value of customer_data:", data_cache['customer_data'])
    print("--- DEBUG END ---")

    return render_template(
        "index.html", active_tab=active_tab,
        unique_months=data_cache['unique_months'], selected_month=selected_month,
        total_orders_month=total_orders_month, total_sales_month=f"₹{total_sales_month:,.0f}",
        most_ordered_item=most_ordered_item, monthly_pie_chart=monthly_pie_chart,
        summary_stats=data_cache['summary_stats'], total_pie_chart=data_cache['total_pie_chart'],
        customer_data_json=json.dumps(data_cache['customer_data']), top_items=data_cache['top_items'],
        all_items=data_cache['all_items'], selected_item=selected_item, item_stats=item_stats,
        sales_trend_chart=sales_trend_chart, date_range_preset=date_range_preset,
        start_date=start_date.strftime('%Y-%m-%d'), end_date=end_date.strftime('%Y-%m-%d')
    )

@app.route("/refresh")
def refresh():
    if "credentials" not in session: return redirect(url_for("index"))
    global data_cache
    data_cache['last_updated'] = None
    logging.info("Cache manually invalidated. Data will be refreshed on next load.")
    return redirect(url_for("dashboard"))

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=True)