import os
import asyncio
import discord
from discord.ext import commands
from fastapi import FastAPI
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from database import guild_settings  # Ensure your imports match your start command choice

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
        print(f"✨ Synced {len(synced)} slash commands.")
    except Exception as e:
        print(f"❌ Error syncing commands: {e}")

# --- FIX: All 'await' calls are wrapped cleanly inside this async function ---
async def load_extensions():
    # If using 'cd backend' start command:
    await bot.load_extension("cogs.general") 
    
    # If using root start command, change it to:
    # await bot.load_extension("backend.cogs.general")

# FastAPI Lifespan to manage Bot startup and shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load extensions first
    await load_extensions()
    
    # Run bot in the background loop
    asyncio.create_task(bot.start(os.getenv("BOT_TOKEN")))
    yield
    await bot.close()

app = FastAPI(lifespan=lifespan)

@app.get("/")
async def root():
    return {"status": "online"}
