import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import pytz
import plotly.graph_objects as go


# Language selection
with st.sidebar:
    lang = st.selectbox("Kieli / Language", ["Suomi", "English"], index=0)

if lang == "English":
    st.set_page_config(layout="wide", page_title="Frequency (Norway & Finland)")
    st.title("📊 Frequency (Norway & Finland)")
else:
    st.set_page_config(layout="wide", page_title="Taajuus (Norja & Suomi)")
    st.title("📊 Taajuus (Norja & Suomi)")

# Tarkista API-avain
if "FINGRID_API_KEY" not in st.secrets:
    st.error("Fingridin API-avainta ei ole määritetty. Lisää se tiedostoon .streamlit/secrets.toml avaimella 'FINGRID_API_KEY'.")
    st.stop()
api_key = st.secrets["FINGRID_API_KEY"]

# Sessioasetukset ja välimuisti
if "interval" not in st.session_state:
    st.session_state.interval = "1 h"
if "auto_refresh" not in st.session_state:
    st.session_state.auto_refresh = False
if "last_updated" not in st.session_state:
    st.session_state.last_updated = None
if "data" not in st.session_state:
    st.session_state.data = None
if "last_fetch_time" not in st.session_state:
    st.session_state.last_fetch_time = datetime.min
if "data_cache" not in st.session_state:
    st.session_state.data_cache = {}

# Aikaväli ja mukautettu valinta
interval_minutes_map = {"10 min": 10, "30 min": 30, "1 h": 60, "3 h": 180}
now = datetime.utcnow()

# Sidebar for custom date/time selection and interval slider
with st.sidebar:
    st.header("Aikaväli")
    interval_options = ["10 min", "30 min", "1 h", "3 h"]
    interval_labels = {"10 min": 0, "30 min": 1, "1 h": 2, "3 h": 3}
    interval_idx = interval_labels.get(st.session_state.interval, 2)
    interval_slider = st.slider(
        "Valitse aikaväli: 0=10min, 1=30min, 2=1h, 3=3h" if lang=="Suomi" else "Select interval: 0=10min, 1=30min, 2=1h, 3=3h",
        min_value=0, max_value=3, value=interval_idx,
        step=1
    )
    selected_interval = interval_options[interval_slider]
    st.write(f"Valittu: {selected_interval}" if lang=="Suomi" else f"Selected: {selected_interval}")
    if selected_interval != st.session_state.interval:
        st.session_state.interval = selected_interval
    interval_minutes = interval_minutes_map[st.session_state.interval]
    start_time = now - timedelta(minutes=interval_minutes)
    end_time = now

    # Hae Nordicin taajuusdata

# Hae Suomen säätösähkön ylös- ja alassäätö (activated regulation power up/down)
def fetch_finnish_regulation_power():
    # Fingrid dataset 124: up, 125: down
    try:
        base_url = "https://data.fingrid.fi/api/datasets/"
        headers = {"x-api-key": api_key}
        # Up-regulation
        url_up = f"{base_url}124/data?startTime={start_time.isoformat()}Z&endTime={end_time.isoformat()}Z"
        resp_up = requests.get(url_up, headers=headers, timeout=10)
        resp_up.raise_for_status()
        data_up = resp_up.json().get("data", [])
        df_up = pd.DataFrame(data_up)
        if not df_up.empty:
            df_up["Timestamp"] = pd.to_datetime(df_up["startTime"]).dt.tz_localize(None)
            df_up = df_up[["Timestamp", "value"]].rename(columns={"value": "RegUp_MW"})
        else:
            df_up = pd.DataFrame(columns=["Timestamp", "RegUp_MW"])
        # Down-regulation
        url_down = f"{base_url}125/data?startTime={start_time.isoformat()}Z&endTime={end_time.isoformat()}Z"
        resp_down = requests.get(url_down, headers=headers, timeout=10)
        resp_down.raise_for_status()
        data_down = resp_down.json().get("data", [])
        df_down = pd.DataFrame(data_down)
        if not df_down.empty:
            df_down["Timestamp"] = pd.to_datetime(df_down["startTime"]).dt.tz_localize(None)
            df_down = df_down[["Timestamp", "value"]].rename(columns={"value": "RegDown_MW"})
        else:
            df_down = pd.DataFrame(columns=["Timestamp", "RegDown_MW"])
        # Merge up and down
        df_reg = pd.merge(df_up, df_down, on="Timestamp", how="outer").sort_values("Timestamp")
        return df_reg
    except Exception as e:
        st.error(f"Virhe haettaessa Suomen säätösähköä: {e}" if lang=="Suomi" else f"Error fetching Finnish regulation power: {e}")
        return pd.DataFrame(columns=["Timestamp", "RegUp_MW", "RegDown_MW"])
