import uvicorn


def main():
    uvicorn.run("web.api.app:app", host="127.0.0.1", port=8000, reload=False)


if __name__ == "__main__":
    main()
