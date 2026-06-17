import os
import discord
from discord.ext import commands
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

# MongoDB Setup
mongo_client = MongoClient(os.getenv("MONGO_URI"))
db = mongo_client["bot_database"]
settings_col = db["settings"]

# Bot Setup
intents = discord.Intents.default()
bot = commands.Bot(command_command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}")
    try:
        # Syncs slash commands globally
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(e)

# Example Slash Command reading from MongoDB
@bot.tree.command(name="status", description="Check the bot status and custom prefix")
async def status(interaction: discord.Interaction):
    # Fetch data configured via dashboard
    config = settings_col.find_one({"_id": "guild_config"}) or {"prefix": "!"}
    current_prefix = config.get("prefix", "!")
    
    await interaction.response.send_message(
        f"Hello! I am online. Current prefix managed by dashboard is: `{current_prefix}`"
    )
