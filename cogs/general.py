import discord
from discord import app_commands
from discord.ext import commands

class General(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="ping", description="Retrieves the current network operational latency thresholds.")
    async def ping(self, interaction: discord.Interaction):
        latency = round(self.bot.latency * 1000)
        await interaction.response.send_message(f"🏓 **Pong!** Latency metrics clocked at `{latency}ms`.")

    @app_commands.command(name="info", description="Exposes historical, runtime configuration parameters about Ender Bot.")
    async def info(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="Ender Bot Core Telemetry Data", 
            color=discord.Color.dark_purple()
        )
        embed.add_field(name="Infrastructure Core Node", value="Python & Discord.py v2", inline=True)
        embed.add_field(name="Total Managed Clusters", value=str(len(self.bot.guilds)), inline=True)
        embed.set_footer(text="Designed for high-throughput, real-time distributed application logic.")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="help", description="Displays functional matrix operations guide.")
    async def help_command(self, interaction: discord.Interaction):
        help_text = (
            "### Available Application Core Interfaces:\n"
            "`/ping` - Analyze platform socket responses.\n"
            "`/info` - Inspect active environment attributes.\n"
            "`/config` - Print localized persistence cache map values."
        )
        await interaction.response.send_message(help_text, ephemeral=True)

async def setup(bot):
    await bot.add_cog(General(bot))