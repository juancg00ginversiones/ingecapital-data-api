# contenido_pro.py

import json
import os
from datetime import datetime
from fastapi import HTTPException

# Archivo local donde se guardan las publicaciones
RUTA_DB = "contenido_pro.json"


def cargar_db():
    """
    Carga la base de datos de contenido PRO.
    Si no existe, devuelve una lista vacía.
    """
    if not os.path.exists(RUTA_DB):
        return []
    try:
        with open(RUTA_DB, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def guardar_db(data):
    """
    Guarda la base de datos completa en formato JSON.
    """
    with open(RUTA_DB, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def agregar_contenido(titulo, texto, imagen_url, fecha):
    """
    Agrega una nueva publicación al JSON.
    Verifica formato de fecha y campos obligatorios.
    """
    # Validación de fecha (YYYY-MM-DD)
    try:
        datetime.strptime(fecha, "%Y-%m-%d")
    except Exception:
        raise HTTPException(status_code=400, detail="Formato de fecha inválido. Use YYYY-MM-DD")

    if not titulo or not texto:
        raise HTTPException(status_code=400, detail="Título y texto son obligatorios.")

    data = cargar_db()

    nuevo = {
        "titulo": titulo,
        "texto": texto,
        "imagen_url": imagen_url,
        "fecha": fecha
    }

    data.append(nuevo)
    guardar_db(data)

    return {"status": "ok", "mensaje": "Contenido agregado correctamente"}


def obtener_contenido():
    """
    Devuelve todas las publicaciones, ordenadas por fecha descendente.
    """
    data = cargar_db()

    # Ordenar por fecha más reciente primero
    try:
        data = sorted(data, key=lambda x: x["fecha"], reverse=True)
    except Exception:
        pass

    return data
