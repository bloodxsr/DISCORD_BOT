from __future__ import annotations
import discord
from discord.ext import commands
from typing import Optional, Union, Set
import os
import ast
import importlib.util
from functools import lru_cache
from discord import ui



class ModerationCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.words_file = 'cogs/words.py'
        self._blacklist_cache: Set[str] = set()
        self._load_blacklist_on_startup()
        self.bot.remove_command('help')

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
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author == self.bot.user:
            return
        if self.bot.user in message.mentions:
            await message.channel.send(f"Hello {message.author.mention}! How can I help you?")
        await self.bot.process_commands(message)


#-------------------------------------------------------------------------------------------------------------------------------------------------------------------
# HELP WITHIN CONTAINER
    @commands.command(name='help', aliases=['h'])
    async def help_command(self, ctx, *, category: str = None): # type: ignore
        """
        Display the help menu with all available commands.
        
        Usage:
            -help - Show interactive help menu
            -help fun - Show fun commands directly
        """
        view = HelpLayoutView(self.bot)
        
        # If a specific category is requested, update to that page
        if category:
            category = category.lower()
            if category in ['fun', 'game', 'games']:
                view.help_text.content = view.get_content('fun')
            elif category in ['utility', 'util', 'tools']:
                view.help_text.content = view.get_content('utility')
            elif category in ['mod', 'moderation', 'admin']:
                view.help_text.content = view.get_content('moderation')
            elif category in ['info', 'information']:
                view.help_text.content = view.get_content('info')
        
        # LayoutViews cannot be sent with regular content or embeds
        await ctx.send(view=view)

    @commands.command(name='cmds')
    async def commands_list(self, ctx):
        """Quick list of all commands using LayoutView."""
        view = CommandsListLayoutView(self.bot)
        await ctx.send(view=view)

    @commands.command(name='botinfo')
    async def botinfo_command(self, ctx):
        """Display information about the bot using LayoutView."""
        view = BotInfoLayoutView(self.bot)
        await ctx.send(view=view)


class HelpButtons(ui.ActionRow):
    """Action row containing navigation buttons for help menu."""
    
    def __init__(self, parent_view: 'HelpLayoutView') -> None:
        super().__init__()
        self.parent_view = parent_view

    @ui.button(label='🎮 Fun', style=discord.ButtonStyle.secondary)
    async def fun_button(self, interaction: discord.Interaction, button: ui.Button) -> None:
        self.parent_view.help_text.content = self.parent_view.get_content('fun')
        await interaction.response.edit_message(view=self.parent_view)

    @ui.button(label='🔧 Utility', style=discord.ButtonStyle.secondary)
    async def utility_button(self, interaction: discord.Interaction, button: ui.Button) -> None:
        self.parent_view.help_text.content = self.parent_view.get_content('utility')
        await interaction.response.edit_message(view=self.parent_view)

    @ui.button(label='🛡️ Moderation', style=discord.ButtonStyle.secondary)
    async def mod_button(self, interaction: discord.Interaction, button: ui.Button) -> None:
        self.parent_view.help_text.content = self.parent_view.get_content('moderation')
        await interaction.response.edit_message(view=self.parent_view)

    @ui.button(label='ℹ️ Info', style=discord.ButtonStyle.secondary)
    async def info_button(self, interaction: discord.Interaction, button: ui.Button) -> None:
        self.parent_view.help_text.content = self.parent_view.get_content('info')
        await interaction.response.edit_message(view=self.parent_view)


class HelpNavigationButtons(ui.ActionRow):
    """Action row for home and close buttons."""
    
    def __init__(self, parent_view: 'HelpLayoutView') -> None:
        super().__init__()
        self.parent_view = parent_view

    @ui.button(label='🏠 Home', style=discord.ButtonStyle.secondary)
    async def home_button(self, interaction: discord.Interaction, button: ui.Button) -> None:
        self.parent_view.help_text.content = self.parent_view.get_content('main')
        await interaction.response.edit_message(view=self.parent_view)

    @ui.button(label='❌ Close', style=discord.ButtonStyle.danger)
    async def close_button(self, interaction: discord.Interaction, button: ui.Button) -> None:
        await interaction.response.edit_message(content="Help menu closed.", view=None)


