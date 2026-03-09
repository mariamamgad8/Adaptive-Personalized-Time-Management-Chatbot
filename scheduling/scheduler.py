import pandas as pd
import joblib


class WeeklyScheduler:
    def __init__(
        self,
        model_path="models/timeslot_model.pkl",
        time_encoder_path="models/time_encoder.pkl",
        task_encoder_path="models/task_encoder.pkl",
        sleep_encoder_path="models/sleep_encoder.pkl"
    ):
        self.model = joblib.load(model_path)
        self.time_encoder = joblib.load(time_encoder_path)
        self.task_encoder = joblib.load(task_encoder_path)
        self.sleep_encoder = joblib.load(sleep_encoder_path)

        self.days_order = [
            "Monday", "Tuesday", "Wednesday",
            "Thursday", "Friday", "Saturday", "Sunday"
        ]

        self.time_blocks = {
            "morning": (8, 12),
            "afternoon": (13, 17),
            "evening": (18, 22)
        }

    def _get_sleep_pattern(self, sleep_time):
        return "early" if sleep_time in [22, 23, 24] else "late"

    def _predict_best_block(self, task_row, user_profile):
        sleep_pattern = self._get_sleep_pattern(user_profile["sleep_time"])

        model_task_type = task_row["category"].lower()
        if "quran" in str(task_row.get("task_name", "")).lower():
            model_task_type = "quran"

        task_type_encoded = self.task_encoder.transform([model_task_type])[0]
        sleep_encoded = self.sleep_encoder.transform([sleep_pattern])[0]

        energies = {
            "morning": int(user_profile["morning_energy"]),
            "afternoon": int(user_profile["afternoon_energy"]),
            "evening": int(user_profile["evening_energy"])
        }
        strongest_block = max(energies, key=energies.get)
        energy_level = energies[strongest_block]

        features = pd.DataFrame([{
            "task_type": task_type_encoded,
            "duration": float(task_row["duration_hours"]),
            "priority": int(task_row["priority"]),
            "energy_level": energy_level,
            "sleep_pattern": sleep_encoded
        }])

        pred_encoded = self.model.predict(features)[0]
        pred_block = self.time_encoder.inverse_transform([pred_encoded])[0]

        return pred_block

    def _is_slot_free(self, day, start_hour, end_hour, fixed_events, scheduled_rows):
        day_events = fixed_events[fixed_events["day"] == day]
        for _, event in day_events.iterrows():
            event_start = float(event["start_hour"])
            event_end = float(event["end_hour"])
            if not (end_hour <= event_start or start_hour >= event_end):
                return False

        for row in scheduled_rows:
            if row["day"] == day:
                sch_start = float(row["start_hour"])
                sch_end = float(row["end_hour"])
                if not (end_hour <= sch_start or start_hour >= sch_end):
                    return False

        return True

    def _find_slot_in_block(self, day, duration, block_name, fixed_events, scheduled_rows):
        block_start, block_end = self.time_blocks[block_name]

        candidate_start = block_start
        while candidate_start + duration <= block_end:
            candidate_end = candidate_start + duration

            if self._is_slot_free(day, candidate_start, candidate_end, fixed_events, scheduled_rows):
                return candidate_start, candidate_end

            candidate_start += 1

        return None, None

    def _deadline_day_rank(self, deadline_day):
        if deadline_day == "Daily":
            return -1
        if deadline_day == "Weekly":
            return 999
        return self.days_order.index(deadline_day) if deadline_day in self.days_order else 999

    def _sort_tasks(self, tasks_df):
        tasks_df = tasks_df.copy()
        tasks_df["deadline_rank"] = tasks_df["deadline_day"].apply(self._deadline_day_rank)

        tasks_df = tasks_df.sort_values(
            by=["priority", "deadline_rank", "deadline_hour"],
            ascending=[False, True, True]
        )
        return tasks_df.drop(columns=["deadline_rank"])

    def generate_weekly_schedule(self, user_profile, tasks_df, fixed_events_df):
        scheduled_rows = []

        tasks_df = self._sort_tasks(tasks_df)

        for _, task in tasks_df.iterrows():
            task_name = task["task_name"]
            duration = float(task["duration_hours"])
            preferred_block = self._predict_best_block(task, user_profile)

            if task["deadline_day"] == "Daily":
                candidate_days = self.days_order
            elif task["deadline_day"] == "Weekly":
                candidate_days = self.days_order
            else:
                deadline_idx = self.days_order.index(task["deadline_day"]) if task["deadline_day"] in self.days_order else 6
                candidate_days = self.days_order[:deadline_idx + 1]

            placed = False

            for day in candidate_days:
                start_hour, end_hour = self._find_slot_in_block(
                    day=day,
                    duration=duration,
                    block_name=preferred_block,
                    fixed_events=fixed_events_df,
                    scheduled_rows=scheduled_rows
                )

                if start_hour is not None:
                    scheduled_rows.append({
                        "day": day,
                        "start_hour": start_hour,
                        "end_hour": end_hour,
                        "task_name": task_name,
                        "category": task["category"],
                        "priority": task["priority"],
                        "deadline_day": task["deadline_day"],
                        "predicted_block": preferred_block
                    })
                    placed = True
                    break

            if not placed:
                fallback_blocks = [b for b in ["morning", "afternoon", "evening"] if b != preferred_block]

                for day in candidate_days:
                    for block in fallback_blocks:
                        start_hour, end_hour = self._find_slot_in_block(
                            day=day,
                            duration=duration,
                            block_name=block,
                            fixed_events=fixed_events_df,
                            scheduled_rows=scheduled_rows
                        )

                        if start_hour is not None:
                            scheduled_rows.append({
                                "day": day,
                                "start_hour": start_hour,
                                "end_hour": end_hour,
                                "task_name": task_name,
                                "category": task["category"],
                                "priority": task["priority"],
                                "deadline_day": task["deadline_day"],
                                "predicted_block": preferred_block
                            })
                            placed = True
                            break
                    if placed:
                        break

            if not placed:
                scheduled_rows.append({
                    "day": "Unscheduled",
                    "start_hour": None,
                    "end_hour": None,
                    "task_name": task_name,
                    "category": task["category"],
                    "priority": task["priority"],
                    "deadline_day": task["deadline_day"],
                    "predicted_block": preferred_block
                })

        schedule_df = pd.DataFrame(scheduled_rows)

        if not schedule_df.empty:
            schedule_df["day_rank"] = schedule_df["day"].apply(
                lambda d: self.days_order.index(d) if d in self.days_order else 999
            )
            schedule_df = schedule_df.sort_values(by=["day_rank", "start_hour"], na_position="last")
            schedule_df = schedule_df.drop(columns=["day_rank"])

        return schedule_df.reset_index(drop=True)