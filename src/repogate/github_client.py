"""GitHub transport and API client for RepoGate."""

import os
from typing import Dict, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from . import __version__


class GitHubClient:
    """Minimal HTTP transport client for interacting with GitHub REST API."""

    def __init__(
        self,
        github_token: Optional[str] = None,
        proxies: Optional[Dict[str, str]] = None,
    ):
        self.token = github_token or os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
        if proxies is not None:
            self.proxies = proxies
        elif (
            os.environ.get("HTTP_PROXY")
            or os.environ.get("HTTPS_PROXY")
            or os.environ.get("ALL_PROXY")
        ):
            raw_p = (
                os.environ.get("HTTPS_PROXY")
                or os.environ.get("ALL_PROXY")
                or os.environ.get("HTTP_PROXY")
                or ""
            )
            norm_p = raw_p.replace("socks5://", "socks5h://")
            self.proxies = {"http": norm_p, "https": norm_p}
        else:
            self.proxies = None

        self.session = requests.Session()
        self.session.trust_env = False
        retries = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[500, 502, 503, 504],
        )
        self.session.mount("https://", HTTPAdapter(max_retries=retries))

    def _headers(self) -> Dict[str, str]:
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": f"RepoGate-Quality-Agent/{__version__}",
        }
        if self.token:
            headers["Authorization"] = f"token {self.token}"
        return headers

    def get(self, url: str) -> requests.Response:
        """Perform GET request with retries, headers, and proxy configuration."""
        try:
            return self.session.get(url, headers=self._headers(), proxies=self.proxies, timeout=15)
        except Exception:
            return requests.get(url, headers=self._headers(), proxies=self.proxies, timeout=15)