def fetch_nordic_data():
    try:
        # Statnett API only supports date, not time, so fetch for the whole day
        from_param = start_time.strftime("%Y-%m-%d")
        url = f"https://driftsdata.statnett.no/restapi/Frequency/BySecond?From={from_param}"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        start_point_utc = data["StartPointUTC"]
        period_tick_ms = data["PeriodTickMs"]
        measurements = data["Measurements"]
        if not measurements:
            st.warning("Nordicin datasta ei löytynyt mittauksia. Yritä myöhemmin uudelleen." if lang=="Suomi" else "No Nordic frequency measurements found. Try again later.")
            return pd.DataFrame()
        start_dt = datetime(1970, 1, 1) + timedelta(milliseconds=start_point_utc)
        period_sec = period_tick_ms / 1000
        df = pd.DataFrame(measurements, columns=["FrequencyHz"])
        df["Timestamp"] = [start_dt + timedelta(seconds=i * period_sec) for i in range(len(df))]
        df["Timestamp"] = pd.to_datetime(df["Timestamp"])
        df.set_index("Timestamp", inplace=True)
        df_resampled = df.resample("1min").mean().reset_index()
        # Filter to selected range
        mask = (df_resampled["Timestamp"] >= start_time) & (df_resampled["Timestamp"] <= end_time)
        return df_resampled.loc[mask].reset_index(drop=True)
    except requests.exceptions.Timeout:
        st.error("Nordicin datan haku aikakatkaistiin. Tarkista verkkoyhteys ja yritä uudelleen." if lang=="Suomi" else "Nordic frequency fetch timed out. Check your connection and try again.")
        return pd.DataFrame()
    except Exception as e:
        st.error((f"Nordicin datan haussa tapahtui virhe: {e}. Yritä päivittää sivu tai tarkista API-palvelun tila." if lang=="Suomi" else f"Error fetching Nordic frequency: {e}. Try refreshing or check the API status."))
        return pd.DataFrame()

# Hae Suomen taajuusdata
def fetch_finnish_data():
    try:
        fingrid_url = (
            f"https://data.fingrid.fi/api/datasets/177/data?"
            f"startTime={start_time.isoformat()}Z&endTime={end_time.isoformat()}Z"
        )
        headers = {"x-api-key": api_key}
        response = requests.get(fingrid_url, headers=headers, timeout=10)
        response.raise_for_status()
        fi_data = response.json()
        if "data" not in fi_data or not fi_data["data"]:
            st.warning("Suomen datasta ei löytynyt mittauksia. Yritä myöhemmin uudelleen.")
            return pd.DataFrame()
        df_fi = pd.DataFrame(fi_data["data"])
        df_fi["Timestamp"] = pd.to_datetime(df_fi["startTime"]).dt.tz_localize(None)
        df_fi["FrequencyHz"] = df_fi["value"]
        df_fi = df_fi[["Timestamp", "FrequencyHz"]]
        return df_fi
    except requests.exceptions.Timeout:
        st.error("Suomen datan haku aikakatkaistiin. Tarkista verkkoyhteys ja yritä uudelleen.")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Suomen datan haussa tapahtui virhe: {e}. Yritä päivittää sivu tai tarkista API-palvelun tila.")
        return pd.DataFrame()

