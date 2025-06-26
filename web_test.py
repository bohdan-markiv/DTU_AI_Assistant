import streamlit as st
from openaiwrapper import OpenAIWrapper
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import uuid
from datetime import datetime
# Set these
# from the Google Sheets URL
SHEET_ID = '1biUALdK33sgINUMLck2VM7QBZpZz-Uswz-Q3Hpvgda0'
SHEET_NAME = 'Sheet1'  # or another sheet name in the file
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
# Authorize client


def get_gsheet_client():
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    service_account_info = st.secrets["gcp_service_account"]
    credentials = Credentials.from_service_account_info(
        service_account_info, scopes=scopes)
    return gspread.authorize(credentials)

# Save to Google Sheet


def save_chat_to_gsheet(chat_history):
    client = get_gsheet_client()
    sheet = client.open_by_key(SHEET_ID).worksheet(SHEET_NAME)

    # Filter out placeholder and format rows
    rows = [
        [msg["role"], msg["content"]]
        for msg in chat_history if msg["content"] != "__thinking__"
    ]

    # Clear existing and write fresh data
    sheet.clear()
    sheet.append_row(["Role", "Content"])
    for row in rows:
        sheet.append_row(row)

    return True


st.set_page_config(page_title="AI Assistant", layout="centered")
st.title("🤖 Chat with DTU Assistant. Слава Україні!")

# Initialize wrapper and session state
if "wrapper" not in st.session_state:
    st.session_state.wrapper = OpenAIWrapper()
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

wrapper = st.session_state.wrapper

# User input
user_input = st.chat_input("Ask me anything...")

if user_input:
    now = datetime.now().isoformat(timespec="seconds")
    session_id = st.session_state.session_id

    # Add user message
    st.session_state.chat_history.append({
        "role": "user",
        "content": user_input,
        "time": now,
        "session_id": session_id,
    })

    # Placeholder assistant message
    st.session_state.chat_history.append({
        "role": "assistant",
        "content": "__thinking__",
        "time": now,  # Same time for response
        "session_id": session_id,
    })

    st.rerun()

# Find and handle the thinking placeholder (if any)
for idx, msg in enumerate(st.session_state.chat_history):
    with st.chat_message(msg["role"]):
        if msg["content"] == "__thinking__":
            with st.spinner("Thinking..."):
                response = wrapper.write_message(
                    st.session_state.chat_history[-2]["content"])
                if response:
                    st.session_state.chat_history[idx]["content"] = response
                else:
                    st.session_state.chat_history[idx]["content"] = "Sorry, I couldn't generate a response."
                st.rerun()
        else:
            st.markdown(msg["content"])

non_placeholder_messages = [
    m for m in st.session_state.chat_history if m['content'] != "__thinking__"
]
message_count = len(non_placeholder_messages)

if "last_saved_row" not in st.session_state:
    st.session_state.last_saved_row = 0

if message_count > st.session_state.last_saved_row:
    new_messages = non_placeholder_messages[st.session_state.last_saved_row:]
    sheet = get_gsheet_client().open_by_key(SHEET_ID).worksheet(SHEET_NAME)

    for msg in new_messages:
        role = msg["role"]
        content = msg["content"]
        timestamp = msg.get(
            "time", datetime.now().isoformat(timespec="seconds"))
        session_id = msg.get("session_id", st.session_state.session_id)
        sheet.append_row([timestamp, session_id, role, content])

    st.session_state.last_saved_row = message_count
    st.toast("📤 Appended chat with metadata to Google Sheets")
