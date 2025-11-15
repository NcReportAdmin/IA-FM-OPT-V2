import streamlit as st
import pandas as pd
from datetime import date,datetime
import gspread
from gspread_dataframe import get_as_dataframe
from oauth2client.service_account import ServiceAccountCredentials
import pytz
import time

# ----------------- PAGE CONFIG -----------------
st.set_page_config(page_title="Intake App", layout="centered")

# ----------------- GOOGLE SHEETS AUTH -----------------
# Connect to Google Sheets using Service Account credentials
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("nc-ia-automation-1745dc341430.json", scope)
client = gspread.authorize(creds)

# ----------------- HELPER FUNCTIONS -----------------
@st.cache_data
def load_permissions():
    """Load permissions from Google Sheet and return as DataFrame."""
    sheet = client.open_by_key("1pTHjR8V1VLxgZKGU-4Ym9_MvkB63OGblstzskE9jrwM").sheet1
    data = sheet.get_all_records()
    return pd.DataFrame(data)

#permissions sheet location : https://docs.google.com/spreadsheets/d/1pTHjR8V1VLxgZKGU-4Ym9_MvkB63OGblstzskE9jrwM

def safe_date(value):
    """Convert value to datetime.date if valid, else return None."""
    if value in [None, "", "NaT"] or pd.isna(value):
        return None
    try:
        return pd.to_datetime(value).date()
    except Exception:
        return None

# ----------------- LOGIN FUNCTION -----------------
def login():
    """Login page flow, verifies email and sets session variables."""
    if "user_email" not in st.session_state:
        st.title("🔐 Intake App Login")

        if 'today_date' not in st.session_state:
            st.session_state['today_date'] = date.today()

        email = st.text_input("Enter your email address to continue:").strip().lower()

        if email:
            permissions = load_permissions()
            match = permissions[permissions['email'].str.lower() == email]

            if match.empty:
                st.error("Access denied. Email not recognized.")
            else:
                role = match.iloc[0]["role"]
                st.session_state["user_email"] = email
                st.session_state["user_role"] = role
                st.session_state["logged_in"] = True   # ✅ Mark user as logged in
                st.success(f"Access granted: {role.capitalize()}")
                st.rerun()
        st.stop()  # stop execution until login is successful

