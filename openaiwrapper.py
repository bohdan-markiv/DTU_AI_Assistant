from openai import OpenAI
import streamlit as st
import time

# Get API key from environment
api_key = st.secrets["OPENAI_API_KEY"]


class OpenAIWrapper:
    def __init__(self):
        self.client = OpenAI(api_key=api_key)
        self.default_assistant = "asst_RhYw3HY9YJM1FnQwv9yGkoD6"
        self.default_vector_storage = "vs_681b4536c7388191916bf5ea2880855e"
        self.thread_id = None

    def create_assistant(self, instructions, name):
        assistant = self.client.beta.assistants.create(
            name=name,
            instructions=instructions,
            model="gpt-4o",
            tools=[{"type": "file_search"}]
        )
        return assistant

    def create_vector_storage(self, name):
        vector_store = self.client.vector_stores.create(name=name)
        return vector_store

    def upload_files(self, file_locations, vector_storage_id=None, batch_size=5):
        if not vector_storage_id:
            vector_storage_id = self.default_vector_storage

        for i in range(0, len(file_locations), batch_size):
            batch = file_locations[i:i + batch_size]
            file_streams = [open(path, "rb") for path in batch]

            try:
                file_batch = self.client.vector_stores.file_batches.upload_and_poll(
                    vector_store_id=vector_storage_id,
                    files=file_streams
                )
                print(
                    f"Batch {i//batch_size + 1}: {file_batch.status}, {file_batch.file_counts}")
            except Exception as e:
                print(f"Error in batch {i//batch_size + 1}: {e}")
            finally:
                for fs in file_streams:
                    fs.close()
            time.sleep(1)

    def add_vector_to_assistant(self, assistant_id=None, vector_storage_id=None):

        if not vector_storage_id:
            vector_storage_id = self.default_vector_storage
        if not assistant_id:
            assistant_id = self.default_assistant

        assistant = self.client.beta.assistants.update(
            assistant_id=assistant_id,
            tool_resources={"file_search": {
                "vector_store_ids": [vector_storage_id]}},
        )

        return assistant

    def write_message(self, message, assistant_id=None):
        if not assistant_id:
            assistant_id = self.default_assistant

        if not self.thread_id:
            thread = self.client.beta.threads.create()
            self.thread_id = thread.id

        # Step 1: Create user message
        self.client.beta.threads.messages.create(
            thread_id=self.thread_id,
            role="user",
            content=message
        )

        # Step 2: Run the assistant
        run = self.client.beta.threads.runs.create_and_poll(
            thread_id=self.thread_id,
            assistant_id=assistant_id
        )

        # Step 3: Get assistant messages
        messages = self.client.beta.threads.messages.list(
            thread_id=self.thread_id,
            run_id=run.id
        ).data

        # Find assistant reply
        assistant_reply = next(
            (m for m in messages if m.role == "assistant"), None)
        if not assistant_reply:
            print("No assistant reply found.")
            return None

        message_content = assistant_reply.content[0].text
        annotations = message_content.annotations or []
        citations = []

        for index, annotation in enumerate(annotations):
            message_content.value = message_content.value.replace(
                annotation.text, f"[{index}]")
            if file_citation := getattr(annotation, "file_citation", None):
                cited_file = self.client.files.retrieve(file_citation.file_id)
                citations.append(f"[{index}] {cited_file.filename}")

        if citations:
            message_content.value += "\n\n**Citations:**\n" + \
                "\n".join(citations)

        return message_content
