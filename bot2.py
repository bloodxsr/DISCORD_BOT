import os
import discord
from discord.ext import commands
import asyncio
from dotenv import load_dotenv
import aiohttp
load_dotenv('token.env')

class Bot(commands.Bot):
    # Suppress error on the User attribute being None since it fills up later
    user: discord.ClientUser

    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True 
        intents.guilds = True # Needed for member join events
        super().__init__(command_prefix='-', intents=intents)

    async def setup_hook(self) -> None:
        # Create a session for making HTTP requests.
        self.session = aiohttp.ClientSession()

    async def close(self) -> None:
        # Close the session when the bot is shutting down.
        await self.session.close()
        await super().close()

    async def on_ready(self):
        activity = discord.Game(name="GOOOOFYYYY")
        await self.change_presence(status=discord.Status.do_not_disturb, activity=activity)
        print(f'Logged in as {self.user} (ID: {self.user.id})')
        print('------')

bot = Bot()
@bot.command()
async def debug(ctx):
    help_commands = [cmd for cmd in bot.commands if cmd.name == 'help']
    await ctx.send(f"Help commands found: {len(help_commands)}")


loading = ['cogs.ai', 'cogs.moderation', 'cogs.automod', 'cogs.blacklist', 'cogs.welcome', 'cogs.fun']

async def load_extensions():
    for i in loading:
        try:
            await bot.load_extension(i)
            print(f'Loaded extension: {i}')
        except Exception as e:
            print(f'Failed to load extension {i}: {e}')

if __name__ == "__main__":
    asyncio.run(load_extensions())

token = str(os.getenv("token"))

bot.run(token)

