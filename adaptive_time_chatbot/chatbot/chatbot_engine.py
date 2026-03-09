import pandas as pd
from chatbot.parser import SmartParser
from scheduling.scheduler import WeeklyScheduler
from scheduling.replanner import ReplanningEngine


class ChatbotEngine:
    def __init__(self):
        self.parser = SmartParser()
        self.scheduler = WeeklyScheduler()
        self.replanner = ReplanningEngine(scheduler=self.scheduler)

    def process_message(
        self,
        user_message,
        user_profile,
        tasks_df,
        fixed_events_df,
        current_schedule=None
    ):
        parsed = self.parser.parse(user_message)
        intent = parsed["intent"]

        if intent == "plan_tasks":
            return self._handle_plan_tasks(
                parsed=parsed,
                user_profile=user_profile,
                tasks_df=tasks_df,
                fixed_events_df=fixed_events_df
            )

        if intent == "wasted_time":
            return self._handle_wasted_time(
                parsed=parsed,
                user_profile=user_profile,
                tasks_df=tasks_df,
                fixed_events_df=fixed_events_df,
                current_schedule=current_schedule
            )

        if intent == "missed_task":
            return self._handle_missed_task(
                parsed=parsed,
                user_profile=user_profile,
                tasks_df=tasks_df,
                fixed_events_df=fixed_events_df,
                current_schedule=current_schedule
            )

        if intent == "new_event":
            return self._handle_new_event(
                parsed=parsed,
                user_profile=user_profile,
                tasks_df=tasks_df,
                fixed_events_df=fixed_events_df,
                current_schedule=current_schedule
            )

        return {
            "text": "Sorry, I could not understand your request yet. Try asking me to plan tasks, report wasted time, mention a missed task, or add a new event.",
            "updated_tasks_df": tasks_df,
            "updated_fixed_events_df": fixed_events_df,
            "updated_schedule": current_schedule
        }

    def _handle_plan_tasks(self, parsed, user_profile, tasks_df, fixed_events_df):
        parsed_tasks = parsed.get("tasks", [])

        if not parsed_tasks:
            return {
                "text": "I understood this as a planning request, but I could not detect any tasks in your message.",
                "updated_tasks_df": tasks_df,
                "updated_fixed_events_df": fixed_events_df,
                "updated_schedule": None
            }

        new_tasks_df = self._append_new_tasks(tasks_df, user_profile["user_id"], parsed_tasks)

        schedule_df = self.scheduler.generate_weekly_schedule(
            user_profile=user_profile,
            tasks_df=new_tasks_df,
            fixed_events_df=fixed_events_df
        )

        response_text = self._format_schedule_response(
            intro="I created your weekly plan.",
            schedule_df=schedule_df
        )

        return {
            "text": response_text,
            "updated_tasks_df": new_tasks_df,
            "updated_fixed_events_df": fixed_events_df,
            "updated_schedule": schedule_df
        }

    def _handle_wasted_time(self, parsed, user_profile, tasks_df, fixed_events_df, current_schedule):
        if current_schedule is None or len(current_schedule) == 0:
            return {
                "text": "You do not have a generated schedule yet. Ask me to plan your week first.",
                "updated_tasks_df": tasks_df,
                "updated_fixed_events_df": fixed_events_df,
                "updated_schedule": current_schedule
            }

        updated_schedule, recovery_schedule, msg = self.replanner.handle_wasted_time(
            schedule_df=current_schedule,
            tasks_df=tasks_df,
            fixed_events_df=fixed_events_df,
            user_profile=user_profile,
            day=parsed["day"],
            hours_lost=parsed["hours_lost"],
            block_name=parsed.get("block_name"),
            start_hour=parsed.get("start_hour")
        )

        response_text = self._format_schedule_response(
            intro=msg,
            schedule_df=recovery_schedule,
            label="Recovery plan"
        )

        return {
            "text": response_text,
            "updated_tasks_df": tasks_df,
            "updated_fixed_events_df": fixed_events_df,
            "updated_schedule": updated_schedule
        }

    def _handle_missed_task(self, parsed, user_profile, tasks_df, fixed_events_df, current_schedule):
        if current_schedule is None or len(current_schedule) == 0:
            return {
                "text": "You do not have a generated schedule yet. Ask me to plan your week first.",
                "updated_tasks_df": tasks_df,
                "updated_fixed_events_df": fixed_events_df,
                "updated_schedule": current_schedule
            }

        task_name = parsed.get("task_name")
        if not task_name:
            return {
                "text": "I understood that you missed a task, but I could not identify which task it was.",
                "updated_tasks_df": tasks_df,
                "updated_fixed_events_df": fixed_events_df,
                "updated_schedule": current_schedule
            }

        updated_schedule, recovery_schedule, msg = self.replanner.handle_missed_task(
            schedule_df=current_schedule,
            tasks_df=tasks_df,
            fixed_events_df=fixed_events_df,
            user_profile=user_profile,
            task_name=task_name
        )

        response_text = self._format_schedule_response(
            intro=msg,
            schedule_df=recovery_schedule,
            label="Rescheduled task"
        )

        return {
            "text": response_text,
            "updated_tasks_df": tasks_df,
            "updated_fixed_events_df": fixed_events_df,
            "updated_schedule": updated_schedule
        }

    def _handle_new_event(self, parsed, user_profile, tasks_df, fixed_events_df, current_schedule):
        if current_schedule is None or len(current_schedule) == 0:
            return {
                "text": "You do not have a generated schedule yet. Ask me to plan your week first.",
                "updated_tasks_df": tasks_df,
                "updated_fixed_events_df": fixed_events_df,
                "updated_schedule": current_schedule
            }

        updated_schedule, recovery_schedule, updated_events, msg = self.replanner.handle_new_fixed_event(
            schedule_df=current_schedule,
            tasks_df=tasks_df,
            fixed_events_df=fixed_events_df,
            user_profile=user_profile,
            event_name=parsed["event_name"],
            day=parsed["day"],
            start_hour=parsed["start_hour"],
            end_hour=parsed["end_hour"]
        )

        response_text = self._format_schedule_response(
            intro=msg,
            schedule_df=recovery_schedule,
            label="Updated plan"
        )

        return {
            "text": response_text,
            "updated_tasks_df": tasks_df,
            "updated_fixed_events_df": updated_events,
            "updated_schedule": updated_schedule
        }

    def _append_new_tasks(self, tasks_df, user_id, parsed_tasks):
        existing_df = tasks_df.copy()

        next_task_id = 1
        if not existing_df.empty and "task_id" in existing_df.columns:
            next_task_id = int(existing_df["task_id"].max()) + 1

        rows = []
        for task in parsed_tasks:
            rows.append({
                "task_id": next_task_id,
                "user_id": user_id,
                "task_name": task["task_name"],
                "category": task["category"],
                "duration_hours": task["duration_hours"],
                "priority": task["priority"],
                "deadline_day": task["deadline_day"],
                "deadline_hour": task["deadline_hour"]
            })
            next_task_id += 1

        new_rows_df = pd.DataFrame(rows)

        if existing_df.empty:
            return new_rows_df

        return pd.concat([existing_df, new_rows_df], ignore_index=True)

    def _format_schedule_response(self, intro, schedule_df, label="Generated schedule"):
        lines = [intro, "", f"{label}:"]

        if schedule_df is None or schedule_df.empty:
            lines.append("No schedule items found.")
            return "\n".join(lines)

        current_day = None
        for _, row in schedule_df.iterrows():
            day = row["day"]

            if day != current_day:
                lines.append(f"\n{day}")
                current_day = day

            if pd.isna(row["start_hour"]) or pd.isna(row["end_hour"]):
                lines.append(f"- {row['task_name']} (unscheduled)")
            else:
                start = self._format_hour(row["start_hour"])
                end = self._format_hour(row["end_hour"])
                lines.append(f"- {start} to {end}: {row['task_name']}")

        return "\n".join(lines)

    def _format_hour(self, value):
        if float(value).is_integer():
            return f"{int(value)}:00"

        hour = int(value)
        minutes = int(round((value - hour) * 60))
        return f"{hour}:{minutes:02d}"