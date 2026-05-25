import os
import json
import logging
import re
from datetime import datetime, timedelta


class FeedbackManager:
    def __init__(self, filepath: str | None = None):
        self.filepath = filepath or os.path.join("data", "feedback.json")
        os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
        if not os.path.exists(self.filepath):
            with open(self.filepath, "w") as f:
                json.dump([], f)

    def add_feedback(self, feedback: str):
        # Basic sanitization to avoid storing obvious PII (emails, phones)
        def _sanitize_text(text: str) -> str:
            # remove email addresses
            text = re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "[redacted_email]", text)
            # remove common phone number patterns
            text = re.sub(r"\+?\d[\d\s\-\(\)]{6,}\d", "[redacted_phone]", text)
            # collapse whitespace and trim
            text = re.sub(r"\s+", " ", text).strip()
            # cap length
            if len(text) > 400:
                return text[:400] + "..."
            return text

        sanitized = _sanitize_text(feedback)

        # Load existing feedbacks and capture a before snapshot for audit
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                feedbacks = json.load(f)
        except Exception:
            feedbacks = []

        before_snapshot = list(feedbacks)
        feedbacks.append(sanitized)

        try:
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(feedbacks, f)
        except Exception as e:
            logging.error(f"Failed to save feedback: {e}")

        # Append an audit record for observability (before/after)
        try:
            audit_dir = os.path.join(os.path.dirname(self.filepath), "audit")
            os.makedirs(audit_dir, exist_ok=True)
            audit_path = os.path.join(audit_dir, "feedback_audit.log")
            entry = {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "added_feedback": sanitized,
                "before_count": len(before_snapshot),
                "after_count": len(feedbacks),
            }
            with open(audit_path, "a", encoding="utf-8") as af:
                af.write(json.dumps(entry) + "\n")
        except Exception:
            logging.exception("Failed to write feedback audit record")

        # Rotate audit logs older than retention to limit growth
        try:
            self._rotate_audit_logs(retention_days=90)
        except Exception:
            logging.exception("Failed during audit log rotation")

    def _rotate_audit_logs(self, retention_days: int = 90) -> int:
        """Remove audit entries older than retention_days. Returns number removed."""
        audit_dir = os.path.join(os.path.dirname(self.filepath), "audit")
        audit_path = os.path.join(audit_dir, "feedback_audit.log")
        if not os.path.exists(audit_path):
            return 0

        keep_ts = datetime.utcnow() - timedelta(days=retention_days)
        kept_lines = []
        removed = 0
        try:
            with open(audit_path, "r", encoding="utf-8") as af:
                for line in af:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                        ts = obj.get("timestamp")
                        if ts:
                            # handle trailing Z
                            ts_dt = datetime.fromisoformat(ts.replace("Z", ""))
                            if ts_dt >= keep_ts:
                                kept_lines.append(line)
                            else:
                                removed += 1
                        else:
                            kept_lines.append(line)
                    except Exception:
                        kept_lines.append(line)

            # overwrite with kept lines
            with open(audit_path, "w", encoding="utf-8") as af:
                for l in kept_lines:
                    af.write(l + "\n")
        except Exception as e:
            logging.exception("Failed to rotate audit logs: %s", e)
        return removed

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
