import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import plotly.graph_objects as go

# Simulated Finnish frequency data for demonstration
now = datetime.utcnow()
minutes = 60
timestamps = pd.date_range(end=now, periods=minutes * 6, freq="10S")
frequencies = 50 + np.random.normal(0, 0.02, size=len(timestamps))
df_fi = pd.DataFrame({"Timestamp": timestamps, "FrequencyHz": frequencies})
filtered_fi = df_fi[df_fi["Timestamp"] >= now - timedelta(minutes=minutes)]

# Generate the chart
if not filtered_fi.empty:
    y_min = filtered_fi["FrequencyHz"].min()
    y_max = filtered_fi["FrequencyHz"].max()
    y_axis_min = y_min - 0.05
    y_axis_max = y_max + 0.05

    fig_fi = go.Figure()

    fig_fi.add_shape(
        type="rect", xref="x", yref="y",
        x0=filtered_fi["Timestamp"].min(), x1=filtered_fi["Timestamp"].max(),
        y0=y_axis_min, y1=min(49.97, y_axis_max),
        fillcolor="rgba(255,0,0,0.1)", line_width=0, layer="below"
    )

    fig_fi.add_shape(
        type="rect", xref="x", yref="y",
        x0=filtered_fi["Timestamp"].min(), x1=filtered_fi["Timestamp"].max(),
        y0=max(50.03, y_axis_min), y1=y_axis_max,
        fillcolor="rgba(0,0,255,0.1)", line_width=0, layer="below"
    )

    fig_fi.add_trace(go.Scatter(x=filtered_fi["Timestamp"], y=filtered_fi["FrequencyHz"],
                                mode="lines+markers", line=dict(color="black")))

    fig_fi.update_layout(
        xaxis_title="Aika (UTC)",
        yaxis_title="Taajuus (Hz)",
        height=600,
        margin=dict(t=10)
    )

    fig_fi.show()

