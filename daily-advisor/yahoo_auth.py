"""Yahoo Fantasy API — OAuth 2.0 首次授權工具

用法：
  op run --env-file=.env -- python yahoo_auth.py

流程：
  1. 產生授權 URL → 你在瀏覽器打開
  2. 登入 Yahoo 授權 → redirect 到 localhost（頁面會打不開，正常）
  3. 從瀏覽器網址列複製 code 參數貼回來
  4. 換取 refresh token → 存到本地檔案
"""

import json
import os
import sys
import urllib.parse
import urllib.request

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TOKEN_FILE = os.path.join(SCRIPT_DIR, "yahoo_token.json")

AUTH_URL = "https://api.login.yahoo.com/oauth2/request_auth"
TOKEN_URL = "https://api.login.yahoo.com/oauth2/get_token"


def main():
    client_id = os.environ.get("YAHOO_CLIENT_ID")
    client_secret = os.environ.get("YAHOO_CLIENT_SECRET")

    if not client_id or not client_secret:
        print("YAHOO_CLIENT_ID / YAHOO_CLIENT_SECRET not set.", file=sys.stderr)
        print("Run with: op run --env-file=.env -- python yahoo_auth.py")
        sys.exit(1)

    # Step 1: Generate auth URL
    params = urllib.parse.urlencode({
        "client_id": client_id,
        "redirect_uri": "https://localhost",
        "response_type": "code",
    })
    auth_url = f"{AUTH_URL}?{params}"

    print("=" * 60)
    print("Step 1: 在瀏覽器打開以下 URL 並登入 Yahoo 授權")
    print("=" * 60)
    print()
    print(auth_url)
    print()
    print("授權後瀏覽器會跳到 https://localhost/?code=XXXX")
    print("頁面會顯示錯誤（正常），從網址列複製 code= 後面的值")
    print()

    # Step 2: Get code from user
    code = input("貼上 code 值: ").strip()
    if not code:
        print("No code provided.", file=sys.stderr)
        sys.exit(1)

    # Step 3: Exchange code for tokens
    print("\n交換 token 中...")
    data = urllib.parse.urlencode({
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": "https://localhost",
        "client_id": client_id,
        "client_secret": client_secret,
    }).encode()

    req = urllib.request.Request(
        TOKEN_URL,
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"Error {e.code}: {body}", file=sys.stderr)
        sys.exit(1)

    if "refresh_token" not in result:
        print(f"Unexpected response: {result}", file=sys.stderr)
        sys.exit(1)

    # Step 4: Save tokens
    token_data = {
        "access_token": result["access_token"],
        "refresh_token": result["refresh_token"],
        "token_type": result.get("token_type", "bearer"),
        "expires_in": result.get("expires_in", 3600),
    }

    with open(TOKEN_FILE, "w") as f:
        json.dump(token_data, f, indent=2)

    print()
    print("=" * 60)
    print(f"授權成功！Token 已存到 {TOKEN_FILE}")
    print(f"Refresh token 永不過期，之後腳本會自動 refresh")
    print("=" * 60)


if __name__ == "__main__":
    main()
