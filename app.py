url = f"https://driftsdata.statnett.no/restapi/Frequency/BySecond?From={from_str}&To={to_str}"

response = requests.get(url)
response.raise_for_status()
data = response.json()

start_point_utc = data["StartPointUTC"]
period_tick_ms = data["PeriodTickMs"]
measurements = data["Measurements"]

# ✅ Tarkistus: onko dataa?
if not measurements:
    st.warning("Statnettin API ei palauttanut dataa. Yritä myöhemmin uudelleen.")
    st.stop()
