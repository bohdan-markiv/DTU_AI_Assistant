from openai import OpenAI
import streamlit as st
import time
import json
from pathlib import Path

# Get API key from environment
# api_key = st.secrets["OPENAI_API_KEY"]
api_key = st.secrets["OPENAI_API_KEY"]


class OpenAIWrapper:
    def __init__(self):
        self.client = OpenAI(api_key=api_key)
        self.default_assistant = "asst_1OPu6ADtBcHwnGPFGacuzMma"
        self.default_vector_storage = "vs_685d88cab14881918083043610feb1d8"
        self.thread_id = None

    def create_assistant(self, instructions, name, model="gpt-4.1-mini", tools=[{"type": "file_search"}]):
        assistant = self.client.beta.assistants.create(
            name=name,
            instructions=instructions,
            model=model,
            tools=tools
        )
        return assistant

    def create_vector_storage(self, name):
        vector_store = self.client.vector_stores.create(name=name)
        return vector_store

    def upload_files(self, folder_path: str, vector_storage_id: str | None = None, batch_size: int = 5) -> None:
        """
        Upload all files found in `folder_path` to the specified (or default) vector store,
        using `batch_size` uploads per request and retrying each batch up to 3 times.

        Parameters
        ----------
        folder_path : str
            Absolute or relative path to the folder that contains the files you want to upload.
        vector_storage_id : str | None, optional
            Target vector-store ID.  Defaults to `self.default_vector_storage`.
        batch_size : int, optional
            Number of files to upload per request.  Defaults to 5.
        """
        if vector_storage_id is None:
            vector_storage_id = self.default_vector_storage

        folder = Path(folder_path).expanduser().resolve()
        if not folder.is_dir():
            raise ValueError(f"'{folder}' is not a valid directory.")

        file_paths = [p for p in folder.iterdir() if p.is_file()]
        if not file_paths:
            raise ValueError(f"No files found in '{folder}'.")

        MAX_RETRIES = 3

        for batch_idx in range(0, len(file_paths), batch_size):
            batch_paths = file_paths[batch_idx: batch_idx + batch_size]
            attempts = 0
            while attempts < MAX_RETRIES:
                # Open the files fresh on every attempt so the streams are valid.
                file_streams = [open(p, "rb") for p in batch_paths]
                try:
                    result = self.client.vector_stores.file_batches.upload_and_poll(
                        vector_store_id=vector_storage_id,
                        files=file_streams
                    )
                    print(f"Batch {batch_idx // batch_size + 1}: "
                          f"{result.status}, {result.file_counts}")
                    break                                           # Success
                except Exception as exc:
                    attempts += 1
                    print(f"Error in batch {batch_idx // batch_size + 1}, "
                          f"attempt {attempts}: {exc}")
                    if attempts < MAX_RETRIES:
                        print("Retrying in 2 s…")
                        time.sleep(2)
                finally:
                    for fs in file_streams:
                        fs.close()
            else:
                # Only runs if the while-loop exited via exhaustion, not via break.
                print(f"❌  Failed to upload batch {batch_idx // batch_size + 1} "
                      f"after {MAX_RETRIES} attempts.")

        time.sleep(1)  # Gentle pause between batches

    def add_vector_to_assistant(self, assistant_id=None, vector_storage_id=None):

        if not vector_storage_id:
            vector_storage_id = self.default_vector_storage
        if not assistant_id:
            assistant_id = self.default_assistant

        # 1️⃣  Fetch the current assistant config
        assistant = self.client.beta.assistants.retrieve(
            assistant_id=assistant_id)

        # 2️⃣  Extract the existing list safely
        file_search_cfg = (assistant.tool_resources or {}
                           ).get("file_search", {})
        current_ids = list(file_search_cfg.get("vector_store_ids", []))

        # 3️⃣  Append if absent
        if vector_storage_id not in current_ids:
            updated_ids = current_ids + [vector_storage_id]

            assistant = self.client.beta.assistants.update(
                assistant_id=assistant_id,
                tool_resources={"file_search": {
                    "vector_store_ids": updated_ids}},
            )
            print(
                f"Added vector store {vector_storage_id} — total now: {len(updated_ids)}")
        else:
            print(f"Vector store {vector_storage_id} already present.")

        return assistant

    def perform_web_search(self, search_query):
        """Perform a web search in case there is no available relevant data in the database 

        Args:
            search_query (string): Formulated prompt for a web search
        """
        client = OpenAI(api_key=api_key)

        response = client.responses.create(
            model="gpt-4.1-mini",
            tools=[{"type": "web_search_preview"}],
            input=search_query,
            instructions="You are a defense-oriented assistant. Prioritize UAV and drone-related news if relevant, and keep answers factual and concise. Firstly check your internal knowledge in the database, and if you don't find anything - search in the web."
        )

        return (response.output_text)

    def perform_additional_db_search(self, search_query, type):
        vector_dbs = {
            "posts": "vs_685160163c2c8191a7fa725ffbb10e90",
            "news": "vs_68515fd639d08191a76323413ad2444b",
            "technologies": "vs_68516027d120819184648a7d26153959"
        }
        vector_id = vector_dbs[type]
        client = OpenAI(api_key=api_key)

        response = client.responses.create(
            model="gpt-4o-mini",
            input=search_query,
            tools=[{
                "type": "file_search",
                "vector_store_ids": [vector_id]
            }],
            include=["file_search_call.results"]
        )
        return (response.output_text)

    def write_message(self, message, assistant_id=None):
        if not assistant_id:
            assistant_id = self.default_assistant

        if not self.thread_id:
            thread = self.client.beta.threads.create()
            self.thread_id = thread.id
        try:
            with open("vocab.json", "r", encoding="utf-8") as f:
                vocab_glossary = json.load(f)
        except Exception as e:
            print(f"Error loading glossary: {e}")
            vocab_glossary = {}

        glossary_text = "\n".join(
            f"- **{k}**: {v}" for k, v in vocab_glossary.items())

        glossary_prompt = (
            "Below is a glossary of terms the user may use. These are for your understanding only. "
            "You should NOT use these alternate terms in your own responses unless the user uses them first. "
            "Default to professional, standard terminology in your replies.\n\n"
            + glossary_text + "\n\n"
        )

        # Step 1: Create user message
        self.client.beta.threads.messages.create(
            thread_id=self.thread_id,
            role="user",
            content=glossary_prompt + message
        )

        # Step 2: Run the assistant
        run = self.client.beta.threads.runs.create_and_poll(
            thread_id=self.thread_id,
            assistant_id=assistant_id
        )

        # # # Step 3: Check for tool call
        # # steps = self.client.beta.threads.runs.steps.list(
        # #     thread_id=self.thread_id,
        # #     run_id=run.id
        # # ).data

        # # tool_call_step = next(
        # #     (s for s in steps if s.type == "tool_calls"), None)

        # # if tool_call_step:
        # #     tool_calls = tool_call_step.step_details.tool_calls
        # #     tool_outputs = []

        # #     for tool_call in tool_calls:
        # #         name = tool_call.function.name
        # #         arguments = json.loads(tool_call.function.arguments)

        # #         if name == "perform_web_search":
        # #             prompt = arguments["search_query"]
        # #             result = self.perform_web_search(search_query=prompt)

        # #             tool_outputs.append({
        # #                 "tool_call_id": tool_call.id,
        # #                 "output": result
        # #             })
        # #         elif name == "search_vector_db":
        # #             prompt = arguments["search_query"]
        # #             type = arguments["type"]
        # #             result = self.perform_additional_db_search(
        # #                 search_query=prompt, type=type)

        # #             tool_outputs.append({
        # #                 "tool_call_id": tool_call.id,
        # #                 "output": result
        # #             })

        #     # Submit tool output to assistant
        #     self.client.beta.threads.runs.submit_tool_outputs(
        #         thread_id=self.thread_id,
        #         run_id=run.id,
        #         tool_outputs=tool_outputs
        #     )

        # Wait again for assistant to finish after using tool
        start_time = time.time()
        timeout_seconds = 30

        while True:
            run = self.client.beta.threads.runs.retrieve(
                thread_id=self.thread_id,
                run_id=run.id
            )

            if run.status in ["completed", "failed", "cancelled", "expired"]:
                break

            if time.time() - start_time > timeout_seconds:
                print("Timeout: Assistant run did not finish within 30 seconds.")
                break

            time.sleep(1)

        # Step 4: Get assistant's message
        messages = self.client.beta.threads.messages.list(
            thread_id=self.thread_id,
            run_id=run.id
        ).data

        assistant_reply = next(
            (m for m in messages if m.role == "assistant"), None)
        if not assistant_reply:
            print("No assistant reply found.")
            return None

        # Handle message content & citations
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

        return message_content.value
