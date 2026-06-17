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

# 1. Load Environmental Variables
load_dotenv()

CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI")
FRONTEND_URL = "https://your-frontend-url.onrender.com"  # Update this with your static site link

# 2. Setup Database Connection Locally (Import safely)
from database import guild_settings

# 3. Initialize Discord Bot Architecture
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
    # Running from 'cd backend', so extensions are directly available
    await bot.load_extension("cogs.general")

# 4. Define Lifespan Event Context
@asynccontextmanager
async def lifespan(app: FastAPI):
    await load_extensions()
    asyncio.create_task(bot.start(os.getenv("BOT_TOKEN")))
    yield
    await bot.close()

# 🔥 5. INITIALIZE FASTAPI INSTANCE FIRST
app = FastAPI(lifespan=lifespan)

# Apply CORS Policy explicitly to allow frontend connection
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 🚀 6. DEFINE ALL API ROUTES SECURELY AFTER INITIALIZATION
@app.get("/")
async def root():
    return {"status": "online"}

@app.get("/api/auth/login")
async def auth_login():
    """Builds and redirects users to the Discord OAuth2 Consent screen."""
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
    """Exchanges code parameters for user session validation tokens."""
    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code token.")

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
        raise HTTPException(status_code=400, detail="Token verification handshakes failed.")
    
    tokens = token_response.json()
    access_token = tokens["access_token"]

    return RedirectResponse(url=f"{FRONTEND_URL}/index.html?token={access_token}")

@app.get("/api/auth/user-guilds")
async def get_user_guilds(token: str):
    """Fetches administrator dashboard targets mapped to currently loaded discord cache."""
    headers = {"Authorization": f"Bearer {token}"}
    guilds_response = requests.get("https://discord.com/api/users/@me/guilds", headers=headers)
    
    if guilds_response.status_code != 200:
        raise HTTPException(status_code=401, detail="Unauthorized dashboard request.")
        
    user_guilds = guilds_response.json()
    admin_guilds = []
    
    for g in user_guilds:
        permissions = int(g.get("permissions", 0))
        if (permissions & 0x8) == 0x8:  # Administrator bit mask confirmation
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
    guild = bot.get_guild(int(guild_id))
    if not guild:
        raise HTTPException(status_code=404, detail="Bot runtime context missing for guild.")
    
    await guild_settings.update_one(
        {"guild_id": guild_id},
        {"$set": {"prefix": data.get("prefix", "!"), "welcome_message": data.get("welcome_message", "")}},
        upsert=True
    )
    return {"status": "success", "message": "Configuration successfully deployed to Cluster."}
