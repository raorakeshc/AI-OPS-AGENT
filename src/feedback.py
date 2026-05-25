import os
import json
import logging


class FeedbackManager:
    def __init__(self, filepath: str | None = None):
        self.filepath = filepath or os.path.join("data", "feedback.json")
        os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
        if not os.path.exists(self.filepath):
            with open(self.filepath, "w") as f:
                json.dump([], f)

    def add_feedback(self, feedback: str):
        try:
            with open(self.filepath, "r") as f:
                feedbacks = json.load(f)
        except Exception:
            feedbacks = []
        feedbacks.append(feedback)
        try:
            with open(self.filepath, "w") as f:
                json.dump(feedbacks, f)
        except Exception as e:
            logging.error(f"Failed to save feedback: {e}")

    def get_feedback_string(self) -> str:
        try:
            with open(self.filepath, "r") as f:
                feedbacks = json.load(f)
        except Exception:
            feedbacks = []
        if not feedbacks:
            return ""
        return (
            "\n\nCRITICAL USER FEEDBACK (ADJUST YOUR TONE/STYLE TO FOLLOW THESE RULES, BUT CONTINUE TO USE YOUR TOOLS NORMALLY):\n- "
            + "\n- ".join(feedbacks)
        )