# Päivitä data
def update_data(include_regulation=False):
    cache_key = (str(start_time), str(end_time), include_regulation)
    if cache_key in st.session_state.data_cache:
        st.session_state.data = st.session_state.data_cache[cache_key]
        st.session_state.last_updated = datetime.utcnow()
        st.session_state.last_fetch_time = datetime.utcnow()
        return
    with st.spinner("Haetaan dataa..."):
        df_nordic = fetch_nordic_data()
        df_finnish = fetch_finnish_data()
        if df_nordic.empty or df_finnish.empty:
            st.warning("Datan haku epäonnistui tai dataa ei löytynyt. Tarkista yhteys ja yritä uudelleen.")
            st.session_state.data = None
            return
        df_merged = pd.merge_asof(
            df_finnish.sort_values("Timestamp"),
            df_nordic.sort_values("Timestamp"),
            on="Timestamp",
            direction="nearest",
            suffixes=("_Suomi", "_Nordic")
        )
        # Only fetch regulation power if requested
        if include_regulation:
            df_reg_fi = fetch_finnish_regulation_power()
            if not df_reg_fi.empty:
                df_merged = pd.merge_asof(
                    df_merged.sort_values("Timestamp"),
                    df_reg_fi.sort_values("Timestamp"),
                    on="Timestamp",
                    direction="nearest"
                )
        st.session_state.data = df_merged
        st.session_state.data_cache[cache_key] = df_merged
        st.session_state.last_updated = datetime.utcnow()
        st.session_state.last_fetch_time = datetime.utcnow()

# Automaattinen päivitys ja päivitysvälin valinta
if 'refresh_interval' not in st.session_state:
    st.session_state.refresh_interval = 60

with st.sidebar:
    st.header("Päivitysasetukset")
    st.session_state.auto_refresh = st.checkbox("Automaattipäivitys", value=st.session_state.auto_refresh)
    st.session_state.refresh_interval = st.slider("Päivitysväli (sekuntia)", min_value=10, max_value=600, value=st.session_state.refresh_interval, step=10)

refresh_countdown = None
if st.session_state.auto_refresh:
    now = datetime.utcnow()
    elapsed = (now - st.session_state.last_fetch_time).total_seconds()
    interval = st.session_state.refresh_interval
    refresh_countdown = max(0, int(interval - elapsed))
    if elapsed > interval:
        update_data()



# Haetaan data tarvittaessa ja lisää retry-nappi, mutta estä liian tiheä päivitys
MIN_REFRESH_INTERVAL = 30  # seconds
now = datetime.utcnow()
can_refresh = (now - st.session_state.last_fetch_time).total_seconds() > MIN_REFRESH_INTERVAL
if st.session_state.data is None:
    update_data(include_regulation=False)
    if st.session_state.data is None:
        if st.button("Yritä hakea data uudelleen"):
            if can_refresh:
                update_data(include_regulation=False)
            else:
                st.warning("Päivitystä yritettiin liian nopeasti. Odota hetki ennen uutta yritystä." if lang=="Suomi" else "Refresh attempted too soon. Please wait before trying again.")

# Button to fetch regulation power data manually
if st.button("Hae säätösähkö (manuaalinen)" if lang=="Suomi" else "Fetch regulation power (manual)"):
    update_data(include_regulation=True)

# Näytä päivityslaskuri
if refresh_countdown is not None and st.session_state.auto_refresh:
    st.sidebar.info(f"Seuraava päivitys: {refresh_countdown} s")


# Ohje/info-osio
with st.expander("ℹ️ Ohjeet ja tietoa" if lang=="Suomi" else "ℹ️ Help & Info"):
    if lang == "Suomi":
        st.markdown("""
**Tietolähteet:**
- Nordicin taajuus: [Statnett Driftsdata](https://driftsdata.statnett.no/)
- Suomen taajuus: [Fingrid Datahub](https://data.fingrid.fi/)

**Päivitys:**
- Data päivittyy automaattisesti valitulla aikavälillä, tai voit päivittää manuaalisesti.

**Kuvaajan tulkinta:**
- Punainen alue: taajuus alle 49.95 Hz (alhainen)
- Sininen alue: taajuus yli 50.05 Hz (korkea)
- Voit piilottaa/näyttää käyrät ja tarkastella yhteenvetotilastoja.
        """)
    else:
        st.markdown("""
**Data sources:**
- Nordic frequency: [Statnett Driftsdata](https://driftsdata.statnett.no/)
- Finland frequency: [Fingrid Datahub](https://data.fingrid.fi/)

**Refresh:**
- Data refreshes automatically at the selected interval, or you can refresh manually.

**Chart interpretation:**
- Red area: frequency below 49.95 Hz (low)
- Blue area: frequency above 50.05 Hz (high)
- You can hide/show curves and view summary statistics.
        """)

# Näytä kuvaaja
df_merged = st.session_state.data