# ----------------- APP 1: Pending Triage -----------------
def show_pending_triage_app():
    """Displays Pending Triage form, allows filtering, viewing, and editing records."""

    # ---------------- Session Info ----------------
    user_email = st.session_state['user_email']
    user_role = st.session_state['user_role']
    
    # Timezone San Francisco time (PT)
    pacific = pytz.timezone("America/Los_Angeles")
    st.session_state['today_date'] = datetime.now(pacific)
    today_date = st.session_state['today_date']

    if user_role in ["FM", "Admin","Editor"]:
        
        # ---------------- Page Title ----------------
        st.markdown("<h1 style='text-align: center;'>📋 FM-Pending Records</h1>", unsafe_allow_html=True)
        st.markdown("---")

        # ---------------- Load Google Sheet Data ----------------
        SHEET_ID = "1HmlKs_uiTrgIy5IHdQYzMXRR7E-88S9HyG85QQa-qLo"
        SHEET_NAME = "Pending Triage"
        sheet = client.open_by_key(SHEET_ID).worksheet(SHEET_NAME)
        df = get_as_dataframe(sheet, evaluate_formulas=True).fillna('')
        df['RowNumber'] = df.index + 2  # Adjust for header row in sheet

        #Test Google Sheet       : https://docs.google.com/spreadsheets/d/1Az-mjNTMGACi4EPgAwfbir3AJkFl6-EWsP0g0OMdX7I
        #Prodcution google Sheet : https://docs.google.com/spreadsheets/d/1HmlKs_uiTrgIy5IHdQYzMXRR7E-88S9HyG85QQa-qLo

        # ---------------- Filters ----------------
        name_email_filter = st.text_input("Search by Email or Name").strip().lower()
        status_filter = st.selectbox(
            "Select status to show:",
            ('All', 'JM-Pending', 'PB-Pending', 'HB-Pending', 'JM-Hold'),
            index=0
        )

        # Apply filters to DataFrame
        filtered_df = df.copy()
        if name_email_filter:
            filtered_df = filtered_df[
                filtered_df['Email Address'].str.lower().str.contains(name_email_filter, na=False) |
                filtered_df['Name (Last, First)'].str.lower().str.contains(name_email_filter, na=False)
            ]

        if status_filter != "All":
            # if user_role not in ["Admin", "Editor","Functional Manager"]:
            #     st.error("❗ Status filter is restricted to Admin/Editor.")
            #     st.stop()
            filtered_df = filtered_df[
                filtered_df["Accepted?\n(y, maybe, n, \"\")"].astype(str).str.lower() == status_filter.lower()
            ]

        if filtered_df.empty:
            st.warning("⚠️ No matching records found.")
            st.stop()

        # ---------------- Record Navigation ----------------
        if "record_pos" not in st.session_state:
            st.session_state.record_pos = 0

        if st.session_state.record_pos >= len(filtered_df):
            st.session_state.record_pos = 0

        default_record_index = filtered_df.index[st.session_state.record_pos]
        record_index = st.selectbox(
            "Choose a record to view/edit:",
            filtered_df.index,
            index=list(filtered_df.index).index(default_record_index),
            format_func=lambda x: f"{filtered_df.loc[x, 'Name (Last, First)']} ({filtered_df.loc[x, 'Email Address']})"
        )
        st.session_state.record_pos = list(filtered_df.index).index(record_index)
        record = filtered_df.loc[record_index]
        row_number = int(record["RowNumber"])

        # ---------------- Record Summary ----------------
        st.subheader("📄 Summary (Read Only)")
        summary_fields = [
            ("Name", "Name (Last, First)"),
            ("Email", "Email Address"),
            ("Phone", "Phone"),
            ("Location", "Geographic Location"),
            ("LinkedIn", "Linkedin link"),
            ("Resume", "Resume or CV or Bio"),
            ("Occupation", "Current Occupation"),
            ("Brief bio", "1. Brief Bio\nPlease share some information about yourself. We’re particularly interested in your experiences, areas of expertise, sources of inspiration, and the aspects you’re eager to develop further."),
            ("Profession Background", "2. Professional Background"),
            ("Nature Counter Functions", "3. Nature Counter Functions\nNature Counter teams are organized by function. Please select up to three functions that interest you the most."),
            ("Interests related to Nature Dosage and Health Benefits", "4. Interests\nPlease select your interests related to Nature Dosage and Health Benefits (select all that apply):"),
            ("Project Experience", "5. Project Experience\nDescribe a previous project where you contributed to a mobile app development. What was your role and what were the outcomes?"),
            ("Motivation", "6. Motivation\n\nWhat motivates you to join the \"Enhancing Nature Counter App\" project?"),
            ("Expectation", "7. Expectation\n\nWhat are your expectations from this project?"),
            ("Availability & Commitment", "8. Availability & Commitment\n\nWhat is your availability and estimated hours per week? How long do you plan to stay with us?  "),
            ("Date Received", "Date Received (formula from A)"),
            ("Accepted Status", "Accepted?\n(y, maybe, n, \"\")"),
        ]
        table_md = "| Field | Value |\n|-------|-------|\n"
        for label, col in summary_fields:
            value = str(record.get(col, "")).replace("\n", "<br>")
            table_md += f"| **{label}** | {value} |\n"
        st.markdown(table_md, unsafe_allow_html=True)

        # ---------------- Editable Fields ----------------
        st.subheader("📄 Edit Section")
        if user_role in ["Editor", "Admin", "FM"]:
            current_status = str(record["Accepted?\n(y, maybe, n, \"\")"]).strip().lower()
            comments_default = "" if pd.isna(record["Comments (prior career)"]) else record["Comments (prior career)"]
            accepted_default = current_status if current_status in ["y", "maybe", "n", ""] else ""

            # Select box and comments text area
            accepted = st.selectbox(
                "Update Accepted Status?",
                ["", "y", "maybe", "n"],
                index=["", "y", "maybe", "n"].index(accepted_default) if accepted_default in ["y", "maybe", "n"] else 0,
                key=f"accepted_{row_number}"
            )
            comments = st.text_area("Comments (prior career)", value=comments_default, key=f"comments_{row_number}")

            # ---------------- Action Buttons ----------------
            col1, col2, col3 = st.columns(3)
            if current_status not in ('y','n'):
                with col2:
                    if st.button("💾 Submit Update"):
                        try:
                            # Update sheet with comments and accepted status
                            sheet.update(f"R{row_number}", [[comments]])
                            if accepted.lower() in ("y", "n", "maybe"):
                                sheet.update(f"S{row_number}", [[accepted]])
                            # Track approvals by date and user
                            if accepted == "y":
                                sheet.update(f"U{row_number}", [[today_date.strftime("%Y-%m-%d")]])
                                sheet.update(f"T{row_number}", [[user_email]])
                            elif accepted == "n":
                                sheet.update(f"W{row_number}", [[today_date.strftime("%Y-%m-%d")]])
                                sheet.update(f"X{row_number}", [[user_email]])
                            elif accepted == "maybe":
                                sheet.update(f"T{row_number}", [[user_email]])
                                sheet.update(f"U{row_number}", [[today_date.strftime("%Y-%m-%d")]])

                            st.success("✅ Changes saved successfully and moved to Next Person")
                            st.session_state.record_pos += 1
                            st.rerun()

                        except Exception as e:
                            st.error(f"Failed to save changes: {e}")

            with col1:
                if st.button("⬅️ Previous Record", disabled=st.session_state.record_pos <= 0):
                    st.session_state.record_pos -= 1
                    st.rerun()

            with col3:
                if st.button("➡️ Next Record", disabled=st.session_state.record_pos >= len(filtered_df) - 1):
                    st.session_state.record_pos += 1
                    st.rerun()
        else:
            st.info("You have read-only access to this data.")
    else:
        st.info("You don't have access to this APP")

