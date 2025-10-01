from __future__ import annotations
import discord
from discord.ext import commands
from typing import Optional, Set
import os
import ast
from functools import lru_cache
from discord import ui
import time
from datetime import timedelta



class ModerationCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.words_file = 'cogs/words.py'
        self._blacklist_cache: Set[str] = set()
        self._mute_role_cache: dict[int, discord.Role] = {}
        self._last_ping: dict[int, float] = {}  # cooldown for mention replies

        self._help_cache: dict[str, str] = {}  # cache help text strings

        self._load_blacklist_on_startup()
        self._cache_help_strings()
        self.bot.remove_command('help')

    # ---------------------- Blacklist ----------------------

    def _load_blacklist_on_startup(self):
        """Load blacklist once into memory"""
        if os.path.exists(self.words_file):
            try:
                with open(self.words_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                if "=" in content:
                    self._blacklist_cache = set(ast.literal_eval(content.split("=", 1)[1].strip()))
            except Exception as e:
                print(f"Error loading blacklist: {e}")
                self._blacklist_cache = set()

    @property
    def blacklist(self) -> Set[str]:
        return self._blacklist_cache

    def _save_blacklist(self):
        """Save blacklist quickly with overwrite"""
        try:
            with open(self.words_file, 'w', encoding='utf-8') as f:
                f.write(f"blat = {list(self._blacklist_cache)!r}")
        except IOError as e:
            print(f"Error saving blacklist: {e}")

    # ---------------------- Permissions ----------------------

    @lru_cache(maxsize=128)
    def _check_permissions(self, author_id: int, guild_id: int, permission: str) -> bool:
        guild = self.bot.get_guild(guild_id)
        if not guild:
            return False
        member = guild.get_member(author_id)
        if not member:
            return False
        return getattr(member.guild_permissions, permission, False)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        # Clear permission cache when roles/permissions change
        self._check_permissions.cache_clear()

    # ---------------------- Helpers ----------------------

    async def _safe_response(self, ctx_or_interaction, content: str, ephemeral: bool = False):
        """Unified response handler for both context and interactions"""
        try:
            if isinstance(ctx_or_interaction, discord.Interaction):
                if ctx_or_interaction.response.is_done():
                    await ctx_or_interaction.followup.send(content, ephemeral=ephemeral)
                else:
                    await ctx_or_interaction.response.send_message(content, ephemeral=ephemeral)
            else:
                await ctx_or_interaction.send(content)
        except discord.HTTPException:
            pass

    def _can_moderate(self, guild: discord.Guild, author: discord.Member, target: discord.Member) -> tuple[bool, str]:
        bot_user_id = self.bot.user.id
        if target.id == bot_user_id:
            return False, "I cannot moderate myself."
        if target.id == author.id:
            return False, "You cannot moderate yourself."
        if target.id == guild.owner_id:
            return False, "Cannot moderate the server owner."
        if target.top_role >= author.top_role and author.id != guild.owner_id:
            return False, "You cannot moderate someone with equal or higher role hierarchy."
        return True, ""

    async def _moderation_action(self, ctx, member, action, reason, success_msg, fail_perm, fail_http):
        """Wrapper to reduce duplicate code for ban/kick/etc."""
        can_moderate, error_msg = self._can_moderate(ctx.guild, ctx.author, member)
        if not can_moderate:
            return await self._safe_response(ctx, f"❌ {error_msg}")

        try:
            await action(reason=reason)
            await self._safe_response(ctx, success_msg.format(member=member, reason=reason))
        except discord.Forbidden:
            await self._safe_response(ctx, fail_perm)
        except discord.HTTPException:
            await self._safe_response(ctx, fail_http)

    def _get_mute_role(self, guild: discord.Guild) -> Optional[discord.Role]:
        """Cache and return mute role"""
        if guild.id not in self._mute_role_cache:
            role = discord.utils.find(lambda r: r.name.lower() == "muted", guild.roles)
        return self._mute_role_cache[guild.id]
    
    @commands.Cog.listener()
    async def on_blacklist_update(self, words: set[str]):
        """Update internal cache if blacklist changes in BlacklistCog."""
        self._blacklist_cache = set(words)
        self._save_blacklist()
        print(f"[ModerationCog] Blacklist updated via event: {len(words)} words")


    # ---------------------- Commands ----------------------

    @commands.hybrid_command(name="kick", description="Kick a member from the server.")
    @commands.has_permissions(kick_members=True)
    async def kick(self, ctx: commands.Context, member: discord.Member, *, reason: Optional[str] = None):
        if not ctx.guild:
            return await self._safe_response(ctx, "⚠️ Server only.")
        reason = reason or "No reason provided"
        await self._moderation_action(
            ctx, member, member.kick, reason,
            "✅ {member.mention} has been kicked. Reason: {reason}",
            "❌ I do not have permission to kick this member.",
            "⚠️ Failed to kick the member due to a Discord error."
        )

    @commands.hybrid_command(name="ban", description="Ban a member from the server.")
    @commands.has_permissions(ban_members=True)
    async def ban(self, ctx: commands.Context, member: discord.Member, *, reason: Optional[str] = None):
        if not ctx.guild:
            return await self._safe_response(ctx, "⚠️ Server only.")
        reason = reason or "No reason provided"
        await self._moderation_action(
            ctx, member, member.ban, reason,
            "✅ {member.mention} has been banned. Reason: {reason}",
            "❌ I do not have permission to ban this member.",
            "⚠️ Failed to ban the member due to a Discord error."
        )



    @commands.hybrid_command(
        name="mute",
        description="Timeouts a member for a certain duration (in minutes)"
    )
    @commands.has_permissions(moderate_members=True)
    async def mute(
        self,
        ctx: commands.Context,
        member: discord.Member,
        *,
        duration: Optional[int] = 10,  # keyword-only argument
        reason: Optional[str] = None
    ):
        """
        Timeout a member for a given duration (minutes)
        """
        if not ctx.guild:
            return await self._safe_response(ctx, "⚠️ This command can only be used in a server.")

        # Moderation check
        can_moderate, error_msg = self._can_moderate(ctx.guild, ctx.author, member) # type: ignore
        if not can_moderate:
            return await self._safe_response(ctx, f"❌ {error_msg}")

        reason = reason or f"Timed out by {ctx.author}"
        duration = duration or 10
        timeout_duration = timedelta(minutes=float(duration))

        try:
            await member.timeout(timeout_duration, reason=reason)
            await self._safe_response(ctx, f"✅ {member.mention} has been timed out for {duration} minute(s).")
        except discord.Forbidden:
            await self._safe_response(ctx, "❌ I do not have permission to timeout this member.")
        except discord.HTTPException:
            await self._safe_response(ctx, "⚠️ Failed to timeout the member.")


    @commands.hybrid_command(
        name="unmute",
        description="Removes timeout from a member"
    )
    @commands.has_permissions(moderate_members=True)
    async def unmute_command(
        self,
        ctx: commands.Context,
        member: discord.Member
    ):
        """
        Remove timeout from a member
        """
        if not ctx.guild:
            return await self._safe_response(ctx, "⚠️ This command can only be used in a server.")
    
        # Moderation check
        can_moderate, error_msg = self._can_moderate(ctx.guild, ctx.author, member) # type: ignore
        if not can_moderate:
            return await self._safe_response(ctx, f"❌ {error_msg}")
    
        if member.timed_out_until is None:
            return await self._safe_response(ctx, "❌ This member is not currently timed out.")
    
        try:
            # Remove the timeout (pass None positionally)
            await member.timeout(None, reason=f"Unmuted by {ctx.author}")
            await self._safe_response(ctx, f"✅ {member.mention} has been unmuted.")
        except discord.Forbidden:
            await self._safe_response(ctx, "❌ I do not have permission to remove the timeout.")
        except discord.HTTPException:
            await self._safe_response(ctx, "⚠️ Failed to unmute the member.")

    

    @commands.hybrid_command(name='clear', description='Delete a number of messages from the channel.')
    @commands.has_permissions(manage_messages=True)
    async def clear(self, ctx: commands.Context, amount: int = 10):
        if not ctx.guild:
            return await self._safe_response(ctx, "⚠️ Server only.")
        if amount <= 0:
            return await self._safe_response(ctx, "❌ Please provide a valid number of messages to delete.")
        try:
            deleted = await ctx.channel.purge(limit=amount) # type: ignore
            await self._safe_response(ctx, f"✅ Successfully deleted {len(deleted)} message(s).")
        except discord.Forbidden:
            await self._safe_response(ctx, "❌ I do not have permission to manage messages.")
        except discord.HTTPException as e:
            await self._safe_response(ctx, f"⚠️ Failed to delete messages: {e}")

    # ---------------------- Events ----------------------

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author == self.bot.user:
            return
        # Reply when bot is pinged, but with cooldown
        if self.bot.user in message.mentions:
            now = time.time()
            last = self._last_ping.get(message.author.id, 0)
            if now - last > 5:  # 5s cooldown
                await message.channel.send(f"Hello {message.author.mention}! How can I help you?")
                self._last_ping[message.author.id] = now
        await self.bot.process_commands(message)

    # ---------------------- Help System ----------------------

    def _cache_help_strings(self):
        """Precompute help texts so they aren’t rebuilt every time"""
        self._help_cache = {
            'main': (
                "🤖 **Bot Help Menu**\n\n"
                "Select a category below to see available commands!\n\n"
                "📚 **Categories:**\n"
                "• **Fun** - Entertainment commands\n"
                "• **Utility** - Useful tools\n"
                "• **Moderation** - Server management\n"
                "• **Info** - Information commands\n\n"
                "Use the buttons below to navigate!"
            ),
            'fun': (
                "🎮 **Fun Commands**\n\n"
                "**`-joke`** - Tells a random joke\n"
                "**`-meme`** - Sends a random meme\n"
                "**`-8ball <question>`** - Ask the magic 8ball\n"
                "**`-trivia`** - Start a trivia game"
            ),
            'utility': (
                "🔧 **Utility Commands**\n\n"
                "**`-ping`** - Check latency\n"
                "**`-ask <question>`** - Ask the bot a question\n"
                "**`-serverinfo`** - Server info\n"
                "**`-userinfo [@user]`** - User info"
            ),
            'moderation': (
                "🛡️ **Moderation Commands**\n\n"
                "**`-kick @user [reason]`** - Kick a user\n"
                "**`-ban @user [reason]`** - Ban a user\n"
                "**`-clear <amount>`** - Bulk delete messages\n"
                "**`-mute @user`** - Mute a user\n"
                "**`-unmute @user`** - Unmute a user"
            ),
            'info': (
                "ℹ️ **Information Commands**\n\n"
                "**`-userinfo [@user]`** - User info\n"
                "**`-avatar [@user]`** - Avatar\n"
                "**`-botinfo`** - Bot info\n"
                "**`-serverinfo`** - Server info"
            )
        }

    @commands.command(name='help', aliases=['h'])
    async def help_command(self, ctx, *, category: str = None): # type: ignore
        view = HelpLayoutView(self.bot, self._help_cache)
        if category:
            category = category.lower()
            if category in ['fun', 'game', 'games']:
                view.help_text.content = self._help_cache['fun']
            elif category in ['utility', 'util', 'tools']:
                view.help_text.content = self._help_cache['utility']
            elif category in ['mod', 'moderation', 'admin']:
                view.help_text.content = self._help_cache['moderation']
            elif category in ['info', 'information']:
                view.help_text.content = self._help_cache['info']
        await ctx.send(view=view)


# ---------------------- Help Layout Views ----------------------

class HelpButtons(ui.ActionRow):
    def __init__(self, parent_view: 'HelpLayoutView') -> None:
        super().__init__()
        self.parent_view = parent_view

    @ui.button(label='🎮 Fun', style=discord.ButtonStyle.secondary)
    async def fun_button(self, interaction: discord.Interaction, button: ui.Button) -> None:
        self.parent_view.help_text.content = self.parent_view.help_cache['fun']
        await interaction.response.edit_message(view=self.parent_view)

    @ui.button(label='🔧 Utility', style=discord.ButtonStyle.secondary)
    async def utility_button(self, interaction: discord.Interaction, button: ui.Button) -> None:
        self.parent_view.help_text.content = self.parent_view.help_cache['utility']
        await interaction.response.edit_message(view=self.parent_view)

    @ui.button(label='🛡️ Moderation', style=discord.ButtonStyle.secondary)
    async def mod_button(self, interaction: discord.Interaction, button: ui.Button) -> None:
        self.parent_view.help_text.content = self.parent_view.help_cache['moderation']
        await interaction.response.edit_message(view=self.parent_view)

    @ui.button(label='ℹ️ Info', style=discord.ButtonStyle.secondary)
    async def info_button(self, interaction: discord.Interaction, button: ui.Button) -> None:
        self.parent_view.help_text.content = self.parent_view.help_cache['info']
        await interaction.response.edit_message(view=self.parent_view)


class HelpNavigationButtons(ui.ActionRow):
    def __init__(self, parent_view: 'HelpLayoutView') -> None:
        super().__init__()
        self.parent_view = parent_view

    @ui.button(label='🏠 Home', style=discord.ButtonStyle.secondary)
    async def home_button(self, interaction: discord.Interaction, button: ui.Button) -> None:
        self.parent_view.help_text.content = self.parent_view.help_cache['main']
        await interaction.response.edit_message(view=self.parent_view)

    @ui.button(label='❌ Close', style=discord.ButtonStyle.danger)
    async def close_button(self, interaction: discord.Interaction, button: ui.Button) -> None:
        await interaction.message.delete() #type: ignore
        await interaction.response.edit_message(content="Help menu closed.", view=None)


class HelpLayoutView(ui.LayoutView):
    def __init__(self, bot: commands.Bot, help_cache: dict[str, str]) -> None:
        super().__init__()
        self.bot = bot
        self.help_cache = help_cache
        self.help_text = ui.TextDisplay(help_cache['main'])

        container = ui.Container(
            self.help_text,
            ui.Separator(),
            HelpButtons(self),
            HelpNavigationButtons(self),
            accent_color=discord.Color.pink()
        )
        self.add_item(container)


# ---------------------- Setup ----------------------

async def setup(bot):
    await bot.add_cog(ModerationCog(bot))
