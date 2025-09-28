import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional, Union, Set
import os
import ast
import importlib.util
from functools import lru_cache

class ModerationCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.words_file = 'cogs/words.py'
        self._blacklist_cache: Set[str] = set()
        self._load_blacklist_on_startup()

    def _load_blacklist_on_startup(self):
        """Load blacklist once during initialization"""
        self._blacklist_cache = set(self._load_blacklist_from_file())

    @property
    def blacklist(self) -> Set[str]:
        """Get blacklist with caching"""
        return self._blacklist_cache

    def _load_blacklist_from_file(self) -> list:
        """Load blacklist from words.py file - optimized version"""
        if not os.path.exists(self.words_file):
            return []

        try:
            with open(self.words_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Fast path: try AST parsing first
            try:
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if (isinstance(node, ast.Assign) and 
                        any(isinstance(target, ast.Name) and target.id == 'blat' 
                            for target in node.targets)):
                        if isinstance(node.value, ast.List):
                            return [ast.literal_eval(elem) for elem in node.value.elts 
                                   if isinstance(elem, ast.Constant) and isinstance(elem.value, str)]
            except (SyntaxError, ValueError):
                pass
            
            # Fallback: import method
            spec = importlib.util.spec_from_file_location("words_module", self.words_file)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                return getattr(module, 'blat', [])
                
        except Exception as e:
            print(f"Error loading blacklist: {e}")
        
        return []

    def _save_blacklist(self):
        """Save blacklist and update cache"""
        try:
            blacklist_list = list(self._blacklist_cache)
            content = f"blat = {blacklist_list!r}\n"
            with open(self.words_file, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # Update AutoMod cog if present
            automod_cog = self.bot.get_cog('AutoMod')
            if automod_cog and hasattr(automod_cog, 'blacklist'):
                automod_cog.blacklist = self._blacklist_cache.copy()
                
        except IOError as e:
            print(f"Error saving blacklist: {e}")

    @lru_cache(maxsize=128)
    def _check_permissions(self, author_id: int, guild_id: int, permission: str) -> bool:
        """Cached permission checking"""
        guild = self.bot.get_guild(guild_id)
        if not guild:
            return False
        
        member = guild.get_member(author_id)
        if not member:
            return False
            
        return getattr(member.guild_permissions, permission, False)

    async def _safe_response(self, ctx_or_interaction, content: str, ephemeral: bool = False):
        """Unified response handler for both context and interactions"""
        try:
            if isinstance(ctx_or_interaction, discord.Interaction):
                if ctx_or_interaction.response.is_done():
                    await ctx_or_interaction.followup.send(content, ephemeral=ephemeral)
                else:
                    await ctx_or_interaction.response.send_message(content, ephemeral=ephemeral)
            else:  # commands.Context
                await ctx_or_interaction.send(content)
        except discord.HTTPException:
            pass  # Silently handle failed responses

    def _can_moderate(self, guild: discord.Guild, author: discord.Member, target: discord.Member) -> tuple[bool, str]:
        """Centralized moderation permission checking"""
        bot_user_id = self.bot.user.id
        
        # Basic checks
        if target.id == bot_user_id:
            return False, "I cannot moderate myself."
        if target.id == author.id:
            return False, "You cannot moderate yourself."
        if target.id == guild.owner_id:
            return False, "Cannot moderate the server owner."
        
        # Hierarchy check
        if target.top_role >= author.top_role and author.id != guild.owner_id:
            return False, "You cannot moderate someone with equal or higher role hierarchy."
        
        return True, ""

#-------------------------------------------------------------------------------------------------------------------------------------------------------------------

    @commands.hybrid_command(name="ping", description="Replies with pong!")
    async def ping(self, ctx: commands.Context):
        await ctx.reply("pong!")

#-------------------------------------------------------------------------------------------------------------------------------------------------------------------

    @commands.hybrid_command(name='slap', description='Slaps a user')
    async def slap(self, ctx: commands.Context, member: discord.Member):
        await ctx.reply(f'{ctx.author.mention} slapped {member.mention} <:skulllmaopoint:1359093554873634816>')

#-------------------------------------------------------------------------------------------------------------------------------------------------------------------

    @commands.hybrid_command(name='avatar', description='Gets the profile picture of a member')
    async def avatar(self, ctx: commands.Context, member: Optional[discord.Member] = None):
        target = member or ctx.author
        
        embed = discord.Embed(
            title=f"🖼 Avatar of {target.display_name}",
            color=0x5865F2  # Use hex color for better performance
        )
        embed.set_image(url=target.display_avatar.url)
        await ctx.send(embed=embed)

#-------------------------------------------------------------------------------------------------------------------------------------------------------------------

    @commands.hybrid_command(name="kick", description="Kick a member from the server.")
    @commands.has_permissions(kick_members=True)
    async def kick(self, ctx: commands.Context, member: discord.Member, *, reason: Optional[str] = None):
        if not ctx.guild:
            return await self._safe_response(ctx, "⚠️ This command can only be used in a server.")
        
        if not isinstance(ctx.author, discord.Member):
            return await self._safe_response(ctx, "⚠️ Could not resolve you as a server member.")

        can_moderate, error_msg = self._can_moderate(ctx.guild, ctx.author, member)
        if not can_moderate:
            return await self._safe_response(ctx, f"❌ {error_msg}")

        reason = reason or "No reason provided"
        
        try:
            await member.kick(reason=reason)
            await self._safe_response(ctx, f"✅ {member.mention} has been kicked. Reason: {reason}")
        except discord.Forbidden:
            await self._safe_response(ctx, "❌ I do not have permission to kick this member.")
        except discord.HTTPException:
            await self._safe_response(ctx, "⚠️ Failed to kick the member due to a Discord error.")

#-------------------------------------------------------------------------------------------------------------------------------------------------------------------

    @commands.hybrid_command(name="ban", description="Ban a member from the server.")
    @commands.has_permissions(ban_members=True)
    async def ban(self, ctx: commands.Context, member: discord.Member, *, reason: Optional[str] = None):
        if not ctx.guild:
            return await self._safe_response(ctx, "⚠️ This command can only be used in a server.")
        
        if not isinstance(ctx.author, discord.Member):
            return await self._safe_response(ctx, "⚠️ Could not resolve you as a server member.")

        can_moderate, error_msg = self._can_moderate(ctx.guild, ctx.author, member)
        if not can_moderate:
            return await self._safe_response(ctx, f"❌ {error_msg}")

        reason = reason or "No reason provided"
        
        try:
            await member.ban(reason=reason)
            await self._safe_response(ctx, f"✅ {member.mention} has been banned. Reason: {reason}")
        except discord.Forbidden:
            await self._safe_response(ctx, "❌ I do not have permission to ban this member.")
        except discord.HTTPException:
            await self._safe_response(ctx, "⚠️ Failed to ban the member due to a Discord error.")

#-------------------------------------------------------------------------------------------------------------------------------------------------------------------

    @commands.hybrid_command(name='mute', description='Mutes a member (requires a "MUTED" role)')
    @commands.has_permissions(manage_roles=True)
    async def mute(self, ctx: commands.Context, member: discord.Member, *, reason: Optional[str] = None):
        if not ctx.guild:
            return await self._safe_response(ctx, "⚠️ This command can only be used in a server.")
        
        if not isinstance(ctx.author, discord.Member):
            return await self._safe_response(ctx, "⚠️ Could not resolve you as a server member.")

        # Cache role lookup
        mute_role = discord.utils.get(ctx.guild.roles, name="MUTED")
        if not mute_role:
            return await self._safe_response(ctx, '❌ Create a "MUTED" role first—I can\'t find it.')

        can_moderate, error_msg = self._can_moderate(ctx.guild, ctx.author, member)
        if not can_moderate:
            return await self._safe_response(ctx, f"❌ {error_msg}")

        reason = reason or f"Muted by {ctx.author}"
        
        try:
            await member.add_roles(mute_role, reason=reason)
            await self._safe_response(ctx, f"✅ {member.mention} has been muted.")
        except discord.Forbidden:
            await self._safe_response(ctx, "❌ I do not have permission to assign roles.")
        except discord.HTTPException:
            await self._safe_response(ctx, "⚠️ Failed to mute the member.")

#-------------------------------------------------------------------------------------------------------------------------------------------------------------------

    @commands.hybrid_command(name='add_role', description='Toggles a role on a user')
    @commands.has_permissions(manage_roles=True)
    async def add_role(self, ctx: commands.Context, member: discord.Member, role: discord.Role):
        if not ctx.guild:
            return await self._safe_response(ctx, "⚠️ This command can only be used in a server.")
        
        if not isinstance(ctx.author, discord.Member):
            return await self._safe_response(ctx, "⚠️ Could not resolve you as a server member.")

        # Bot hierarchy check
        bot_member = ctx.guild.me
        if role >= bot_member.top_role:
            return await self._safe_response(ctx, "❌ I cannot manage this role (hierarchy).")
        
        # User hierarchy check
        if member.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
            return await self._safe_response(ctx, "❌ You cannot manage roles for someone with equal or higher hierarchy.")

        try:
            if role in member.roles:
                await member.remove_roles(role, reason=f'Role removed by {ctx.author}')
                await self._safe_response(ctx, f'✅ Removed {role.mention} from {member.mention}')
            else:
                await member.add_roles(role, reason=f"Role added by {ctx.author}")
                await self._safe_response(ctx, f"✅ Added {role.mention} to {member.mention}")
        except discord.Forbidden:
            await self._safe_response(ctx, "❌ I do not have permission to manage roles.")
        except discord.HTTPException:
            await self._safe_response(ctx, "⚠️ Failed to manage the role.")

#-------------------------------------------------------------------------------------------------------------------------------------------------------------------
    @commands.hybrid_command(name='unmute', description='Unmutes a member (requires a "MUTED" role)')
    @commands.has_permissions(manage_roles=True)
    async def unmute_command(self, ctx: commands.Context, member: discord.Member):
        if not ctx.guild:
            return await self._safe_response(ctx, "⚠️ This command can only be used in a server.")

        mute_role = discord.utils.get(ctx.guild.roles, name="MUTED")
        if not mute_role:
            return await self._safe_response(ctx, "⚠️ MUTE role not found.")

        if mute_role not in member.roles:
            return await self._safe_response(ctx, "❌ This member is not muted.")

        try:
            await member.remove_roles(mute_role, reason=f'Unmuted by {ctx.author}')
            await self._safe_response(ctx, f"✅ {member.mention} has been unmuted.")
        except discord.Forbidden:
            await self._safe_response(ctx, "❌ I do not have permission to remove roles.")
        except discord.HTTPException:
            await self._safe_response(ctx, "⚠️ Failed to unmute the member.")
#-------------------------------------------------------------------------------------------------------------------------------------------------------------------

async def setup(bot):
    await bot.add_cog(ModerationCog(bot))