# ----------------- APP 2: OPT SVC -----------------
def show_opt_svc_app():
    """Displays OPT SVC form with record summary and editable fields side by side."""
    #user_email = st.session_state['user_email']
    user_role = st.session_state['user_role']
    
    # #Timezone San Francisco time (PT)
    # pacific = pytz.timezone("America/Los_Angeles")
    # st.session_state['today_date'] = datetime.now(pacific)
    # today_date = st.session_state['today_date']

    if user_role in ["HRS", "Admin","Editor","Viewer","FM"]:

        st.markdown("<h1 style='text-align: center;'>📋 OPT SVC Form</h1>", unsafe_allow_html=True)
        st.markdown("---")

        # Load OPT SVC sheet data
        SHEET_ID = "1wY9N1GlQ_-elkH2kdufOE1jWE6-_bVZNaCvlDuKziBk"
        SHEET_NAME = "Form Responses-2025"
        sheet = client.open_by_key(SHEET_ID).worksheet(SHEET_NAME)
        df = get_as_dataframe(sheet, evaluate_formulas=True, header=2).fillna('')
        df['RowNumber'] = df.index + 4  # first data row is 4 in the Sheet

        #Test Google Sheet       : https://docs.google.com/spreadsheets/d/1mqSramm8OgbdEXDET-kSre1q10ruTpH2DFRlvc4UeWw
        #Prodcution google Sheet : https://docs.google.com/spreadsheets/d/1wY9N1GlQ_-elkH2kdufOE1jWE6-_bVZNaCvlDuKziBk

        # ---------------- Filters ----------------
        name_email_filter = st.text_input("Search by Email Address or Name").strip().lower()
        filtered_df = df.copy()
        if name_email_filter:
            filtered_df = filtered_df[
                filtered_df['Email Address'].str.lower().str.contains(name_email_filter, na=False) |
                filtered_df['Name (Last, First)'].str.lower().str.contains(name_email_filter, na=False)
            ]

        if filtered_df.empty:
            st.warning("⚠️ No matching records found.")
            st.stop()
        st.markdown("---")

        # ---------------- Record Navigation ----------------
        if "record_pos" not in st.session_state:
            st.session_state.record_pos = 0
        if st.session_state.record_pos >= len(filtered_df):
            st.session_state.record_pos = 0

        default_record_index = filtered_df.index[st.session_state.record_pos]
        record_index = st.selectbox(
            "Choose a record to view/edit:",
            filtered_df.index,
            index=list(filtered_df.index).index(default_record_index),
            format_func=lambda x: f"{filtered_df.loc[x, 'Name (Last, First)']} ({filtered_df.loc[x, 'Email Address']})"
        )
        st.session_state.record_pos = list(filtered_df.index).index(record_index)
        record = filtered_df.loc[record_index]
        row_number = int(record["RowNumber"])

        # ---------------- Columns for Summary & Edit ----------------
        col_summary, col_edit = st.columns([3, 2])  # two equal width columns

        # ---------- LEFT COLUMN: SUMMARY ----------
        with col_summary:
            st.subheader("📄 Summary (Read Only)")
            summary_fields = [
                ("Name", "Name (Last, First)"),
                ("Email", "Email Address"),
                ("Intake Received", "Date Received (formula from A)"),
                ("Approved?", "Accepted?\n(y, maybe, n, \"\")"),
                ("Approved Date", "Date app'd/assigned "),
                ("Approved by", "Approved/Reassigned by"),
                ("OPT?", "OPT"),
                ("Team", "NC-Track (initial)"),
                ("Role", "NC-Role (initial)"),
                ("Rejected/Left Date (if any)", "Date left/rejected"),
                ("FM Last Update By", "FM Last Update By"),
                #("Comments","Comments (prior career)"),
            ]
            table_md = "| Field | Value |\n|-------|-------|\n"
            for label, col in summary_fields:
                value = str(record.get(col, "")).replace("\n", "<br>")
                table_md += f"| **{label}** | {value} |\n"
            st.markdown(table_md, unsafe_allow_html=True)

        # ---------- RIGHT COLUMN: EDITABLE FIELDS ----------
        with col_edit:
            st.subheader("📄 Edit Section")
            if user_role in ["Admin"]:
                vcl_issued_default = safe_date(record.get("VCL Issued Date"))
                vcl_start_default = safe_date(record.get("VCL Start"))
                vcl_end_default = safe_date(record.get("VCL End"))
                vel_issued_default = safe_date(record.get("VEL Issued \nDate"))

                #opt_ltr_status_default = "" if pd.isna(record.get("OPT LTR Status")) else str(record.get("OPT LTR Status"))
                final_status_default = "" if pd.isna(record.get("Final Status")) else str(record.get("Final Status"))

                # Editable date and text fields
                vcl_issued = st.date_input("Last VCL Issued Date", value=vcl_issued_default if vcl_issued_default else None, key=f"vcl_issued_{row_number}")
                vcl_start = st.date_input("VCL Start", value=vcl_start_default if vcl_start_default else None, key=f"vcl_start_{row_number}")
                vcl_end = st.date_input("VCL End", value=vcl_end_default if vcl_end_default else None, key=f"vcl_end_{row_number}")
                vel_issued = st.date_input("VEL Issued Date", value=vel_issued_default if vel_issued_default else None, key=f"vel_issued_{row_number}")

                #opt_ltr_status = st.text_input("OPT LTR Status", value=opt_ltr_status_default, key=f"opt_ltr_status_{row_number}")
                final_status = st.text_input("Status (placeholder)", value=final_status_default, key=f"final_status_{row_number}")
            else:
                st.info("You have read-only access to this data.")

        st.markdown("---")

        # ---------------- Action Buttons ----------------
        col1, col2, col3 = st.columns(3)
        if user_role in ["Admin"]:
            with col2:
                if st.button("💾 Submit Update"):
                    try:
                        # Update Google Sheet with edited fields
                        if vcl_issued: sheet.update(f"AI{row_number}", [[vcl_issued.strftime("%m/%d/%y")]])
                        if vcl_start: sheet.update(f"AJ{row_number}", [[vcl_start.strftime("%m/%d/%y")]])
                        if vcl_end: sheet.update(f"AK{row_number}", [[vcl_end.strftime("%m/%d/%y")]])
                        #if opt_ltr_status: sheet.update(f"AM{row_number}", [[opt_ltr_status]])
                        if vel_issued: sheet.update(f"AL{row_number}", [[vel_issued.strftime("%m/%d/%y")]])
                        if final_status: sheet.update(f"AN{row_number}", [[final_status]])

                        st.success("✅ Changes saved successfully. Moving to next record...")
                        st.session_state.record_pos += 1
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed to save changes: {e}")

        with col1:
            if st.button("⬅️ Previous Record", disabled=st.session_state.record_pos <= 0):
                st.session_state.record_pos -= 1
                st.rerun()

        with col3:
            if st.button("➡️ Next Record", disabled=st.session_state.record_pos >= len(filtered_df) - 1):
                st.session_state.record_pos += 1
                st.rerun()
    else:
        st.info("You don't have access to this APP")


# ----------------- MAIN APP -----------------
def main():
    """Main app flow: login and app selection."""
    if "logged_in" not in st.session_state:
        st.session_state["logged_in"] = False

    if not st.session_state["logged_in"]:
        login()
    else:
        # Sidebar: show user info
        st.sidebar.success("Login successful!")
        st.sidebar.markdown(
            f"""
            **👤 User:** {st.session_state['user_email']}  
            **🔐 Role:** {st.session_state['user_role']}
            """
        )

        # Sidebar: app selection
        st.sidebar.markdown("---")
        app_choice = st.sidebar.radio("Select App", ["FM-Pending Update", "OPT SVC"])

        # Show selected app
        if app_choice == "FM-Pending Update":
            show_pending_triage_app()
        elif app_choice == "OPT SVC":
            show_opt_svc_app()

if __name__ == "__main__":
    main()

