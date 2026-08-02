import httpx


class HttpService:
    def get(self, url: str, **kwargs):
        return httpx.get(url, **kwargs)

    def post(self, url: str, **kwargs):
        return httpx.post(url, **kwargs)
