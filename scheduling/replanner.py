import pandas as pd
from scheduling.scheduler import WeeklyScheduler


class ReplanningEngine:
    def __init__(self, scheduler=None):
        self.scheduler = scheduler if scheduler is not None else WeeklyScheduler()

        self.block_ranges = {
            "morning": (8, 12),
            "afternoon": (13, 17),
            "evening": (18, 22)
        }

    def _copy_schedule(self, schedule_df):
        return schedule_df.copy() if schedule_df is not None else pd.DataFrame()

    def _get_block_range(self, block_name):
        return self.block_ranges.get(block_name, (8, 22))

    def _find_tasks_in_range(self, schedule_df, day, start_hour, end_hour):
        affected = schedule_df[
            (schedule_df["day"] == day) &
            (schedule_df["start_hour"].notna()) &
            (schedule_df["end_hour"].notna()) &
            ~(
                (schedule_df["end_hour"] <= start_hour) |
                (schedule_df["start_hour"] >= end_hour)
            )
        ].copy()

        return affected

    def handle_wasted_time(self, schedule_df, tasks_df, fixed_events_df, user_profile,
                           day, hours_lost, block_name=None, start_hour=None):
        updated_schedule = self._copy_schedule(schedule_df)

        if updated_schedule.empty:
            return updated_schedule, pd.DataFrame(), "No existing schedule found."

        if start_hour is not None:
            disruption_start = float(start_hour)
            disruption_end = float(start_hour) + float(hours_lost)
        elif block_name is not None:
            block_start, block_end = self._get_block_range(block_name)
            disruption_start = block_start
            disruption_end = min(block_start + float(hours_lost), block_end)
        else:
            return updated_schedule, pd.DataFrame(), "Please provide either block_name or start_hour."

        affected_tasks = self._find_tasks_in_range(
            updated_schedule, day, disruption_start, disruption_end
        )

        if affected_tasks.empty:
            msg = f"No scheduled tasks were affected on {day} between {disruption_start}:00 and {disruption_end}:00."
            return updated_schedule, pd.DataFrame(), msg

        affected_task_names = affected_tasks["task_name"].tolist()

        updated_schedule = updated_schedule[
            ~(
                (updated_schedule["day"] == day) &
                (updated_schedule["task_name"].isin(affected_task_names)) &
                (updated_schedule["start_hour"].notna())
            )
        ].copy()

        affected_tasks_df = tasks_df[tasks_df["task_name"].isin(affected_task_names)].copy()

        occupied_as_events = self._schedule_to_events(updated_schedule, user_profile["user_id"])
        merged_fixed = pd.concat([fixed_events_df, occupied_as_events], ignore_index=True)

        recovery_schedule = self.scheduler.generate_weekly_schedule(
            user_profile=user_profile,
            tasks_df=affected_tasks_df,
            fixed_events_df=merged_fixed
        )

        final_schedule = pd.concat([updated_schedule, recovery_schedule], ignore_index=True)

        if not final_schedule.empty:
            day_order = self.scheduler.days_order
            final_schedule["day_rank"] = final_schedule["day"].apply(
                lambda d: day_order.index(d) if d in day_order else 999
            )
            final_schedule = final_schedule.sort_values(
                by=["day_rank", "start_hour"], na_position="last"
            ).drop(columns=["day_rank"]).reset_index(drop=True)

        msg = f"Recovered {len(affected_tasks)} affected task(s) after losing {hours_lost} hour(s) on {day}."
        return final_schedule, recovery_schedule, msg

    def handle_missed_task(self, schedule_df, tasks_df, fixed_events_df, user_profile, task_name):
        updated_schedule = self._copy_schedule(schedule_df)

        missed_rows = updated_schedule[updated_schedule["task_name"] == task_name].copy()

        if missed_rows.empty:
            return updated_schedule, pd.DataFrame(), f"Task '{task_name}' was not found in the current schedule."

        updated_schedule = updated_schedule[updated_schedule["task_name"] != task_name].copy()

        task_to_reschedule = tasks_df[tasks_df["task_name"] == task_name].copy()

        occupied_as_events = self._schedule_to_events(updated_schedule, user_profile["user_id"])
        merged_fixed = pd.concat([fixed_events_df, occupied_as_events], ignore_index=True)

        recovery_schedule = self.scheduler.generate_weekly_schedule(
            user_profile=user_profile,
            tasks_df=task_to_reschedule,
            fixed_events_df=merged_fixed
        )

        final_schedule = pd.concat([updated_schedule, recovery_schedule], ignore_index=True)

        if not final_schedule.empty:
            day_order = self.scheduler.days_order
            final_schedule["day_rank"] = final_schedule["day"].apply(
                lambda d: day_order.index(d) if d in day_order else 999
            )
            final_schedule = final_schedule.sort_values(
                by=["day_rank", "start_hour"], na_position="last"
            ).drop(columns=["day_rank"]).reset_index(drop=True)

        msg = f"Task '{task_name}' was rescheduled."
        return final_schedule, recovery_schedule, msg

    def handle_new_fixed_event(self, schedule_df, tasks_df, fixed_events_df, user_profile,
                               event_name, day, start_hour, end_hour):
        updated_events = fixed_events_df.copy()

        new_event = pd.DataFrame([{
            "event_id": int(updated_events["event_id"].max() + 1) if not updated_events.empty else 1,
            "user_id": user_profile["user_id"],
            "event_name": event_name,
            "day": day,
            "start_hour": start_hour,
            "end_hour": end_hour
        }])

        updated_events = pd.concat([updated_events, new_event], ignore_index=True)

        affected_tasks = self._find_tasks_in_range(schedule_df, day, start_hour, end_hour)

        if affected_tasks.empty:
            return schedule_df.copy(), pd.DataFrame(), updated_events, "New event added. No tasks were affected."

        affected_task_names = affected_tasks["task_name"].tolist()

        remaining_schedule = schedule_df[
            ~(
                (schedule_df["day"] == day) &
                (schedule_df["task_name"].isin(affected_task_names))
            )
        ].copy()

        affected_tasks_df = tasks_df[tasks_df["task_name"].isin(affected_task_names)].copy()

        occupied_as_events = self._schedule_to_events(remaining_schedule, user_profile["user_id"])
        merged_fixed = pd.concat([updated_events, occupied_as_events], ignore_index=True)

        recovery_schedule = self.scheduler.generate_weekly_schedule(
            user_profile=user_profile,
            tasks_df=affected_tasks_df,
            fixed_events_df=merged_fixed
        )

        final_schedule = pd.concat([remaining_schedule, recovery_schedule], ignore_index=True)

        if not final_schedule.empty:
            day_order = self.scheduler.days_order
            final_schedule["day_rank"] = final_schedule["day"].apply(
                lambda d: day_order.index(d) if d in day_order else 999
            )
            final_schedule = final_schedule.sort_values(
                by=["day_rank", "start_hour"], na_position="last"
            ).drop(columns=["day_rank"]).reset_index(drop=True)

        msg = f"New event '{event_name}' added and {len(affected_tasks)} task(s) were replanned."
        return final_schedule, recovery_schedule, updated_events, msg

    def _schedule_to_events(self, schedule_df, user_id):
        if schedule_df.empty:
            return pd.DataFrame(columns=["event_id", "user_id", "event_name", "day", "start_hour", "end_hour"])

        rows = []
        for idx, row in schedule_df.iterrows():
            if pd.notna(row["start_hour"]) and pd.notna(row["end_hour"]) and row["day"] != "Unscheduled":
                rows.append({
                    "event_id": 100000 + idx,
                    "user_id": user_id,
                    "event_name": f"Occupied: {row['task_name']}",
                    "day": row["day"],
                    "start_hour": row["start_hour"],
                    "end_hour": row["end_hour"]
                })

        return pd.DataFrame(rows)