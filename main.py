import os
import asyncio
import logging
from typing import Optional
from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import discord
from discord.ext import commands
import motor.motor_asyncio
import aiohttp
from itsdangerous import Signer, BadSignature

# --- Logging Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s:%(levelname)s:%(name)s: %(message)s')
logger = logging.getLogger("EnderBotApp")

# --- Environment Validation ---
TOKEN = os.environ.get("DISCORD_TOKEN")
CLIENT_ID = os.environ.get("CLIENT_ID")
CLIENT_SECRET = os.environ.get("CLIENT_SECRET")
REDIRECT_URI = os.environ.get("REDIRECT_URI")
MONGO_URI = os.environ.get("MONGO_URI")
SECRET_KEY = os.environ.get("SECRET_KEY", "fallback-super-secret-key")

if not all([TOKEN, CLIENT_ID, CLIENT_SECRET, REDIRECT_URI, MONGO_URI]):
    logger.critical("Missing critical environment variables! Ensure all Discord and Mongo variables are set.")

# --- Database Initialization ---
mongo_client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI)
db = mongo_client["ender_bot_db"]
config_collection = db["guild_configs"]

# --- Crypto Signer for Custom Secure Sessions ---
signer = Signer(SECRET_KEY)

# --- Discord Bot Setup ---
intents = discord.Intents.default()
intents.guilds = True
intents.members = True

class EnderBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        self.db = db
        self.config_cache = {}

    async def setup_hook(self):
        # Load Cogs
        await self.load_extension("cogs.general")
        await self.load_extension("cogs.config")
        # Sync Slash Commands
        try:
            synced = await self.tree.sync()
            logger.info(self.user)
            logger.info(f"Global Slash Commands Synced: {len(synced)} commands.")
        except Exception as e:
            logger.error(f"Failed to sync slash commands: {e}")

    async def on_ready(self):
        logger.info(f"Logged into Discord API as {self.user} (ID: {self.user.id})")

bot = EnderBot()

# --- FastAPI Web Server Setup ---
app = FastAPI(title="Ender Bot Web Dashboard")

# Ensure directories exist prior to mounting
os.makedirs("static/css", exist_ok=True)
os.makedirs("templates", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# --- Helper Functions for Session Management & Auth ---
def get_user_token(request: Request) -> Optional[str]:
    cookie = request.cookies.get("session_token")
    if not cookie:
        return None
    try:
        unsigned_token = signer.unsign(cookie).decode("utf-8")
        return unsigned_token
    except BadSignature:
        return None

async def fetch_user_guilds(token: str):
    headers = {"Authorization": f"Bearer {token}"}
    async with aiohttp.ClientSession() as session:
        async with session.get("https://discord.com/api/v10/users/@me/guilds", headers=headers) as resp:
            if resp.status == 200:
                return await resp.json()
            return None

async def fetch_user_identity(token: str):
    headers = {"Authorization": f"Bearer {token}"}
    async with aiohttp.ClientSession() as session:
        async with session.get("https://discord.com/api/v10/users/@me", headers=headers) as resp:
            if resp.status == 200:
                return await resp.json()
            return None

# --- Web Routes ---

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    token = get_user_token(request)
    user_data = None
    if token:
        user_data = await fetch_user_identity(token)
    
    # Global Bot Analytics
    guild_count = len(bot.guilds)
    user_count = sum(guild.member_count for guild in bot.guilds if guild.member_count)
    bot_ping = round(bot.latency * 1000) if bot.latency else 0

    # OAuth URL Construction
    login_url = (
        f"https://discord.com/api/oauth2/authorize?client_id={CLIENT_ID}"
        f"&redirect_uri={encode_uri(REDIRECT_URI)}&response_type=code&scope=identify%20guilds"
    )

    return templates.TemplateResponse("index.html", {
        "request": request,
        "user": user_data,
        "guild_count": guild_count,
        "user_count": user_count,
        "ping": bot_ping,
        "login_url": login_url
    })

def encode_uri(uri: str) -> str:
    import urllib.parse
    return urllib.parse.quote(uri, safe='')

@app.get("/auth/callback")
async def auth_callback(code: str):
    # Exchange Auth Code for Access Token
    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    
    async with aiohttp.ClientSession() as session:
        async with session.post("https://discord.com/api/v10/oauth2/token", data=data, headers=headers) as resp:
            token_json = await resp.json()
            access_token = token_json.get("access_token")
            
            if not access_token:
                logger.error(f"Failed to acquire access token: {token_json}")
                return RedirectResponse(url="/?error=auth_failed")
            
            # Create response and set signed session token
            response = RedirectResponse(url="/dashboard")
            signed_cookie = signer.sign(access_token.encode("utf-8")).decode("utf-8")
            response.set_cookie(key="session_token", value=signed_cookie, httponly=True, secure=True, samesite="lax")
            return response

@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/")
    response.delete_cookie("session_token")
    return response

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    token = get_user_token(request)
    if not token:
        return RedirectResponse(url="/")
    
    user_data = await fetch_user_identity(token)
    guilds_payload = await fetch_user_guilds(token)
    
    if guilds_payload is None:
        return RedirectResponse(url="/logout")

    # Filter out servers where user does not have Administrator privileges (0x8)
    manageable_guilds = []
    for g in guilds_payload:
        perms = int(g.get("permissions", 0))
        if (perms & 0x8) == 0x8:
            # Check if bot is present
            bot_guild = bot.get_guild(int(g["id"]))
            g["bot_present"] = bot_guild is not None
            manageable_guilds.append(g)

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": user_data,
        "guilds": manageable_guilds
    })

