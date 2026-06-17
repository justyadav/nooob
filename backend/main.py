import os
import asyncio
import discord
from discord.ext import commands
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from database import guild_settings

load_dotenv()

# Initialize Bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"🤖 Logged in as {bot.user.name}")
    try:
        synced = await bot.tree.sync()
        print(f"✨ Synced {len(synced)} slash commands globally.")
    except Exception as e:
        print(f"❌ Error syncing commands: {e}")

# Load Cogs asynchronously
async def load_extensions():
    await bot.load_extension("cogs.general")

# FastAPI Lifespan to manage Bot startup and shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    await load_extensions()
    # Run bot in the background loop
    asyncio.create_task(bot.start(os.getenv("BOT_TOKEN")))
    yield
    await bot.close()

app = FastAPI(lifespan=lifespan)

# Enable CORS for your separate frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, replace with your Render frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- API ENDPOINTS FOR THE DASHBOARD ---

@app.get("/api/guilds")
async def get_bot_guilds():
    """Returns basic details of servers the bot is in."""
    guilds = []
    for guild in bot.guilds:
        guilds.append({
            "id": str(guild.id),
            "name": guild.name,
            "member_count": guild.member_count,
            "icon": str(guild.icon.url) if guild.icon else None
        })
    return {"guilds": guilds}

@app.post("/api/guild/{guild_id}/config")
async def update_guild_config(guild_id: str, data: dict):
    """Updates settings for a specific guild in MongoDB."""
    # Ensure bot is in that guild
    guild = bot.get_guild(int(guild_id))
    if not guild:
        raise HTTPException(status_code=404, detail="Bot is not in this guild.")
    
    # Save/Update configuration in MongoDB
    await guild_settings.update_one(
        {"guild_id": guild_id},
        {"$set": {"prefix": data.get("prefix", "!"), "welcome_message": data.get("welcome_message", "")}},
        upsert=True
    )
    return {"status": "success", "message": "Configuration updated!"}