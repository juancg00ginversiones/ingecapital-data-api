# ============================================================
# GENERATE FORECAST — GitHub Actions
# Guarda forecast_data.json en el repo
# ============================================================
import json
import datetime as dt

def main():
    print("\n📡 Generando forecast_data.json...")
    try:
        from forecast_cuantitativo import get_forecast_cuantitativo_for_api
        data = get_forecast_cuantitativo_for_api()
        if isinstance(data, dict):
            data["updated_at"] = dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        with open("forecast_data.json", "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print("✅ forecast_data.json generado")
    except Exception as e:
        print(f"⚠ Error forecast: {e}")

if __name__ == "__main__":
    main()