# Muunna aikaleimat Suomen aikaan
helsinki_tz = pytz.timezone("Europe/Helsinki")
df_merged["Timestamp_local"] = df_merged["Timestamp"].dt.tz_localize("UTC").dt.tz_convert(helsinki_tz)


# Piirrä kuvaaja
fig = go.Figure()

# Varoitusalueet
x_start = df_merged["Timestamp_local"].min()
x_end = df_merged["Timestamp_local"].max()
y_min = df_merged[["FrequencyHz_Suomi", "FrequencyHz_Nordic"]].min().min()
y_max = df_merged[["FrequencyHz_Suomi", "FrequencyHz_Nordic"]].max().max()
y_axis_min = y_min - 0.05
y_axis_max = y_max + 0.05

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

# Nordic taajuus
fig.add_trace(go.Scatter(
    x=df_merged["Timestamp_local"],
    y=df_merged["FrequencyHz_Nordic"],
    mode="lines+markers",
    name="Nordic (1 min)",
    line=dict(color="#1f77b4"),  # blue, colorblind-friendly
    visible=True,
    hovertemplate=("Aika: %{x}<br>Nordic: %{y:.3f} Hz<extra></extra>" if lang=="Suomi" else "Time: %{x}<br>Nordic: %{y:.3f} Hz<extra></extra>")
))

# Suomen taajuus
fig.add_trace(go.Scatter(
    x=df_merged["Timestamp_local"],
    y=df_merged["FrequencyHz_Suomi"],
    mode="lines+markers",
    name="Suomi (3 min)" if lang=="Suomi" else "Finland (3 min)",
    line=dict(color="#ff7f0e"),  # orange, colorblind-friendly
    visible=True,
    hovertemplate=("Aika: %{x}<br>Suomi: %{y:.3f} Hz<extra></extra>" if lang=="Suomi" else "Time: %{x}<br>Finland: %{y:.3f} Hz<extra></extra>")
))

# Suomen säätösähkö ylös (up-regulation)
if "RegUp_MW" in df_merged.columns and not df_merged["RegUp_MW"].isnull().all():
    fig.add_trace(go.Scatter(
        x=df_merged["Timestamp_local"],
        y=df_merged["RegUp_MW"],
        mode="lines+markers",
        name="Suomi säätö ylös (MW)" if lang=="Suomi" else "Finland Reg. Up (MW)",
        line=dict(color="#2ca02c", dash="dash"),  # green, dashed
        visible=True,
        yaxis="y2",
        hovertemplate=("Aika: %{x}<br>Ylös-säätö: %{y:.0f} MW<extra></extra>" if lang=="Suomi" else "Time: %{x}<br>Reg. Up: %{y:.0f} MW<extra></extra>")
    ))

# Suomen säätösähkö alas (down-regulation)
if "RegDown_MW" in df_merged.columns and not df_merged["RegDown_MW"].isnull().all():
    fig.add_trace(go.Scatter(
        x=df_merged["Timestamp_local"],
        y=df_merged["RegDown_MW"],
        mode="lines+markers",
        name="Suomi säätö alas (MW)" if lang=="Suomi" else "Finland Reg. Down (MW)",
        line=dict(color="#d62728", dash="dot"),  # red, dotted
        visible=True,
        yaxis="y2",
        hovertemplate=("Aika: %{x}<br>Alas-säätö: %{y:.0f} MW<extra></extra>" if lang=="Suomi" else "Time: %{x}<br>Reg. Down: %{y:.0f} MW<extra></extra>")
    ))

# Aikajanat
fig.update_layout(
    xaxis=dict(
        title=dict(text="Aika (Suomen aika)", font=dict(size=22)),
        tickformat="%H:%M",
        domain=[0.0, 1.0],
        anchor="y",
        tickfont=dict(size=18)
    ),
    xaxis2=dict(
        title=dict(text="Aika (UTC)", font=dict(size=20)),
        overlaying="x",
        side="top",
        tickvals=df_merged["Timestamp_local"],
        ticktext=df_merged["Timestamp"].dt.strftime("%H:%M"),
        showgrid=False,
        tickfont=dict(size=16)
    ),
    yaxis=dict(
        title=dict(text="Taajuus (Hz)", font=dict(size=22)),
        range=[y_axis_min, y_axis_max],
        tickfont=dict(size=18)
    ),
    yaxis2=dict(
        title=dict(text="Säätösähkö (MW)" if lang=="Suomi" else "Regulation Power (MW)"),
        overlaying="y",
        side="right",
        showgrid=False,
        tickfont=dict(size=16),
        anchor="x"
    ),
    height=600,
    margin=dict(t=60, b=40, l=60, r=40),
    legend=dict(
        orientation="h",
        yanchor="bottom",
        y=1.02,
        xanchor="right",
        x=1,
        font=dict(size=18)
    ),
    title=dict(
        text="Taajuusvertailu: Nordic (1 min) & Suomi (3 min)" if lang=="Suomi" else "Frequency Comparison: Nordic (1 min) & Finland (3 min)",
        font=dict(size=26)
    )
)


