from fastapi import FastAPI
from calculadora import calcular_todo, curva_AL, curva_GD

app = FastAPI()

@app.get("/")
def home():
    return {"status": "API funcionando"}

@app.get("/bonos")
def bonos():
    return calcular_todo()

@app.get("/curva/al")
def curva_al():
    return curva_AL()

@app.get("/curva/gd")
def curva_gd():
    return curva_GD()
