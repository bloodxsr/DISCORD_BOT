from discord.ext import commands
import discord
from typing import Optional

class funCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="ping")
    async def ping(self, ctx):
        latency = self.bot.latency
        await ctx.send(f"Pong! Latency: {latency*1000:.2f} ms")

    @commands.hybrid_command(name='avatar', description='Gets the profile picture of a member')
    async def avatar(self, ctx: commands.Context, member: Optional[discord.Member] = None):
        target = member or ctx.author
        
        embed = discord.Embed(
            title=f"🖼 Avatar of {target.display_name}",
            color=0x5865F2  # Use hex color for better performance
        )
        embed.set_image(url=target.display_avatar.url)
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name='slap', description='Slaps a user')
    async def slap(self, ctx: commands.Context, member: discord.Member):
        await ctx.reply(f'{ctx.author.mention} slapped {member.mention} <:skulllmaopoint:1359093554873634816>')

async def setup(bot):
    await bot.add_cog(funCog(bot))
