from datetime import datetime, timedelta

from fastmcp import FastMCP

mcp = FastMCP("Insomnia MCP Server 🚀")


def _GetUserInfo():
    return {
        "name": "John",
        "sleep_goal": "8 hours",
        "bedtime": "11:00 PM",
        "sleep_onset_latency": 60,
        "asleep_at": "12:00 AM",
        "wake_after_sleep_onset": 2,
        "each_night_wakes_duration": 20,
        "alarm_time": "7:30 AM",
        "terminal_wakefulness": 30,
        "out_of_bed_time": "8:00 AM",
        "feeling_tired_in_morning": True,
    }


@mcp.tool
def GetUserInfo():
    """
    Get information about the user.

    Returns:
        A dictionary containing user information.
    """
    return _GetUserInfo()


@mcp.tool
def GetSleepEfficiency():
    """
    Get the sleep efficiency of the user.

    Returns:
        The sleep efficiency of the user.
    """
    user_info = _GetUserInfo()

    # Parse time strings to datetime objects (using today as reference date)
    bedtime = datetime.strptime(user_info["bedtime"], "%I:%M %p")
    out_of_bed_time = datetime.strptime(user_info["out_of_bed_time"], "%I:%M %p")

    # Handle crossing midnight - if out_of_bed_time is earlier than bedtime, add a day
    if out_of_bed_time < bedtime:
        out_of_bed_time += timedelta(days=1)

    # Calculate time in bed in minutes
    time_in_bed = out_of_bed_time - bedtime
    time_in_bed_mins = time_in_bed.total_seconds() / 60

    # Calculate time asleep by subtracting interruptions
    total_wake_time = (
        (user_info["each_night_wakes_duration"] * user_info["wake_after_sleep_onset"])
        + user_info["terminal_wakefulness"]
        + user_info["sleep_onset_latency"]
    )
    time_asleep_mins = time_in_bed_mins - total_wake_time

    # Calculate sleep efficiency as percentage
    sleep_efficiency = (time_asleep_mins * 100) / time_in_bed_mins

    return round(sleep_efficiency, 1)


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
