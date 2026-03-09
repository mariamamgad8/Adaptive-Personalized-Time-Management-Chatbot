import re
from typing import Dict, List, Any


class SmartParser:
    def __init__(self):
        self.days = [
            "monday", "tuesday", "wednesday",
            "thursday", "friday", "saturday", "sunday"
        ]

        self.task_keywords = {
            "math": {"task_name": "Math Study", "category": "study"},
            "ai": {"task_name": "AI Study", "category": "study"},
            "signals": {"task_name": "Signals Study", "category": "study"},
            "quran": {"task_name": "Quran Memorization", "category": "personal"},
            "exercise": {"task_name": "Exercise", "category": "exercise"},
            "gym": {"task_name": "Exercise", "category": "exercise"},
            "reading": {"task_name": "Reading", "category": "personal"},
            "deep learning": {"task_name": "Deep Learning", "category": "study"},
            "algorithms": {"task_name": "Algorithms Practice", "category": "study"},
        }

    def parse(self, message: str) -> Dict[str, Any]:
        text = message.strip().lower()

        intent = self.detect_intent(text)

        result = {
            "intent": intent,
            "raw_text": message
        }

        if intent == "plan_tasks":
            result["tasks"] = self.extract_tasks(text)

        elif intent == "wasted_time":
            result.update(self.extract_wasted_time(text))

        elif intent == "missed_task":
            result.update(self.extract_missed_task(text))

        elif intent == "new_event":
            result.update(self.extract_new_event(text))

        return result

    def detect_intent(self, text: str) -> str:
        if any(phrase in text for phrase in ["wasted", "lost", "wasted time", "lost time"]):
            return "wasted_time"

        if any(phrase in text for phrase in ["missed", "didn't do", "did not do", "skipped"]):
            return "missed_task"

        if any(phrase in text for phrase in ["i have a class", "i have class", "i added", "i have an event", "meeting", "appointment"]):
            return "new_event"

        if any(phrase in text for phrase in ["i want to study", "i want to", "plan my week", "schedule", "organize my time"]):
            return "plan_tasks"

        return "unknown"

    def extract_tasks(self, text: str) -> List[Dict[str, Any]]:
        tasks = []

        for keyword, info in self.task_keywords.items():
            if keyword in text:
                duration = self.extract_duration_for_keyword(text, keyword)
                priority = self.infer_priority(text, keyword)
                deadline_day = self.extract_deadline_day(text)
                deadline_hour = self.extract_deadline_hour(text)

                repeat_count = 1
                if keyword in ["exercise", "gym"]:
                    repeat_count = self.extract_repeat_count(text, default=1)

                if keyword == "quran" and "daily" in text:
                    repeat_count = 7
                    deadline_day = "Daily"

                for _ in range(repeat_count):
                    tasks.append({
                        "task_name": info["task_name"],
                        "category": info["category"],
                        "duration_hours": duration,
                        "priority": priority,
                        "deadline_day": deadline_day,
                        "deadline_hour": deadline_hour
                    })

        return tasks

    def extract_duration_for_keyword(self, text: str, keyword: str) -> float:
        pattern_1 = rf"{re.escape(keyword)}.*?(\d+(?:\.\d+)?)\s*hours?"
        pattern_2 = rf"(\d+(?:\.\d+)?)\s*hours?.*?{re.escape(keyword)}"

        match = re.search(pattern_1, text)
        if match:
            return float(match.group(1))

        match = re.search(pattern_2, text)
        if match:
            return float(match.group(1))

        if keyword == "quran":
            return 1.0
        if keyword in ["exercise", "gym"]:
            return 1.0

        return 2.0

    def extract_repeat_count(self, text: str, default: int = 1) -> int:
        match = re.search(r"(\d+)\s*times?", text)
        if match:
            return int(match.group(1))
        return default

    def infer_priority(self, text: str, keyword: str) -> int:
        if any(word in text for word in ["urgent", "important", "must", "priority"]):
            return 5

        if keyword in ["quran", "math", "ai", "signals"]:
            return 4

        if keyword in ["exercise", "reading"]:
            return 3

        return 3

    def extract_deadline_day(self, text: str) -> str:
        if "daily" in text:
            return "Daily"
        if "this week" in text or "weekly" in text:
            return "Weekly"

        for day in self.days:
            if day in text:
                return day.capitalize()

        return "Weekly"

    def extract_deadline_hour(self, text: str) -> int:
        match = re.search(r"by\s+(\d{1,2})", text)
        if match:
            return int(match.group(1))

        return 20

    def extract_wasted_time(self, text: str) -> Dict[str, Any]:
        hours_lost = 1
        day = "Monday"
        block_name = None
        start_hour = None

        match = re.search(r"(\d+(?:\.\d+)?)\s*hours?", text)
        if match:
            hours_lost = float(match.group(1))

        for d in self.days:
            if d in text:
                day = d.capitalize()
                break

        if "morning" in text:
            block_name = "morning"
        elif "afternoon" in text:
            block_name = "afternoon"
        elif "evening" in text or "night" in text:
            block_name = "evening"

        time_match = re.search(r"at\s+(\d{1,2})", text)
        if time_match:
            start_hour = float(time_match.group(1))

        return {
            "day": day,
            "hours_lost": hours_lost,
            "block_name": block_name,
            "start_hour": start_hour
        }

    def extract_missed_task(self, text: str) -> Dict[str, Any]:
        detected_task = None

        for keyword, info in self.task_keywords.items():
            if keyword in text:
                detected_task = info["task_name"]
                break

        if detected_task is None:
            match = re.search(r"missed\s+(?:my\s+)?(.+)", text)
            if match:
                detected_task = match.group(1).strip().title()

        return {"task_name": detected_task}

    def extract_new_event(self, text: str) -> Dict[str, Any]:
        event_name = "New Event"
        day = "Monday"
        start_hour = 14
        end_hour = 16

        for d in self.days:
            if d in text:
                day = d.capitalize()
                break

        time_range = re.search(r"from\s+(\d{1,2})\s*(?:to|-)\s*(\d{1,2})", text)
        if time_range:
            start_hour = int(time_range.group(1))
            end_hour = int(time_range.group(2))

        if "class" in text:
            event_name = "Class"
        elif "meeting" in text:
            event_name = "Meeting"
        elif "appointment" in text:
            event_name = "Appointment"

        return {
            "event_name": event_name,
            "day": day,
            "start_hour": start_hour,
            "end_hour": end_hour
        }