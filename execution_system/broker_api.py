"""
ASIM-Tracker: Asynchronous Broker API Connection Client
Implements OAuth/TOTP 2FA authentication, session resets, and account validation
for the National Stock Exchange of India (NSE) cash equity segment.
"""

import asyncio
import base64
import hashlib
import hmac
import logging
import socket
import struct
import time
from typing import Any, Dict, Optional
import aiohttp

import config

logger = logging.getLogger("asim_tracker.broker_api")


class BrokerAPIClient:
    """
    Asynchronous client for interacting with the broker API (Angel One V2 Publisher API).
    Includes pure-Python TOTP generation, pre-market login, and session watchdog.
    """

    def __init__(self) -> None:
        self.broker = config.BROKER_NAME
        self.client_id = config.BROKER_CLIENT_ID
        self.password = config.BROKER_PASSWORD
        self.totp_key = config.BROKER_TOTP_KEY
        self.api_key = config.BROKER_API_KEY
        self.redirect_url = config.BROKER_REDIRECT_URL

        # Session properties
        self.jwt_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.feed_token: Optional[str] = None
        self.session: Optional[aiohttp.ClientSession] = None

        # Network headers / identifiers
        self.local_ip = self._get_local_ip()
        self.public_ip = config.STATIC_IP or "127.0.0.1"  # Whitelisted static IP or local fallback
        self.mac_address = "02:00:00:00:00:00"  # standard dummy MAC address

    def _get_local_ip(self) -> str:
        """
        Resolves local IP address using socket connection.
        """
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    def generate_totp(self) -> str:
        """
        Generates RFC 6238 6-digit TOTP token using SHA-1 and 30-second steps.
        Self-contained implementation to eliminate pyotp dependency.
        """
        if not self.totp_key or "YOUR_TOTP" in self.totp_key:
            raise ValueError("Invalid BROKER_TOTP_KEY configured in environment.")

        # Clean secret key and pad base32 encoding
        secret = self.totp_key.replace(" ", "").upper()
        missing_padding = len(secret) % 8
        if missing_padding:
            secret += "=" * (8 - missing_padding)

        try:
            key = base64.b32decode(secret)
        except Exception as e:
            raise ValueError(f"Failed to base32 decode TOTP key: {e}")

        # Compute intervals count
        intervals = int(time.time() / 30)
        msg = struct.pack(">Q", intervals)

        # HMAC-SHA1 signature
        hm = hmac.new(key, msg, hashlib.sha1).digest()

        # Dynamic truncation
        offset = hm[19] & 15
        binary_code = (struct.unpack(">I", hm[offset : offset + 4])[0] & 0x7FFFFFFF) % 1000000

        return f"{binary_code:06d}"

    def get_auth_headers(self) -> Dict[str, str]:
        """
        Constructs standard authorized headers required for API requests.
        """
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-UserType": "USER",
            "X-SourceID": "WEB",
            "X-ClientLocalIP": self.local_ip,
            "X-ClientPublicIP": self.public_ip,
            "X-MACAddress": self.mac_address,
            "X-PrivateKey": self.api_key,
        }
        if self.jwt_token:
            headers["Authorization"] = f"Bearer {self.jwt_token}"
        return headers

    async def init_session(self) -> None:
        """
        Initializes aiohttp client session if not already existing.
        """
        if not self.session or self.session.closed:
            self.session = aiohttp.ClientSession()

    async def close_session(self) -> None:
        """
        Closes the active HTTP client session.
        """
        if self.session and not self.session.closed:
            await self.session.close()

    async def login(self) -> Dict[str, Any]:
        """
        Runs morning pre-market authorization. Generates TOTP code and performs
        Angel One V2 Publisher/SmartAPI login to retrieve JWT and Feed tokens.
        """
        # 1. Config Validation Check
        if not self.client_id or "YOUR_" in self.client_id:
            logger.warning("Mock mode activated: credentials set to placeholders.")
            return {"status": False, "message": "MOCK_MODE"}

        await self.init_session()

        # Generate TOTP code
        totp_code = self.generate_totp()

        url = "https://apiconnect.angelone.in/publisher-webapi/api/v1/user/login/v2"
        payload = {
            "clientcode": self.client_id,
            "password": self.password,
            "totp": totp_code,
        }

        logger.info(f"Attempting OAuth login for user {self.client_id} at {time.strftime('%H:%M:%S IST')}...")

        if not config.STATIC_IP:
            try:
                # Query public IP once dynamically if possible
                async with self.session.get("https://api.ipify.org?format=json") as ip_resp:
                    if ip_resp.status == 200:
                        ip_data = await ip_resp.json()
                        self.public_ip = ip_data.get("ip", "127.0.0.1")
            except Exception as e:
                logger.debug(f"Could not resolve public IP, using fallback: {e}")
        else:
            logger.info(f"Using statically whitelisted public IP parameter: {self.public_ip}")

        headers = self.get_auth_headers()

        async with self.session.post(url, json=payload, headers=headers) as resp:
            if resp.status != 200:
                body = await resp.text()
                raise ConnectionError(f"HTTP login failed with status {resp.status}: {body}")

            result = await resp.json()
            if not result.get("status"):
                raise PermissionError(f"Broker rejected credentials: {result.get('message')}")

            data = result.get("data", {})
            self.jwt_token = data.get("jwtToken")
            self.refresh_token = data.get("refreshToken")
            self.feed_token = data.get("feedToken")

            logger.info("Broker authentication successful. Session tokens cached.")
            return result

    async def logout(self) -> bool:
        """
        Terminates the active broker API session. Clears cached tokens.
        """
        if not self.jwt_token or not self.session:
            logger.info("No active login session to terminate.")
            return True

        url = "https://apiconnect.angelone.in/publisher-webapi/api/v1/user/logout"
        headers = self.get_auth_headers()
        payload = {"clientcode": self.client_id}

        logger.info(f"Terminating broker session for user {self.client_id}...")

        try:
            async with self.session.post(url, json=payload, headers=headers) as resp:
                result = await resp.json()
                if result.get("status"):
                    logger.info("Session terminated successfully at broker endpoint.")
                else:
                    logger.warning(f"Logout endpoint returned failure: {result.get('message')}")
        except Exception as e:
            logger.error(f"Error occurred during logout call: {e}")
        finally:
            # Reset local session keys
            self.jwt_token = None
            self.refresh_token = None
            self.feed_token = None
            await self.close_session()

        return True

    async def get_funds(self) -> Dict[str, Any]:
        """
        Queries funds and margins structure to verify session token validity.
        """
        if not self.jwt_token:
            if not self.client_id or "YOUR_" in self.client_id:
                # Return mock funds in mock mode
                return {"status": True, "data": {"net": str(config.MAX_CAPITAL)}}
            raise ConnectionError("User is not authenticated. Execute login() first.")

        url = "https://apiconnect.angelone.in/rest/secure/angelbroking/user/v1/getRMS"
        headers = self.get_auth_headers()

        async with self.session.get(url, headers=headers) as resp:
            if resp.status != 200:
                body = await resp.text()
                raise ConnectionError(f"Query funds failed: {body}")
            return await resp.json()

    def is_authenticated(self) -> bool:
        """
        Checks if the client has cached JWT tokens.
        """
        return self.jwt_token is not None
