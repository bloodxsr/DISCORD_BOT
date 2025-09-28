import os
import discord
from discord.ext import commands
from keep_Alive import keep_alive
import asyncio
from dotenv import load_dotenv
load_dotenv('token.env')

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    try:
        # Sync slash commands globally (no guild specified)
        await bot.tree.sync()
        
        activity = discord.Activity(type=discord.ActivityType.playing, name="with AI")
        await bot.change_presence(status=discord.Status.dnd, activity=activity)
        
        print(f"Bot extensions loaded: {list(bot.extensions.keys())}")
        print(f"Bot logged in as {bot.user} and commands synced globally")
    except Exception as e:
        print(f"Failed to sync commands globally: {e}")

async def load_extensions():
    try:
        await bot.load_extension("cogs.ai")
        print("loaded ai cog")
    except Exception as e:
        print(f"Failed to load cogs.ai: {e}")
    try:
        await bot.load_extension("cogs.moderation")  # corrected module name here
        print("loaded moderation cog")
    except Exception as e:
        print(f"Failed to load cogs.moderation: {e}")
    try:
        await bot.load_extension("cogs.automod")
        print("loaded automod cog")
    except Exception as e:
        print(f"Failed to load cogs.automod: {e}")
    try:
        await bot.load_extension("cogs.blacklist")
        print("loaded blacklist cog")
    except Exception as e:
        print(f"Failed to load cogs.blacklist: {e}")


if __name__ == "__main__":
    keep_alive()
    asyncio.run(load_extensions())

token = str(os.getenv("token"))

bot.run(token)

