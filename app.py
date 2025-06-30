import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta, timezone
import plotly.graph_objects as go

# Streamlit page config
st.set_page_config(page_title="Statnett Frequency Viewer", layout="wide")
st.title("Statnett Grid Frequency Viewer")

# Päivitä-nappi ja automaattinen päivitys 2 minuutin välein
refresh = st.button("Päivitä")
st_autorefresh = st.experimental_get_query_params().get("refresh", [None])[0]
if st_autorefresh is None:
    st.experimental_set_query_params(refresh=str(datetime.utcnow().timestamp()))

# Aikavälin valinta
interval_option = st.selectbox("Valitse aikaväli:", ["10 min", "30 min", "1 h"], index=2)
interval_minutes = {"10 min": 10, "30 min": 30, "1 h": 60}[interval_option]

# Päivitä vain, jos nappia painetaan tai 2 min kulunut
last_refresh = st.session_state.get("last_refresh", datetime.min)
now = datetime.utcnow()
if refresh or (now - last_refresh).total_seconds() > 120:
    st.session_state["last_refresh"] = now

    try:
        # Aikaväli: viimeinen 1 tunti UTC-ajassa
        now_utc = datetime.now(timezone.utc)
        one_hour_ago_utc = now_utc - timedelta(hours=1)

        from_str = one_hour_ago_utc.strftime("%Y-%m-%dT%H:%M:%S")
        to_str = now_utc.strftime("%Y-%m-%dT%H:%M:%S")

        url = f"https://driftsdata.statnett.no/restapi/Frequency/BySecond?From={from_str}&To={to_str}"
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()

        start_point_utc = data["StartPointUTC"]
        period_tick_ms = data["PeriodTickMs"]
        measurements = data["Measurements"]

        start_time = datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=start_point_utc // 1000)
        period_sec = period_tick_ms / 1000

        df = pd.DataFrame(measurements, columns=["FrequencyHz"])
        df["Index"] = df.index
        df["UtcTimestamp"] = df["Index"].apply(lambda i: start_time + timedelta(seconds=i * period_sec))
        df["Time_10s"] = df["UtcTimestamp"].dt.floor("10S")

        grouped = df.groupby("Time_10s").agg(FrequencyHz=("FrequencyHz", "mean")).reset_index()
        grouped["Color"] = grouped["FrequencyHz"].apply(lambda f: "Blue" if f >= 50 else "Red")
        grouped.rename(columns={"Time_10s": "Timestamp"}, inplace=True)

        # Rajataan näkyvä aikaväli
        cutoff_time = now_utc - timedelta(minutes=interval_minutes)
        result = grouped[grouped["Timestamp"] >= cutoff_time]

        if result.empty:
            st.warning("Ei dataa valitulla aikavälillä.")
        else:
            # Laske y-akselin rajat vain viivan perusteella
            y_min = result["FrequencyHz"].min()
            y_max = result["FrequencyHz"].max()
            y_margin = (y_max - y_min) * 0.1 if y_max > y_min else 0.05
            y_axis_min = y_min - y_margin
            y_axis_max = y_max + y_margin

            # Plotly chart
            fig = go.Figure()

            # Punainen alue: alle 49.99 Hz
            if y_axis_min < 49.99:
                fig.add_shape(
                    type="rect", xref="x", yref="y",
                    x0=result["Timestamp"].min(), x1=result["Timestamp"].max(),
                    y0=y_axis_min, y1=min(49.99, y_axis_max),
                    fillcolor="rgba(255,0,0,0.1)", line_width=0, layer="below"
                )

            # Sininen alue: yli 50.01 Hz
            if y_axis_max > 50.01:
                fig.add_shape(
                    type="rect", xref="x", yref="y",
                    x0=result["Timestamp"].min(), x1=result["Timestamp"].max(),
                    y0=max(50.01, y_axis_min), y1=y_axis_max,
                    fillcolor="rgba(0,0,255,0.1)", line_width=0, layer="below"
                )

            # Musta viiva
            fig.add_trace(go.Scatter(x=result["Timestamp"], y=result["FrequencyHz"],
                                     mode="lines+markers", line=dict(color="black")))

            fig.update_layout(
                title=f"Grid Frequency (Hz) – viimeiset {interval_option}",
                xaxis_title="Time",
                yaxis_title="Frequency (Hz)",
                yaxis=dict(range=[y_axis_min, y_axis_max])
            )

            st.plotly_chart(fig, use_container_width=True)

            # Taulukon värit ja fonttikoko
            def highlight_frequency(row):
                color = row["Color"]
                if color == "Blue":
                    bg = "background-color: rgba(0, 0, 255, 0.2)"
                else:
                    bg = "background-color: rgba(255, 0, 0, 0.2)"
                return [bg if col == "FrequencyHz" else '' for col in row.index]

            styled_df = result.copy()
            styled = styled_df.style \
                .apply(highlight_frequency, axis=1) \
                .set_properties(subset=["Timestamp", "FrequencyHz"], **{'font-size': '16px'}) \
                .hide(axis="columns", subset=["Color"])

            st.dataframe(styled, use_container_width=True)

    except Exception as e:
        st.error(f"Virhe datan haussa: {e}")
else:
    st.info("Päivitetään automaattisesti 2 minuutin välein tai paina 'Päivitä'.")

