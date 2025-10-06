# Välilehdet: Taajuudet ja Asetukset
tabs = st.tabs(["Taajuudet", "Asetukset"])

with tabs[0]:
    st.subheader("📊 Taajuus (Norja & Suomi)")

    # Valintaruudut
    col1, col2 = st.columns(2)
    with col1:
        show_norway = st.checkbox("Näytä Norjan taajuus", value=True)
    with col2:
        show_finland = st.checkbox("Näytä Suomen taajuus", value=True)

    # Haetaan Suomen taajuusdata
    now = datetime.utcnow()
    start_time = now - timedelta(minutes=interval_minutes[st.session_state.interval])
    fingrid_url = (
        f"https://data.fingrid.fi/api/datasets/177/data?"
        f"startTime={start_time.isoformat()}Z&endTime={now.isoformat()}Z"
    )
    headers = {"x-api-key": api_key}
    try:
        response = requests.get(fingrid_url, headers=headers)
        response.raise_for_status()
        fi_data = response.json()
        df_fi = pd.DataFrame(fi_data["data"])
        df_fi["Timestamp"] = pd.to_datetime(df_fi["startTime"])
        df_fi["FrequencyHz"] = df_fi["value"]
        filtered_fi = df_fi[["Timestamp", "FrequencyHz"]]
    except Exception as e:
        st.error(f"Virhe haettaessa Fingridin dataa: {e}")
        filtered_fi = pd.DataFrame()

    if (show_norway and not filtered.empty) or (show_finland and not filtered_fi.empty):
        fig = go.Figure()

        # Yhdistetty aikaväli ja y-akselin rajat
        timestamps = pd.concat([
            filtered["Timestamp"] if show_norway else pd.Series(dtype='datetime64[ns]'),
            filtered_fi["Timestamp"] if show_finland else pd.Series(dtype='datetime64[ns]')
        ])
        freqs = pd.concat([
            filtered["FrequencyHz"] if show_norway else pd.Series(dtype='float'),
            filtered_fi["FrequencyHz"] if show_finland else pd.Series(dtype='float')
        ])
        if not timestamps.empty and not freqs.empty:
            y_min = freqs.min()
            y_max = freqs.max()
            y_axis_min = y_min - 0.1
            y_axis_max = y_max + 0.1

            fig.add_shape(
                type="rect", xref="x", yref="y",
                x0=timestamps.min(), x1=timestamps.max(),
                y0=y_axis_min, y1=min(49.95, y_axis_max),
                fillcolor="rgba(255,0,0,0.1)", line_width=0, layer="below"
            )

            fig.add_shape(
                type="rect", xref="x", yref="y",
                x0=timestamps.min(), x1=timestamps.max(),
                y0=max(50.05, y_axis_min), y1=y_axis_max,
                fillcolor="rgba(0,0,255,0.1)", line_width=0, layer="below"
            )

        # Norjan taajuus
        if show_norway and not filtered.empty:
            fig.add_trace(go.Scatter(
                x=filtered["Timestamp"], y=filtered["FrequencyHz"],
                mode="lines+markers", name="Norja", line=dict(color="black")
            ))

        # Suomen taajuus
        if show_finland and not filtered_fi.empty:
            fig.add_trace(go.Scatter(
                x=filtered_fi["Timestamp"], y=filtered_fi["FrequencyHz"],
                mode="lines+markers", name="Suomi", line=dict(color="green")
            ))

        fig.update_layout(
            xaxis_title="Aika (UTC)",
            yaxis_title="Taajuus (Hz)",
            height=600,
            margin=dict(t=10),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )

        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("Valitse vähintään yksi taajuusnäyttö tai varmista, että data on saatavilla.")

with tabs[1]:
    st.markdown("### ⚙️ Asetukset")
    button_cols = st.columns([1, 1, 1, 1, 2], gap="small")

    with button_cols[0]:
        if st.button("10 min"):
            st.session_state.interval = "10 min"
    with button_cols[1]:
        if st.button("30 min"):
            st.session_state.interval = "30 min"
    with button_cols[2]:
        if st.button("1 h"):
            st.session_state.interval = "1 h"
    with button_cols[3]:
        if st.button("Päivitä"):
            update_data()
    with button_cols[4]:
        st.session_state.auto_refresh = st.checkbox("Automaattipäivitys (1 min)", value=st.session_state.auto_refresh)