# Toggle traces (legend click is default in Plotly, but add checkboxes for clarity)

# Toggle traces (legend click is default in Plotly, but add checkboxes for clarity)
with st.expander("Näytä/piilota käyrät kuvaajassa" if lang=="Suomi" else "Show/hide curves in chart"):
    show_nordic = st.checkbox("Näytä Nordic", value=True)
    show_suomi = st.checkbox("Näytä Suomi" if lang=="Suomi" else "Show Finland", value=True)
    show_regup = st.checkbox("Näytä Suomi säätö ylös" if lang=="Suomi" else "Show Finland Reg. Up", value=True) if "RegUp_MW" in df_merged.columns else False
    show_regdown = st.checkbox("Näytä Suomi säätö alas" if lang=="Suomi" else "Show Finland Reg. Down", value=True) if "RegDown_MW" in df_merged.columns else False
fig.data[0].visible = show_nordic
fig.data[1].visible = show_suomi
if "RegUp_MW" in df_merged.columns and len(fig.data) > 2:
    fig.data[2].visible = show_regup
if "RegDown_MW" in df_merged.columns and len(fig.data) > 3:
    fig.data[3].visible = show_regdown

st.plotly_chart(fig, use_container_width=True)

# Summary statistics
with st.expander("📈 Yhteenveto valitulta aikaväliltä" if lang=="Suomi" else "📈 Summary for selected period"):
    st.write("**Nordic**")
    if show_nordic and not df_merged["FrequencyHz_Nordic"].isnull().all():
        st.write(f"Min: {df_merged['FrequencyHz_Nordic'].min():.3f} Hz")
        st.write(f"Max: {df_merged['FrequencyHz_Nordic'].max():.3f} Hz")
        st.write(f"Keskiarvo: {df_merged['FrequencyHz_Nordic'].mean():.3f} Hz" if lang=="Suomi" else f"Mean: {df_merged['FrequencyHz_Nordic'].mean():.3f} Hz")
        st.write(f"Keskihajonta: {df_merged['FrequencyHz_Nordic'].std():.3f} Hz" if lang=="Suomi" else f"Std: {df_merged['FrequencyHz_Nordic'].std():.3f} Hz")
    else:
        st.write("Ei dataa." if lang=="Suomi" else "No data.")
    st.write("**Suomi**" if lang=="Suomi" else "**Finland**")
    if show_suomi and not df_merged["FrequencyHz_Suomi"].isnull().all():
        st.write((f"Min: {df_merged['FrequencyHz_Suomi'].min():.3f} Hz" if lang=="Suomi" else f"Min: {df_merged['FrequencyHz_Suomi'].min():.3f} Hz"))
        st.write((f"Max: {df_merged['FrequencyHz_Suomi'].max():.3f} Hz" if lang=="Suomi" else f"Max: {df_merged['FrequencyHz_Suomi'].max():.3f} Hz"))
        st.write((f"Keskiarvo: {df_merged['FrequencyHz_Suomi'].mean():.3f} Hz" if lang=="Suomi" else f"Mean: {df_merged['FrequencyHz_Suomi'].mean():.3f} Hz"))
        st.write((f"Keskihajonta: {df_merged['FrequencyHz_Suomi'].std():.3f} Hz" if lang=="Suomi" else f"Std: {df_merged['FrequencyHz_Suomi'].std():.3f} Hz"))
    else:
        st.write("Ei dataa." if lang=="Suomi" else "No data.")

if st.session_state.last_updated:
    st.caption(f"Viimeisin päivitys: {st.session_state.last_updated.strftime('%H:%M:%S')} UTC")

# Remove settings menu (no replacement needed)
