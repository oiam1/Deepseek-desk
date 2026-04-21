import json
from pathlib import Path

from utils import extract_first_line, generate_id, get_current_time


class DataManager:
    def __init__(self, filepath="conversations.json"):
        self.filepath = Path(filepath)
        self.conversations = {}
        self.load()

    def load(self):
        if not self.filepath.exists():
            self.conversations = {}
            return

        try:
            with self.filepath.open("r", encoding="utf-8") as file:
                data = json.load(file)
        except (OSError, json.JSONDecodeError):
            self.conversations = {}
            return

        self.conversations = data if isinstance(data, dict) else {}

    def save(self):
        temp_path = self.filepath.with_suffix(".tmp")
        with temp_path.open("w", encoding="utf-8") as file:
            json.dump(self.conversations, file, ensure_ascii=False, indent=2)
        temp_path.replace(self.filepath)

    def new_conversation(self, first_user_message=""):
        conv_id = generate_id()
        title = extract_first_line(first_user_message) if first_user_message else "新对话"
        self.conversations[conv_id] = {
            "title": title,
            "messages": [],
            "updated": get_current_time(),
        }
        self.save()
        return conv_id

    def delete_conversation(self, conv_id):
        if conv_id not in self.conversations:
            return False
        del self.conversations[conv_id]
        self.save()
        return True

    def delete_all(self):
        self.conversations.clear()
        self.save()

    def add_message(self, conv_id, role, content, reasoning_content=""):
        if conv_id not in self.conversations:
            return None

        conversation = self.conversations[conv_id]
        conversation["messages"].append(
            {
                "role": role,
                "content": content,
                "reasoning_content": reasoning_content,
                "timestamp": get_current_time(),
            }
        )
        conversation["updated"] = get_current_time()

        if role == "user" and len(conversation["messages"]) == 1:
            conversation["title"] = extract_first_line(content)

        self.save()
        return len(conversation["messages"]) - 1

    def update_message(self, conv_id, message_index, content, reasoning_content=None):
        conversation = self.conversations.get(conv_id)
        if not conversation:
            return False

        messages = conversation.get("messages", [])
        if message_index < 0 or message_index >= len(messages):
            return False

        messages[message_index]["content"] = content
        if reasoning_content is not None:
            messages[message_index]["reasoning_content"] = reasoning_content
        messages[message_index]["timestamp"] = get_current_time()
        conversation["updated"] = get_current_time()
        self.save()
        return True

    def get_messages(self, conv_id):
        if conv_id not in self.conversations:
            return []
        return [
            {"role": msg["role"], "content": msg["content"]}
            for msg in self.conversations[conv_id].get("messages", [])
        ]

    def get_conversation(self, conv_id):
        return self.conversations.get(conv_id)

    def get_conversation_list(self):
        items = [
            (conv_id, data.get("title", "新对话"), data.get("updated", ""))
            for conv_id, data in self.conversations.items()
        ]
        items.sort(key=lambda item: item[2], reverse=True)
        return items
