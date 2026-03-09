import pandas as pd


def format_schedule_table(schedule_df):
    if schedule_df is None or schedule_df.empty:
        return pd.DataFrame(columns=["Day", "Start", "End", "Task", "Category"])

    df = schedule_df.copy()

    def fmt_hour(x):
        if pd.isna(x):
            return ""
        if float(x).is_integer():
            return f"{int(x)}:00"
        hour = int(x)
        minutes = int(round((x - hour) * 60))
        return f"{hour}:{minutes:02d}"

    formatted = pd.DataFrame({
        "Day": df["day"],
        "Start": df["start_hour"].apply(fmt_hour),
        "End": df["end_hour"].apply(fmt_hour),
        "Task": df["task_name"],
        "Category": df["category"]
    })

    return formatted