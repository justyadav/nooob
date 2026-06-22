import discord
from discord import app_commands
from discord.ext import commands

class Config(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def get_guild_configuration(self, guild_id: int) -> dict:
        # Resolve from fast-cache layers if current
        if guild_id in self.bot.config_cache:
            return self.bot.config_cache[guild_id]

        # Read-repair missing keys from cluster state
        doc = await self.bot.db["guild_configs"].find_one({"guild_id": guild_id})
        if doc:
            config_data = {
                "welcome_message": doc.get("welcome_message", "Welcome to the server!"),
                "leveling_enabled": doc.get("leveling_enabled", False)
            }
        else:
            config_data = {
                "welcome_message": "Welcome to the server!",
                "leveling_enabled": False
            }
        
        self.bot.config_cache[guild_id] = config_data
        return config_data

    @app_commands.command(name="config", description="Extract and read the internal DB operational parameters for this cluster.")
    @app_commands.checks.has_permissions(administrator=True)
    async def view_config(self, interaction: discord.Interaction):
        guild_id = interaction.guild_id
        config = await self.get_guild_configuration(guild_id)
        
        embed = discord.Embed(
            title=f"Configuration Diagnostics for {interaction.guild.name}",
            color=discord.Color.blue()
        )
        embed.add_field(name="Welcome System String Payload", value=f"`{config['welcome_message']}`", inline=False)
        embed.add_field(name="Leveling Subsystem Operational State", value=f"`{'ENABLED' if config['leveling_enabled'] else 'DISABLED'}`", inline=False)
        
        await interaction.response.send_message(embed=embed)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        config = await self.get_guild_configuration(member.guild.id)
        # Verify if specific default messaging targeted channels can resolve
        channel = member.guild.system_channel
        if channel and channel.permissions_for(member.guild.me).send_messages:
            msg = config["welcome_message"].replace("{user}", member.mention).replace("{server}", member.guild.name)
            await channel.send(msg)

async def setup(bot):
    await bot.add_cog(Config(bot))