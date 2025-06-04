from flask import Flask, render_template, request, session, redirect
import requests
from utils.flight_data import get_flights_from_opensky

app = Flask(__name__)
app.secret_key = "supersecret"

AVIATIONSTACK_API_KEY = '1111350efb2569c2bc1f04debda65b8c'

city_to_airport_code = {
    "hyderabad": "HYD",
    "mumbai": "BOM",
    "delhi": "DEL",
    "bangalore": "BLR",
    "chennai": "MAA"
}

city_coords = {
    "hyderabad": [17.385044, 78.486671],
    "mumbai": [19.076090, 72.877426],
    "delhi": [28.613939, 77.209023],
    "bangalore": [12.971599, 77.594566],
    "chennai": [13.082680, 80.270721]
}

@app.route('/')
def home():
    all_flights = get_flights_from_opensky()
    india_flights = []
    for flight in all_flights:
        if flight[2] and 'india' in flight[2].lower():
            india_flights.append({
                "callsign": flight[1],
                "origin": flight[2],
                "lat": flight[6],
                "lon": flight[5],
                "alt": flight[7],
                "speed": flight[9]
            })
    return render_template("home.html", flights=india_flights)

@app.route('/plan', methods=['GET', 'POST'])
def plan():
    country = None
    from_location = None
    to_location = None
    suggested_flights = []
    route_coords = []
    error_message = None

    if request.method == 'POST':
        country = request.form.get('country', '').strip().lower()
        from_location = request.form.get('from', '').strip().lower()
        to_location = request.form.get('to', '').strip().lower()

        if country != 'india':
            error_message = "🚫 We are working to expand our area. For now, we only show flights over India."
        else:
            dep_iata = city_to_airport_code.get(from_location)
            arr_iata = city_to_airport_code.get(to_location)

            if not dep_iata or not arr_iata:
                error_message = "Invalid city selection."
            else:
                url = f"http://api.aviationstack.com/v1/flights?access_key={AVIATIONSTACK_API_KEY}&dep_iata={dep_iata}&arr_iata={arr_iata}&flight_status=active"
                response = requests.get(url)
                data = response.json()

                if "data" in data:
                    for flight in data["data"]:
                        suggested_flights.append({
                            "callsign": flight["flight"].get("iata"),
                            "departure": flight["departure"].get("airport"),
                            "arrival": flight["arrival"].get("airport"),
                            "lat": flight["live"].get("latitude") if flight.get("live") else None,
                            "lon": flight["live"].get("longitude") if flight.get("live") else None,
                            "alt": flight["live"].get("altitude") if flight.get("live") else None,
                            "speed": flight["live"].get("speed_horizontal") if flight.get("live") else None
                        })

                if from_location in city_coords and to_location in city_coords:
                    route_coords = [city_coords[from_location], city_coords[to_location]]

                # Store last 3 searches
                history = session.get("history", [])
                history.insert(0, f"{from_location.title()} → {to_location.title()}")
                session["history"] = history[:3]

    # ✅ FINAL RETURN (always returns, even if GET)
    return render_template(
        "plan.html",
        country=country,
        from_location=from_location,
        to_location=to_location,
        suggested_flights=suggested_flights,
        error_message=error_message,
        recent_searches=session.get("history", []),
        route_coords=route_coords
    )


@app.route('/clear_history', methods=['POST'])
def clear_history():
    session.pop('history', None)
    return redirect('/plan')
@app.route('/flight/<callsign>')
def flight_detail(callsign):
    url = f"http://api.aviationstack.com/v1/flights?access_key={AVIATIONSTACK_API_KEY}&flight_iata={callsign}&limit=10"
    response = requests.get(url)
    data = response.json()

    if "data" not in data or not data["data"]:
        return f"No live data found for flight {callsign}", 404

    flight_data = data["data"][0]

    flight = {
        "callsign": callsign,
        "airline": flight_data.get("airline", {"name": "Unknown"}),
        "departure": flight_data.get("departure", {}),
        "arrival": flight_data.get("arrival", {}),
        "flight_status": flight_data.get("flight_status", "unknown")
    }

    delay = flight["departure"].get("delay", 0) or 0

    # ✅ Build real flight history from the 10 results
    history = []
    for item in data["data"]:
        scheduled = item.get("departure", {}).get("scheduled")
        delay_val = item.get("departure", {}).get("delay", 0) or 0
        history.append({
            "airline": item.get("airline", {"name": "Unknown"}),
            "departure": {
                "scheduled": scheduled,
                "delay": delay_val
            }
        })

    # ✅ Accuracy & prediction logic
    total_flights = len(history)
    delayed_flights = sum(1 for h in history if h["departure"]["delay"] and h["departure"]["delay"] > 0)
    on_time_flights = total_flights - delayed_flights

    avg_delay = round(sum(h["departure"]["delay"] for h in history) / total_flights, 1) if total_flights else 0
    accuracy_percent = round((on_time_flights / total_flights) * 100, 1) if total_flights else 0

    if avg_delay > 20:
        prediction = "🔴 Likely to be Delayed"
    elif avg_delay > 5:
        prediction = "🟡 Might be Slightly Delayed"
    else:
        prediction = "🟢 Likely On-Time"

    return render_template(
        "flight_detail.html",
        callsign=callsign,
        flight=flight,
        delay=delay,
        history=history,
        on_time_flights=on_time_flights,
        delayed_flights=delayed_flights,
        on_time_percent=accuracy_percent,
        delayed_percent=round(100 - accuracy_percent, 1),
        avg_delay=avg_delay,
        prediction=prediction
    )



if __name__ == '__main__':
    app.run(debug=True)
