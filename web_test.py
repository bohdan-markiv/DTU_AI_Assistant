import streamlit as st
from openaiwrapper import OpenAIWrapper
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import uuid

# --- Constants ---
SHEET_ID = '1biUALdK33sgINUMLck2VM7QBZpZz-Uswz-Q3Hpvgda0'
SHEET_NAME = 'Sheet1'

# --- Session Setup ---
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "wrapper" not in st.session_state:
    st.session_state.wrapper = OpenAIWrapper()
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "saved_pairs" not in st.session_state:
    st.session_state.saved_pairs = set()

# --- Google Sheets Auth ---


def get_gsheet_client():
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    service_account_info = st.secrets["gcp_service_account"]
    credentials = Credentials.from_service_account_info(
        service_account_info, scopes=scopes)
    return gspread.authorize(credentials)

# --- Save Prompt-Response Pair to Sheets ---


def save_pair_to_gsheet(timestamp, session_id, prompt, response, rating, feedback):
    sheet = get_gsheet_client().open_by_key(SHEET_ID).worksheet(SHEET_NAME)

    # Add headers if the sheet is empty
    if sheet.row_count == 0 or not sheet.get_all_values():
        sheet.append_row(["Timestamp", "Session ID", "Prompt",
                         "Response", "Rating", "Feedback"])

    # Then append the actual row
    sheet.append_row([timestamp, session_id, prompt,
                     response, rating, feedback])


# --- UI Setup ---
st.set_page_config(page_title="AI Assistant", layout="centered")
st.title("🤖 Chat with DTU Assistant. Слава Україні!")

wrapper = st.session_state.wrapper

# --- Input ---
user_input = st.chat_input("Ask me anything...")

if user_input:
    now = datetime.now().isoformat(timespec="seconds")
    session_id = st.session_state.session_id
    st.session_state.chat_history.append({
        "role": "user",
        "content": user_input,
        "time": now,
        "session_id": session_id,
    })
    st.session_state.chat_history.append({
        "role": "assistant",
        "content": "__thinking__",
        "time": now,
        "session_id": session_id,
    })
    st.rerun()

# --- Display Messages ---
i = 0
while i < len(st.session_state.chat_history):
    msg = st.session_state.chat_history[i]
    with st.chat_message(msg["role"]):
        if msg["content"] == "__thinking__":
            with st.spinner("Thinking..."):
                response = wrapper.write_message(
                    st.session_state.chat_history[i - 1]["content"])
                st.session_state.chat_history[i]["content"] = response or "Sorry, I couldn't generate a response."
                st.rerun()
        else:
            st.markdown(msg["content"])

            # Check if this is an assistant message and has a user message before it
            if msg["role"] == "assistant" and i > 0 and st.session_state.chat_history[i - 1]["role"] == "user":
                pair_key = f"{i - 1}_{i}"

                # Only show the feedback block for assistant messages
                if msg["role"] == "assistant" and i > 0 and st.session_state.chat_history[i - 1]["role"] == "user":

                    if pair_key not in st.session_state.saved_pairs:
                        with st.expander("💬 Rate this response", expanded=True):
                            rating_key = f"rating_{i}"
                            feedback_key = f"feedback_{i}"

                            # # if rating_key not in st.session_state:
                            # #     st.session_state[rating_key] = 7
                            # if feedback_key not in st.session_state:
                            #     st.session_state[feedback_key] = ""

                            rating = st.slider(
                                "Rate from 1 to 10", 1, 10, 7, key=rating_key)
                            feedback = st.text_area(
                                "Feedback (optional)", value="", key=feedback_key)

                            if st.button("✅ Save this exchange", key=f"save_btn_{i}"):
                                prompt = st.session_state.chat_history[i - 1]["content"]
                                response = msg["content"]
                                timestamp = msg["time"]
                                session_id = msg["session_id"]
                                save_pair_to_gsheet(
                                    timestamp, session_id, prompt, response, rating, feedback)
                                st.session_state.saved_pairs.add(pair_key)
                                st.success("Saved to Google Sheets ✅")

    i += 1
