import requests
from config import DATA912_BASE_URL

def fetch_market912():
    data = {}

    for endpoint in ["arg_notes", "arg_corp", "arg_bonds"]:
        r = requests.get(f"{DATA912_BASE_URL}/{endpoint}")
        r.raise_for_status()
        data[endpoint] = r.json()

    return data
