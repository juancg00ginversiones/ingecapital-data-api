# ============================================================
# GENERATE SCREENER — GitHub Actions
# Guarda screener_data.json en el repo
# ============================================================
import json
import datetime as dt
import warnings
warnings.filterwarnings('ignore')

def main():
    print("\n📡 Generando screener_data.json...")
    try:
        from market_screener import get_market_screener_for_api
        data = get_market_screener_for_api()
        data["updated_at"] = dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        with open("screener_data.json", "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print("✅ screener_data.json generado")
    except Exception as e:
        print(f"⚠ Error screener: {e}")

if __name__ == "__main__":
    main()
