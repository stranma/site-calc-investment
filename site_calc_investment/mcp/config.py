"""Configuration for the MCP server, loaded from environment variables."""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    """MCP server configuration from environment variables."""

    api_url: str
    api_key: str

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables.

        :raises ValueError: If required environment variables are missing.
        """
        api_url = os.environ.get("INVESTMENT_API_URL", "")
        api_key = os.environ.get("INVESTMENT_API_KEY", "")

        if not api_url:
            raise ValueError(
                "INVESTMENT_API_URL environment variable is required. "
                "Set it to the Site-Calc API URL (e.g., http://site-calc-prod-alb-xxx.elb.amazonaws.com)"
            )
        if not api_key:
            raise ValueError(
                "INVESTMENT_API_KEY environment variable is required. "
                "Set it to your investment API key (starts with 'inv_')"
            )

        return cls(api_url=api_url, api_key=api_key)
