import streamlit as st
import pandas as pd
import requests
import plotly.express as px

st.title("Statnett Grid Frequency Viewer")

st.markdown("""
Visualisoi sähköverkon taajuusdataa Statnettin rajapinnasta.
""")

API_URL = "https://driftsdata.statnett.no/restapi/Frequency/BySecond?From=2012-01-01"

@st.cache_data
def fetch_data():
    try:
        response = requests.get(API_URL)
        response.raise_for_status()
        data = response.json()
        df = pd.DataFrame(data)
        df['TimeStamp'] = pd.to_datetime(df['timeStamp'])
        return df
    except Exception as e:
        st.error(f"Virhe datan haussa: {e}")
        return pd.DataFrame()

df = fetch_data()

if not df.empty:
    st.success(f"Ladattu {len(df)} riviä dataa.")
    start_date = st.date_input("Aloituspäivä", df['TimeStamp'].min().date())
    end_date = st.date_input("Lopetuspäivä", df['TimeStamp'].max().date())

    mask = (df['TimeStamp'].dt.date >= start_date) & (df['TimeStamp'].dt.date <= end_date)
    filtered_df = df.loc[mask]

    fig = px.line(filtered_df, x='TimeStamp', y='Value',
                  title='Sähköverkon taajuus (Hz)',
                  labels={'TimeStamp': 'Aika', 'Value': 'Taajuus (Hz)'})
    st.plotly_chart(fig, use_container_width=True)
else:
    st.warning("Ei dataa näytettäväksi.")
