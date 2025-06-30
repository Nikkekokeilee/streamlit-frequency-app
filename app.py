import pandas as pd
import requests
from datetime import datetime, timedelta, timezone
import plotly.graph_objects as go

# Define the time range: last 1 hour in UTC
now_utc = datetime.now(timezone.utc)
one_hour_ago_utc = now_utc - timedelta(hours=1)

from_str = one_hour_ago_utc.strftime("%Y-%m-%dT%H:%M:%S")
to_str = now_utc.strftime("%Y-%m-%dT%H:%M:%S")

# Statnett API URL
url = f"https://driftsdata.statnett.no/restapi/Frequency/BySecond?From={from_str}&To={to_str}"

# Fetch data from the API
response = requests.get(url)
response.raise_for_status()
data = response.json()

# Extract data
start_point_utc = data["StartPointUTC"]
period_tick_ms = data["PeriodTickMs"]
measurements = data["Measurements"]

# Calculate timestamps
start_time = datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(milliseconds=start_point_utc)
period_sec = period_tick_ms / 1000

# Create DataFrame
df = pd.DataFrame(measurements, columns=["FrequencyHz"])
df["Index"] = df.index
df["UtcTimestamp"] = df["Index"].apply(lambda i: start_time + timedelta(seconds=i * period_sec))
df["Time_10s"] = df["UtcTimestamp"].dt.floor("10S")

# Group by 10-second intervals
grouped = df.groupby("Time_10s").agg(FrequencyHz=("FrequencyHz", "mean")).reset_index()

# Display the latest entries
latest_data = grouped.tail(10)

# Plot the data
fig = go.Figure()
fig.add_trace(go.Scatter(x=grouped["Time_10s"], y=grouped["FrequencyHz"],
                         mode="lines+markers", line=dict(color="black")))
fig.update_layout(title="Statnett Grid Frequency (Last 1 Hour, 10s Averages)",
                  xaxis_title="Time (UTC)", yaxis_title="Frequency (Hz)",
                  yaxis=dict(autorange=True))

# Show the latest data and plot
print("Latest 10 entries (10s averages):")
print(latest_data)
fig.show()