@app.post("/dashboard/update/{guild_id}")
async def update_config(guild_id: str, request: Request):
    token = get_user_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Unauthorized execution context.")
    
    # Security Validation: Confirm user owns/administers this target guild
    guilds_payload = await fetch_user_guilds(token)
    if not guilds_payload:
         raise HTTPException(status_code=403, detail="Forbidden execution environment.")
         
    target_guild = next((g for g in guilds_payload if g["id"] == guild_id), None)
    if not target_guild or (int(target_guild.get("permissions", 0)) & 0x8) != 0x8:
        raise HTTPException(status_code=403, detail="Unauthorized administrative context over target domain.")

    # Process Form Submission
    form_data = await request.form()
    welcome_message = form_data.get("welcome_message", "Welcome to the server!")
    leveling_toggle = form_data.get("leveling_enabled") == "on"

    # Persistent Write to Cluster Pipeline
    await config_collection.update_one(
        {"guild_id": int(guild_id)},
        {"$set": {
            "welcome_message": welcome_message,
            "leveling_enabled": leveling_toggle
        }},
        upsert=True
    )
    
    # Refresh Active Execution Cache Runtime Memory Loop Immediately
    bot.config_cache[int(guild_id)] = {
        "welcome_message": welcome_message,
        "leveling_enabled": leveling_toggle
    }

    return RedirectResponse(url="/dashboard?success=true", status_code=303)

# --- Server Keep-Alive Ping Endpoint ---
@app.get("/health")
async def health_check():
    return {"status": "healthy", "bot_online": bot.is_ready()}

# --- Concurrent Lifecycle Orchestration Entry ---
async def run_services():
    # Constructing Uvicorn Runtime Execution Pipeline
    import uvicorn
    config = uvicorn.Config(app=app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)), loop="asyncio")
    server = uvicorn.Server(config)
    
    # Concurrently execute both blocking loops
    await asyncio.gather(
        server.serve(),
        bot.start(TOKEN)
    )

if __name__ == "__main__":
    try:
        asyncio.run(run_services())
    except KeyboardInterrupt:
        logger.info("Application lifecycle safely terminated via interrupt invocation.")