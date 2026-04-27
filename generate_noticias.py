# ============================================================
# GENERATE NOTICIAS — GitHub Actions
# Guarda noticias_data.json en el repo
# ============================================================
import json
import datetime as dt

def main():
    print("\n📡 Generando noticias_data.json...")
    try:
        from noticias import get_financial_news_for_api
        data = get_financial_news_for_api()
        if isinstance(data, dict):
            data["updated_at"] = dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        elif isinstance(data, list):
            data = {"news": data, "updated_at": dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")}
        with open("noticias_data.json", "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print("✅ noticias_data.json generado")
    except Exception as e:
        print(f"⚠ Error noticias: {e}")

if __name__ == "__main__":
    main()
