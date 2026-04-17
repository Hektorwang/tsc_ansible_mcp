from fastapi import FastAPI
from .routes import packages

app = FastAPI()

# 注册路由
app.include_router(packages.router)

@app.get("/")
def read_root():
    return {"message": "TSC Packages API", "version": "1.0.0"}
