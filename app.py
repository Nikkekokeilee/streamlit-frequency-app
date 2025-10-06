# Rajataan molemmat datat samaan aikaväliin
    filtered_fi = filtered_fi[(filtered_fi["Timestamp"] >= cutoff) & (filtered_fi["Timestamp"] <= datetime.utcnow())]
    filtered = filtered[(filtered["Timestamp"] >= cutoff) & (filtered["Timestamp"] <= datetime.utcnow())]

    # Yhdistetään aikaleimat ja taajuudet
    timestamps = pd.concat([
        filtered["Timestamp"] if show_norway else pd.Series([], dtype='datetime64[ns]'),
        filtered_fi["Timestamp"] if show_finland else pd.Series([], dtype='datetime64[ns]')
    ])
    freqs = pd.concat([
        filtered["FrequencyHz"] if show_norway else pd.Series([], dtype='float'),
        filtered_fi["FrequencyHz"] if show_finland else pd.Series([], dtype='float')
    ])

    if not timestamps.empty and not freqs.empty:
        # Määritä yhteinen aikaväli
        x_start = timestamps.min()
        x_end = timestamps.max()

        y_min = freqs.min()
        y_max = freqs.max()
        y_axis_min = y_min - 0.1
        y_axis_max = y_max + 0.1

        fig = go.Figure()

        # Varoitusalueet
        fig.add_shape(
            type="rect", xref="x", yref="y",
            x0=x_start, x1=x_end,
            y0=y_axis_min, y1=min(49.95, y_axis_max),
            fillcolor="rgba(255,0,0,0.1)", line_width=0, layer="below"
        )
        fig.add_shape(
            type="rect", xref="x", yref="y",
            x0=x_start, x1=x_end,
            y0=max(50.05, y_axis_min), y1=y_axis_max,
            fillcolor="rgba(0,0,255,0.1)", line_width=0, layer="below"
        )

        # Piirretään käyrät
        if show_norway and not filtered.empty:
            fig.add_trace(go.Scatter(
                x=filtered["Timestamp"], y=filtered["FrequencyHz"],
                mode="lines+markers", name="Norja", line=dict(color="black")
            ))

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
