import requests # type: ignore

def get_flights_from_opensky():
    url = "https://opensky-network.org/api/states/all"
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        return data.get("states", [])
    except Exception as e:
        print("Error fetching data:", e)
        return []

