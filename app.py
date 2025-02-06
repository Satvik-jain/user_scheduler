import requests
from datetime import datetime, timedelta, timezone
from flask import Flask, request, jsonify
from zoho_auth import get_access_token
import json
import pytz

app = Flask(__name__)

ZOHO_CRM_URL = "https://www.zohoapis.in/crm/v7"
ZOHO_UNAVAILABILITY_URL = "https://www.zohoapis.in/crm/v7/settings/users_unavailability"

# Getting user id
def get_agent_user_id(property_id):
    headers = {
        "Authorization": f"Bearer {get_access_token()}",
        "Content-Type": "application/json"
    }

    url = f"{ZOHO_CRM_URL}/Listings/{property_id}"
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        data = response.json().get("data", [])
        if data:
            id = data[0].get("Property_Agent")[0].get("Property_Agent").get("id") 
            # print(id)
            return id
    return None

# Getting user's unavailable slots
def get_unavailability():
    headers = {
        "Authorization": f"Zoho-oauthtoken {get_access_token()}",
        "Content-Type": "application/json"
    }

    today_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")

    filters = {
        "group_operator": "and",
        "group": [
            {
                "comparator": "greater_equal",
                "field": {"api_name": "from"},
                "value": today_iso  
            }
        ]
    }

    params = {"filters": json.dumps(filters)}

    response = requests.get(
        "https://www.zohoapis.in/crm/v7/settings/users_unavailability",
        headers=headers,
        params=params
    )
    if response.status_code == 200:
        return response.json()
    elif response.status_code == 204:
        return {}  # (all free)
    else:
        print(f"Error fetching unavailability: {response.status_code}, {response.text}")
        return None

def find_free_slots(agent_id, unavailability_data, start_time="09:00", end_time="17:00", timezone="Asia/Kolkata"):
    local_tz = pytz.timezone(timezone)
    now = datetime.now(local_tz)
    print(now)

    today = now.strftime("%Y-%m-%d")
    tomorrow = (now + timedelta(days=1)).strftime("%Y-%m-%d")

    start_today = datetime.strptime(start_time, "%H:%M").time()
    end_today = datetime.strptime(end_time, "%H:%M").time()

    # time excedded working hour then return empty list
    if now.time() >= end_today:
        adjusted_start_today = None
    # else return next full hour and checks if it is more than the starting hour
    else:
        adjusted_start_today = max(
            now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1), 
            now.replace(hour=start_today.hour, minute=start_today.minute)
        )

    # Initialize free slots dictionary
    free_slots = {today: [], tomorrow: []}

    # If 204 response, return full working hours
    if not unavailability_data or "users_unavailability" not in unavailability_data:
        if adjusted_start_today:
            return {
                today: [{"start": adjusted_start_today.strftime("%H:%M"), "end": end_time}],
                tomorrow: [{"start": start_time, "end": end_time}]
            }
        else:
            return {today: [], tomorrow: [{"start": start_time, "end": end_time}]}

    busy_periods = {today: [], tomorrow: []}
    for entry in unavailability_data.get("users_unavailability", []):
        user = entry.get("user", {})
        if user.get("id") == agent_id: 
            from_time = entry.get("from")
            to_time = entry.get("to")
            
            if from_time and to_time:
                busy_start = datetime.fromisoformat(from_time).astimezone(local_tz)
                busy_end = datetime.fromisoformat(to_time).astimezone(local_tz)
                
                date_key = busy_start.strftime("%Y-%m-%d")

                if busy_start.time() >= end_today or busy_end.time() <= start_today:
                    continue

                busy_start = max(busy_start.time(), start_today)
                busy_end = min(busy_end.time(), end_today)
                
                if date_key in busy_periods:
                    busy_periods[date_key].append((busy_start.strftime("%H:%M"), busy_end.strftime("%H:%M")))

    for date, busy_slots in busy_periods.items():
        available_slots = []
        
        if date == today:
            if adjusted_start_today is None:
                continue
            current_time = adjusted_start_today.strftime("%H:%M")
        else:
            current_time = start_time

        for start, end in sorted(busy_slots):
            if (datetime.strptime(start, "%H:%M") - datetime.strptime(current_time, "%H:%M")).seconds / 3600 >= 1:
                available_slots.append({"start": current_time, "end": start})
            
            current_time = end 

        if (datetime.strptime(end_time, "%H:%M") - datetime.strptime(current_time, "%H:%M")).seconds / 3600 >= 1:
            available_slots.append({"start": current_time, "end": end_time})

        free_slots[date] = available_slots

    return free_slots


# Webhook to handle requests
@app.route("/get_free_slots", methods=["POST"])
def get_free_slots():
    data = request.get_json()
    print(data)
    data = data.get("args")
    property_id = data.get("property_id")

    if not property_id:
        return jsonify({"error": "Property ID is required"}), 400

    # User id
    agent_id = get_agent_user_id(property_id)
    if not agent_id:
        return jsonify({"error": "No agent assigned to this property"}), 404

    # unavailable slots
    unavailable_slots = get_unavailability()
    if unavailable_slots is None:
        return jsonify({"error": "Error fetching unavailability data"}), 500

    # available slots
    free_slots = find_free_slots(agent_id, unavailable_slots)

    return jsonify({"available_slots": free_slots})

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
