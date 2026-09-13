import uvicorn
import os


def main():
    if os.environ.get("YUJIAN_HOST", "127.0.0.1") not in {"127.0.0.1", "localhost", "::1"} and not os.environ.get("YUJIAN_PASSWORD"):
        raise RuntimeError("局域网部署需要设置 YUJIAN_PASSWORD，登录账号为 operator。")
    uvicorn.run("web.api.app:app", host=os.environ.get("YUJIAN_HOST", "127.0.0.1"),
                port=int(os.environ.get("YUJIAN_PORT", "8000")), reload=False)


if __name__ == "__main__":
    main()
