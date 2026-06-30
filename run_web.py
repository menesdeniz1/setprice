# -*- coding: utf-8 -*-
import uvicorn

if __name__ == "__main__":
    print("SetPrice Web Uygulamasi Baslatiliyor...")
    print("Adres: http://localhost:8000")
    uvicorn.run("src.web_backend.main:app", host="127.0.0.1", port=8000, reload=True)
