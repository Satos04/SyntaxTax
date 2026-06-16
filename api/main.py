from fastapi import FastAPI

app = FastAPI(title="SyntaxTax API", version="0.1.0")


@app.get("/ping")
def health_check():
    return {"status": "ok", "service": "syntaxtax-api"}
