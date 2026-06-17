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
from database import guild_settings  # Assumes 'cd backend' start command configuration

load_dotenv()

# 1. Initialize the Discord Bot Configuration
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"🤖 Logged in as {bot.user.name}")

async def load_extensions():
    await bot.load_extension("cogs.general")

# 2. Define the FastAPI Lifespan Handler
@asynccontextmanager
async def lifespan(app: FastAPI):
    await load_extensions()
    asyncio.create_task(bot.start(os.getenv("BOT_TOKEN")))
    yield
    await bot.close()

# 🔥 3. DEFINE 'app' FIRST (Must be done before adding any @app routes!)
app = FastAPI(lifespan=lifespan)

# Add CORS Middleware right after defining app
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 4. Define OAuth2 Variables
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI")
FRONTEND_URL = "https://your-frontend-url.onrender.com" 

# 5. NOW You Can Use @app.get / @app.post Safely
@app.get("/")
async def root():
    return {"status": "online"}

@app.get("/api/auth/login")
async def auth_login():
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
    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code.")
    # ... (rest of your callback code)
