import streamlit as st
import sqlite3
import hashlib
from PIL import Image
import google.generativeai as genai
import pandas as pd
import pdf2image
import io

# --- Password hashing ---
def make_hashes(password):
    return hashlib.sha256(password.encode()).hexdigest()

def check_hashes(password, hashed_text):
    return make_hashes(password) == hashed_text

# --- DB Connection and Initialization ---
def connect_db():
    return sqlite3.connect("users_db.sqlite")

def init_db():
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

def add_user(username, password):
    conn = connect_db()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, make_hashes(password)))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def login_user(username, password):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username=? AND password=?", (username, make_hashes(password)))
    data = cursor.fetchone()
    conn.close()
    return data

# --- Initialize DB ---
init_db()

# --- Initialize session state safely ---
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
if "username" not in st.session_state:
    st.session_state["username"] = ""
if "table_data" not in st.session_state:
    st.session_state["table_data"] = None

# --- Google Generative AI Setup ---
GOOGLE_API_KEY = "AIzaSyB05Y2KOJo5JUf5Y46B6aB94dGksVdXj0c"  # Replace with secure storage in production
genai.configure(api_key=GOOGLE_API_KEY)
prompt = """You are an expert in quantity surveying from structural drawings. 
From the given structural drawings, identify elements like beams, columns, slabs, sunken slabs, plinth beams, staircases, and their measurements in a table format. 
If no elements are present, don't include them in the table. Provide the output as a markdown table with columns: Element, Length (m), Width (m), Height/Depth (m), Quantity, Notes."""

# --- Function to convert PDF to image ---
def pdf_to_image(pdf_file):
    images = pdf2image.convert_from_bytes(pdf_file.read())
    return images[0].convert("RGB") # Return the first page as a PIL image

# --- Function to process image and get table ---
# def analyze_drawing(image):
#     try:
#         model = genai.GenerativeModel('gemini-1.5-flash')
#         response = model.generate_content([prompt, image])
#         if response.text:
#             # Parse markdown table to DataFrame
#             lines = response.text.strip().split('\n')
#             if lines and lines[0].startswith('|'):
#                 headers = [h.strip() for h in lines[0].split('|')[1:-1]]  # Skip first and last empty elements
#                 data = []
#                 for line in lines[2:]:  # Skip header and separator
#                     if line.strip().startswith('|'):
#                         row = [cell.strip() for cell in line.split('|')[1:-1]]
#                         data.append(row)
#                 df = pd.DataFrame(data, columns=headers)
#                 return df
#         return None
#     except Exception as e:
#         st.error(f"Error analyzing drawing: {str(e)}")
#         return None

def analyze_drawing(image):
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        # Ensure image is in RGB format
        if not image.mode == "RGB":
            image = image.convert("RGB")
        
        response = model.generate_content([prompt, image])
        
        if response.text:
            # Try to parse markdown table from response
            lines = response.text.strip().split('\n')
            table_lines = [line for line in lines if line.startswith("|")]

            if len(table_lines) >= 2:
                headers = [col.strip() for col in table_lines[0].split('|')[1:-1]]
                data = [
                    [cell.strip() for cell in row.split('|')[1:-1]]
                    for row in table_lines[2:] if row.strip()
                ]
                df = pd.DataFrame(data, columns=headers)
                return df

            else:
                st.warning("Model responded but no markdown table was found.")
        else:
            st.warning("Model did not return any text.")
        return None
    except Exception as e:
        st.error(f"Error analyzing drawing: {str(e)}")
        return None


# --- If user is logged in, show the main app ---
if st.session_state["logged_in"]:
    st.sidebar.markdown("### 🛠️ Quantity Surveying Guide")
    st.sidebar.markdown("""
    **Step-by-Step Guide**
    
    1. Go to the **'Upload Drawings'** page and upload your structural drawings in PDF, JPG, JPEG, or PNG format.
    2. If the measurements are inaccurate, edit the table directly to correct them.
    3. Add prices for materials like steel, cement, etc., in the editable pricing column.
    4. Click the **'Calculate'** button to generate the final quantity surveying table.
    5. Use the **'Print'** button to save the results as a PDF.
    """)
    
    # File uploader for drawings
    uploaded_file = st.sidebar.file_uploader("📤 Upload Structural Drawing", type=["pdf", "jpg", "jpeg", "png"])
    
    st.markdown("## ✅ You're now logged in!")
    st.markdown(f"Welcome, **{st.session_state['username']}** 🎉")
    st.markdown("---")

    # Process uploaded file
    if uploaded_file:
        st.info("Processing uploaded drawing...")
        try:
            # Handle different file types
            if uploaded_file.type == "application/pdf":
                image = pdf_to_image(uploaded_file)
            else:  # Image files (JPG, JPEG, PNG)
                image = Image.open(uploaded_file)
            
            # Display uploaded image (Updated to use_container_width)
            st.image(image, caption="Uploaded Drawing", use_container_width=True)
            
            # Analyze drawing
            df = analyze_drawing(image)
            if df is not None and not df.empty:
                st.session_state["table_data"] = df
            else:
                st.warning("No structural elements detected in the drawing or analysis failed.")
        
        except Exception as e:
            st.error(f"Error processing file: {str(e)}")

    # Display and edit table if available
    if st.session_state["table_data"] is not None:
        st.markdown("### 📊 Quantity Surveying Table")
        # Allow editing of the table
        edited_df = st.data_editor(
            st.session_state["table_data"],
            num_rows="dynamic",  # Allow adding/removing rows
            column_config={
                "Element": st.column_config.TextColumn("Element"),
                "Length (m)": st.column_config.NumberColumn("Length (m)", min_value=0.0, format="%.2f"),
                "Width (m)": st.column_config.NumberColumn("Width (m)", min_value=0.0, format="%.2f"),
                "Height/Depth (m)": st.column_config.NumberColumn("Height/Depth (m)", min_value=0.0, format="%.2f"),
                "Quantity": st.column_config.NumberColumn("Quantity", min_value=0, format="%d"),
                "Notes": st.column_config.TextColumn("Notes"),
            },
            use_container_width=True
        )
        st.session_state["table_data"] = edited_df  # Update session state with edited data

        # Placeholder for Calculate and Print buttons
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Calculate"):
                st.success("Calculation logic to be implemented.")
                # Add your calculation logic here (e.g., material costs)
        with col2:
            if st.button("Print"):
                st.info("Print functionality to be implemented.")
                # Add PDF export logic here

# --- Else, show login/sign-up page ---
else:
    tab1, tab2 = st.tabs(["Login", "Sign Up"])

    with tab1:
        username = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_pass")
        remember = st.checkbox("I accept the terms and conditions", key="login_terms")

        if st.button("Login"):
            if username and password and remember:
                user = login_user(username, password)
                if user:
                    st.session_state["logged_in"] = True
                    st.session_state["username"] = username
                    st.success(f"Welcome back, {username}!")
                    st.rerun()  # Forces UI refresh to show main app
                else:
                    st.error("Incorrect credentials.")
            else:
                st.warning("Please complete all fields.")

    with tab2:
        new_username = st.text_input("Email", key="signup_email")
        new_password = st.text_input("Password", type="password", key="signup_pass")
        confirm = st.text_input("Confirm Password", type="password", key="signup_confirm")

        if st.button("Sign Up"):
            if new_username and new_password == confirm:
                if add_user(new_username, new_password):
                    st.success("Account created successfully! Please login.")
                else:
                    st.error("Username already exists.")
            else:
                st.warning("Passwords do not match or field is empty.")