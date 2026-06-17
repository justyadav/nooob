import os
import requests
from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import RedirectResponse

# ... (Keep your existing bot, lifespan, and database initialization here) ...

CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI") # e.g., https://enderbot-wyog.onrender.com/api/auth/callback
FRONTEND_URL = "https://your-frontend-url.onrender.com" # Update with your frontend static site URL

@app.get("/api/auth/login")
async def auth_login():
    """Redirects the user to Discord's OAuth2 authorization page."""
    discord_login_url = (
        f"https://discord.com/api/oauth2/authorize"
        f"?client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&response_type=code"
        f"&scope=identify%20guilds"
    )
    return RedirectResponse(url=discord_login_url)

@app.get("/api/auth/callback")
async def auth_callback(code: str):
    """Handles the callback from Discord, exchanges code for token, and redirects to frontend."""
    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code.")

    # Exchange code for Access Token
    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    
    token_response = requests.post("https://discord.com/api/v1/oauth2/token", data=data, headers=headers)
    if token_response.status_code != 200:
        raise HTTPException(status_code=400, detail="Failed to verify code with Discord.")
    
    tokens = token_response.json()
    access_token = tokens["access_token"]

    # Redirect user back to frontend with the access token in the URL anchor/query
    response = RedirectResponse(url=f"{FRONTEND_URL}/index.html?token={access_token}")
    return response

@app.get("/api/auth/user-guilds")
async def get_user_guilds(token: str):
    """Fetches the guilds of the logged-in user where they have ADMIN permissions."""
    headers = {"Authorization": f"Bearer {token}"}
    guilds_response = requests.get("https://discord.com/api/users/@me/guilds", headers=headers)
    
    if guilds_response.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid token or failed to fetch user guilds.")
        
    user_guilds = guilds_response.json()
    
    # Filter guilds where user has Administrator permissions (Bitwise check: 0x8)
    admin_guilds = []
    for g in user_guilds:
        permissions = int(g.get("permissions", 0))
        if (permissions & 0x8) == 0x8:
            # Check if bot is also in this guild
            bot_guild = bot.get_guild(int(g["id"]))
            admin_guilds.append({
                "id": g["id"],
                "name": g["name"],
                "icon": f"https://cdn.discordapp.com/icons/{g['id']}/{g['icon']}.png" if g["icon"] else None,
                "bot_in_guild": bot_guild is not None
            })
            
    return {"guilds": admin_guilds}
