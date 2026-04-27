# ============================================================
# GENERATE DÓLARES — GitHub Actions
# Guarda dolares_data.json en el repo
# ============================================================
import json
import datetime as dt

def main():
    print("\n📡 Generando dolares_data.json...")
    try:
        from dolares import get_dolares_for_api
        data = get_dolares_for_api()
        if isinstance(data, dict):
            data["updated_at"] = dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        with open("dolares_data.json", "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print("✅ dolares_data.json generado")
    except Exception as e:
        print(f"⚠ Error dolares: {e}")

if __name__ == "__main__":
    main()