class HelpLayoutView(ui.LayoutView):
    """LayoutView for interactive help menu using Container."""
    
    def __init__(self, bot: commands.Bot) -> None:
        super().__init__()
        self.bot = bot
        self.current_page = 'main'
        
        # Create text display for content
        self.help_text = ui.TextDisplay(self.get_content('main'))
        
        # Create separator
        separator = ui.Separator()
        
        # Create button rows
        self.category_buttons = HelpButtons(self)
        self.nav_buttons = HelpNavigationButtons(self)
        
        # Create container with all components
        container = ui.Container(
            self.help_text,
            separator,
            self.category_buttons,
            self.nav_buttons,
            accent_color=discord.Color.pink()
        )
        
        self.add_item(container)

    def get_content(self, page: str) -> str:
        """Get content for a specific page."""
        contents = {
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
                "Entertainment and game commands\n\n"
                "**`-joke`**\n"
                "Tells a random joke\n\n"
                "**`-meme`**\n"
                "Sends a random meme\n\n"
                "**`-8ball <question>`**\n"
                "Ask the magic 8ball a question\n\n"
                "**`-trivia`**\n"
                "Start a trivia game"
            ),
            'utility': (
                "🔧 **Utility Commands**\n\n"
                "Useful tools and utilities\n\n"
                "**`-ping`**\n"
                "Check bot's response time\n\n"
                "**`-ask <question>`**\n"
                "Ask the bot a question\n\n"
                "**`-serverinfo`**\n"
                "Get information about the server\n\n"
                "**`-userinfo [@user]`**\n"
                "Get information about a user"
            ),
            'moderation': (
                "🛡️ **Moderation Commands**\n\n"
                "Server management commands (requires permissions)\n\n"
                "**`-kick @user [reason]`**\n"
                "Kick a user from the server\n\n"
                "**`-ban @user [reason]`**\n"
                "Ban a user from the server\n\n"
                "**`-clear <amount>`**\n"
                "Delete messages in bulk\n\n"
                "**`-mute @user [duration]`**\n"
                "Mute a user temporarily"
            ),
            'info': (
                "ℹ️ **Information Commands**\n\n"
                "Get information about users and the server\n\n"
                "**`-userinfo [@user]`**\n"
                "Get information about a user\n\n"
                "**`-avatar [@user]`**\n"
                "Get a user's avatar\n\n"
                "**`-botinfo`**\n"
                "Get information about the bot\n\n"
                "**`-serverinfo`**\n"
                "Get detailed server information"
            )
        }
        return contents.get(page, contents['main'])

    def update_content(self, page: str) -> None:
        """Update the displayed content."""
        self.current_page = page
        self.help_text.content = self.get_content(page)


class BotInfoLayoutView(ui.LayoutView):
    """LayoutView for displaying bot information."""
    
    def __init__(self, bot: commands.Bot, guild_owner_name: str | None = None) -> None:
        super().__init__()
        
        # Safely get bot attributes
        bot_name = bot.user.name if bot.user else "Unknown"
        bot_id = bot.user.id if bot.user else "Unknown"
        total_users = sum(g.member_count for g in bot.guilds if g.member_count)
        
        # Create bot info text
        info_text = (
            f"🤖 **Bot Information**\n\n"
            f"**Bot Name:** {bot_name}\n"
            f"**Bot ID:** {bot_id}\n"
            f"**Servers:** {len(bot.guilds)}\n"
            f"**Users:** {total_users}\n"
            f"**Commands:** {len([c for c in bot.commands if not c.hidden])}\n"
            f"**Ping:** {round(bot.latency * 1000)}ms\n\n"
            f"Built with discord.py"
        )
        
        text_display = ui.TextDisplay(info_text)
        separator = ui.Separator()
        
        # Create container with separator
        container = ui.Container(
            text_display,
            separator,
            accent_color=discord.Color.pink()
        )
        
        self.add_item(container)


class CommandsListLayoutView(ui.LayoutView):
    """LayoutView for displaying a list of all commands."""
    
    def __init__(self, bot: commands.Bot) -> None:
        super().__init__()
        
        # Build command list
        command_list = ["📋 **Quick Command List**\n\n"]
        
        for cog_name, cog in bot.cogs.items():
            commands_in_cog = cog.get_commands()
            if commands_in_cog:
                command_list.append(f"**{cog_name}:**\n")
                for command in commands_in_cog:
                    if not command.hidden:
                        command_list.append(f"• `-{command.name}`\n")
                command_list.append("\n")
        
        if len(command_list) == 1:
            command_list.append("No commands available.")
        
        command_list.append("\nUse `-help` for detailed information")
        
        text_display = ui.TextDisplay("".join(command_list))
        separator = ui.Separator()
        
        # Create container with separator
        container = ui.Container(
            text_display,
            separator,
            accent_color=discord.Color.gold()
        )
        
        self.add_item(container)


async def setup(bot):
    await bot.add_cog(ModerationCog(bot))