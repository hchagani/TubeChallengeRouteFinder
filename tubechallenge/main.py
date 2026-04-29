import uvicorn


def main():
    uvicorn.run(
        "tubechallenge.api.app:app",
        host="0.0.0.0",
        port=8000,
    )
