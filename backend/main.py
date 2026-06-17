import os
import asyncio
import discord
import requests
from discord.ext import commands
from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from urllib.parse import urlencode

# ==========================================
# 1. INITIALIZATION & ENVIRONMENT SETUP
# ==========================================
load_dotenv()

CLIENT_ID = os.getenv("CLIENT_ID", "").strip()
CLIENT_SECRET = os.getenv("CLIENT_SECRET", "").strip()
REDIRECT_URI = os.getenv("REDIRECT_URI", "").strip()
FRONTEND_URL = os.getenv("FRONTEND_URL", "https://enderbot-dk9x.onrender.com").strip()

# Safely import database configurations
try:
    from database import guild_settings
except ImportError:
    print("⚠️ Warning: database.py file or guild_settings object could not be found.")

# ==========================================
# 2. DISCORD BOT CLIENT CONFIGURATION
# ==========================================
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"🤖 Logged in successfully as {bot.user.name}")
    try:
        synced = await bot.tree.sync()
        print(f"✨ Synced {len(synced)} global slash commands.")
    except Exception as e:
        print(f"❌ Slash command sync failed: {e}")

async def load_extensions():
    try:
        await bot.load_extension("cogs.general")
        print("📦 Successfully loaded cogs.general extension.")
    except Exception as e:
        print(f"⚠️ Extension load skipped or failed: {e}")

# ==========================================
# 3. FASTAPI LIFESPAN ENGINE
# ==========================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Runs during startup
    await load_extensions()
    bot_token = os.getenv("BOT_TOKEN")
    if bot_token:
        asyncio.create_task(bot.start(bot_token.strip()))
    else:
        print("❌ Error: BOT_TOKEN is missing from the environment variables.")
    yield
    # Runs during shutdown
    await bot.close()

# ==========================================
# 4. FASTAPI INSTANCE & MIDDLEWARE
# ==========================================
app = FastAPI(lifespan=lifespan)

# Setup CORS Policy explicitly for cross-domain browser requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================
# 5. API ROUTE DEFINITIONS
# ==========================================

@app.get("/")
async def root():
    """Health check endpoint to verify backend service state."""
    return {"status": "online"}

@app.get("/api/auth/login")
async def auth_login():
    """Constructs and routes to the Discord user consent interface."""
    if not CLIENT_ID or not REDIRECT_URI:
        raise HTTPException(status_code=500, detail="Backend configuration missing CLIENT_ID or REDIRECT_URI.")

    params = {
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": "identify guilds"
    }
    
    # Safely constructs clean parameters preventing string injection or structural errors
    discord_login_url = f"https://discord.com/api/oauth2/authorize?{urlencode(params)}"
    return RedirectResponse(url=discord_login_url)

@app.get("/api/auth/callback")
async def auth_callback(code: str = None):
    """Exchanges authorization code parameter responses for structural user access keys."""
    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization token parameter from client route.")

    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI
    }
    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    try:
        token_response = requests.post("https://discord.com/api/v1/oauth2/token", data=data, headers=headers)
        
        # Verbose terminal logs to reveal explicitly what parameters fail validation protocols
        if token_response.status_code != 200:
            print(f"❌ Discord API Handshake Rejected: Status {token_response.status_code}")
            print(f"❌ Discord Error Details: {token_response.text}")
            raise HTTPException(
                status_code=400, 
                detail=f"Token verification handshakes failed. Discord response: {token_response.text}"
            )
        
        tokens = token_response.json()
        access_token = tokens["access_token"]

        return RedirectResponse(url=f"{FRONTEND_URL}/index.html?token={access_token}")

    except requests.exceptions.RequestException as e:
        print(f"❌ Network error contacting Discord: {e}")
        raise HTTPException(status_code=500, detail="Internal server failed to reach Discord.")

@app.get("/api/auth/user-guilds")
async def get_user_guilds(token: str):
    """Fetches administrator dashboard metadata records managed by the requesting token session."""
    headers = {"Authorization": f"Bearer {token}"}
    guilds_response = requests.get("https://discord.com/api/users/@me/guilds", headers=headers)
    
    if guilds_response.status_code != 200:
        raise HTTPException(status_code=401, detail="Unauthorized dashboard runtime request context.")
        
    user_guilds = guilds_response.json()
    admin_guilds = []
    
    for g in user_guilds:
        permissions = int(g.get("permissions", 0))
        # Binary validation gate checking for Administrator flag bit authorization mapping
        if (permissions & 0x8) == 0x8:  
            bot_guild = bot.get_guild(int(g["id"]))
            admin_guilds.append({
                "id": g["id"],
                "name": g["name"],
                "icon": f"https://cdn.discordapp.com/icons/{g['id']}/{g['icon']}.png" if g["icon"] else None,
                "bot_in_guild": bot_guild is not None
            })
            
    return {"guilds": admin_guilds}

@app.post("/api/guild/{guild_id}/config")
async def update_guild_config(guild_id: str, data: dict):
    """Saves configured variable components directly into the persistent cluster collection storage."""
    guild = bot.get_guild(int(guild_id))
    if not guild:
        raise HTTPException(status_code=404, detail="Active Bot runtime context missing for requested target.")
    
    try:
        await guild_settings.update_one(
            {"guild_id": guild_id},
            {"$set": {"prefix": data.get("prefix", "!"), "welcome_message": data.get("welcome_message", "")}},
            upsert=True
        )
        return {"status": "success", "message": "Configuration saved cleanly to database cluster."}
    except NameError:
        raise HTTPException(status_code=501, detail="Database instance configurations are offline or unmapped.")
