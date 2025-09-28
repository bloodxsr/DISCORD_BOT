import sqlite3
from discord.ext import commands
import discord
from typing import Optional, Set, Dict
import re
from functools import lru_cache


class AutoMod(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
        # Try different import paths for BlacklistManager
        self.manager = None
        try:
            from .utils import BlacklistManager
            self.manager = BlacklistManager()
        except ImportError:
            try:
                from utils import BlacklistManager
                self.manager = BlacklistManager()
            except ImportError:
                try:
                    import utils
                    self.manager = utils.BlacklistManager()
                except ImportError:
                    print("Warning: Could not import BlacklistManager. Using inline fallback.")
                    self.manager = None
        
        # Initialize blacklist set
        if self.manager:
            blacklist_words = self.manager.current
            self._blacklist: Set[str] = set(blacklist_words)
        else:
            self._blacklist: Set[str] = set()
            self._load_blacklist_inline()
        
        self.db_file: Optional[str] = 'warnings.db'
        self.MAX_WARNINGS = 10
        self._init_database()
        self.fallback_warnings: Dict[int, int] = {}
        
        # Compile regex patterns for blacklist checking
        self._compile_blacklist_patterns()

    # Add this method inside class AutoMod

    def update_blacklist(self, new_set: Set[str]) -> None:
        """Receive updates from BlacklistCog and refresh patterns."""
        try:
            self._blacklist = set(new_set)
            self._compile_blacklist_patterns()
            # clear permission cache in case roles changed
            self._is_staff_cached.cache_clear()
            print(f"[AutoMod] Blacklist updated: {len(self._blacklist)} words.")
        except Exception as e:
            print(f"[AutoMod] Failed to update blacklist: {e}")


    def _load_blacklist_inline(self):
        """Fallback blacklist loading if utils.py is not available"""
        try:
            import os
            import ast
            words_file = 'cogs/words.py'
            if os.path.exists(words_file):
                with open(words_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if (isinstance(node, ast.Assign) and 
                        any(isinstance(target, ast.Name) and target.id == 'blat' for target in node.targets)):
                        if isinstance(node.value, ast.List):
                            words = [ast.literal_eval(elem) for elem in node.value.elts 
                                     if isinstance(elem, ast.Constant) and isinstance(elem.value, str)]
                            self._blacklist = set(words)
                            return
        except Exception as e:
            print(f"Error loading blacklist inline: {e}")
            self._blacklist = set()

    def _compile_blacklist_patterns(self):
        """Compile regex pattern to speed up blacklist checks"""
        if not self._blacklist:
            self._pattern = None
            return
        try:
            escaped_words = [re.escape(word) for word in self._blacklist]
            pattern = r'\b(?:' + '|'.join(escaped_words) + r')\b'
            self._pattern = re.compile(pattern, re.IGNORECASE)
        except re.error as e:
            print(f"Error compiling regex pattern: {e}")
            self._pattern = None

    @property
    def blacklist(self) -> Set[str]:
        """Get current blacklist, reload if changed"""
        if hasattr(self, 'manager') and self.manager:
            current_words_list = self.manager.current
            current_words_set = set(current_words_list)
            if current_words_set != self._blacklist:
                self._blacklist = current_words_set
                self._compile_blacklist_patterns()
        return self._blacklist

    def _init_database(self):
        """Initialize SQLite database for warnings"""
        if not self.db_file:
            return
        try:
            with sqlite3.connect(self.db_file) as conn:
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS warnings (
                        user_id INTEGER PRIMARY KEY,
                        warning_count INTEGER NOT NULL DEFAULT 0,
                        last_warning TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                conn.commit()
                print(f"Database initialized: {self.db_file}")
        except sqlite3.Error as e:
            print(f"Database initialization error: {e}. Using in-memory fallback.")
            self.db_file = None

    def _db_execute(self, query: str, params: tuple = (), fetch: bool = False):
        """Execute database query safely"""
        if not self.db_file:
            return None
        try:
            with sqlite3.connect(self.db_file) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(query, params)
                if fetch:
                    result = cursor.fetchone()
                    return dict(result) if result else None
                else:
                    conn.commit()
                    return True
        except sqlite3.Error as e:
            print(f"Database error: {e}. Falling back to in-memory.")
            self.db_file = None
            return None

    def get_warning_count(self, user_id: int) -> int:
        """Get the warning count for a user"""
        if self.db_file:
            result = self._db_execute(
                "SELECT warning_count FROM warnings WHERE user_id = ?",
                (user_id,),
                fetch=True
            )
            if isinstance(result, dict):
                return result.get('warning_count', 0)
        return self.fallback_warnings.get(user_id, 0)

    def increment_warning(self, user_id: int) -> int:
        """Increment and return the new warning count"""
        current = self.get_warning_count(user_id)
        new_count = current + 1
        if self.db_file:
            success = self._db_execute(
                "INSERT OR REPLACE INTO warnings (user_id, warning_count) VALUES (?, ?)",
                (user_id, new_count)
            )
            if success:
                return new_count
        self.fallback_warnings[user_id] = new_count
        return new_count

    def reset_warnings(self, user_id: int) -> bool:
        """Reset warnings for a user"""
        if self.db_file:
            success = self._db_execute(
                "UPDATE warnings SET warning_count = 0 WHERE user_id = ?",
                (user_id,)
            )
            if success:
                return True
        self.fallback_warnings.pop(user_id, None)
        return True

    @lru_cache(maxsize=1000)
    def _is_staff_cached(self, user_id: int, guild_id: int) -> bool:
        """Check if user is staff (cached)"""
        guild = self.bot.get_guild(guild_id)
        if not guild:
            return False
        member = guild.get_member(user_id)
        if not member:
            return False
        return (member.guild_permissions.manage_messages or
                member.guild_permissions.administrator or
                member.id == guild.owner_id)

    def _contains_blacklisted_word(self, text: str) -> bool:
        """Check if text contains any blacklisted word"""
        if not self._blacklist:
            return False
        if self._pattern:
            return bool(self._pattern.search(text))
        text_lower = text.lower()
        return any(word in text_lower for word in self._blacklist)


    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Main automod logic on message"""
        # Ignore bots, DMs, and empty messages
        if message.author.bot or not message.guild or not message.content.strip():
            return
        
        if self._is_staff_cached(message.author.id, message.guild.id):
            return
        
        if self._contains_blacklisted_word(message.content):
            try:
                await message.delete()
                user_id = message.author.id
                current_warnings = self.increment_warning(user_id)

                if current_warnings >= self.MAX_WARNINGS:
                    await self._handle_max_warnings(message, user_id)
                else:
                    await self._send_warning(message, current_warnings)
            except discord.NotFound:
                # Already deleted
                pass
            except discord.Forbidden:
                # Can't delete message; just warn
                await self._send_warning(message, self.get_warning_count(user_id))
            except Exception as e:
                print(f"Error in automod: {e}")

    async def _handle_max_warnings(self, message: discord.Message, user_id: int):
        """Handle user reaching max warnings by kicking"""
        if not message.guild:
            return

        member = message.guild.get_member(user_id)
        if not member:
            try:
                member = await message.guild.fetch_member(user_id)
            except discord.NotFound:
                print(f"Could not find member {user_id} in guild {message.guild.id}")
                return

        try:
            await member.kick(reason="Exceeded maximum warnings for banned words")

            embed = discord.Embed(
                title="🚨 User Kicked",
                description=f"{member.mention} has been kicked for repeated rule violations.",
                color=0xFF0000
            )
            await message.channel.send(embed=embed, delete_after=15)

            self.reset_warnings(user_id)

        except discord.Forbidden:
            embed = discord.Embed(
                title="⚠️ Max Warnings Reached",
                description=(f"{member.mention} has reached the maximum warning limit "
                             "but cannot be kicked (insufficient permissions)."),
                color=0xFF6600
            )
            await message.channel.send(embed=embed, delete_after=20)
        except Exception as e:
            print(f"Error handling max warnings: {e}")

    async def _send_warning(self, message: discord.Message, warning_count: int):
        """Send warning message to user"""
        embed = discord.Embed(
            title="⚠️ Message Removed",
            description=(f"{message.author.mention}, your message contained banned content "
                         f"and was removed.\n\n**Warnings:** {warning_count}/{self.MAX_WARNINGS}"),
            color=0xFFAA00
        )
        if warning_count >= self.MAX_WARNINGS - 1:
            embed.add_field(
                name="⚡ Final Warning",
                value="Next violation will result in a kick!",
                inline=False
            )
        try:
            warning_msg = await message.channel.send(embed=embed)
            await warning_msg.delete(delay=10)
        except Exception as e:
            print(f"Error sending warning: {e}")

    def reload_blacklist(self) -> Set[str]:
        """Manually reload blacklist words"""
        if hasattr(self, 'manager') and self.manager:
            try:
                reloaded_words_list = self.manager.reload()
                self._blacklist = set(reloaded_words_list)
            except Exception as e:
                print(f"Error reloading blacklist: {e}")
                self._blacklist = set()
        else:
            self._load_blacklist_inline()
        self._compile_blacklist_patterns()
        self._is_staff_cached.cache_clear()
        return self._blacklist

    @commands.command(name='automod_reload', hidden=True)
    @commands.has_permissions(administrator=True)
    async def reload_blacklist_command(self, ctx: commands.Context):
        """Command to reload blacklist manually"""
        try:
            reloaded = self.reload_blacklist()
            await ctx.send(f"✅ Blacklist reloaded: {len(reloaded)} words loaded.", delete_after=10)
        except Exception as e:
            await ctx.send(f"❌ Error reloading blacklist: {str(e)}", delete_after=10)

    @commands.command(name='warnings', hidden=True)
    @commands.has_permissions(manage_messages=True)
    async def check_warnings(self, ctx: commands.Context, member: Optional[discord.Member] = None):
        """Check warning count for user"""
        if not ctx.guild:
            await ctx.send("❌ This command can only be used in a server.", delete_after=10)
            return
        
        target = member or (ctx.author if isinstance(ctx.author, discord.Member) else None)
        if not target:
            await ctx.send("❌ Could not resolve you as a server member.", delete_after=10)
            return
        
        count = self.get_warning_count(target.id)
        embed = discord.Embed(
            title=f"⚠️ Warnings for {target.display_name}",
            description=f"Current warnings: **{count}/{self.MAX_WARNINGS}**",
            color=0x00AA00 if count < self.MAX_WARNINGS else 0xFF0000
        )
        await ctx.send(embed=embed, delete_after=15)


async def setup(bot):
    await bot.add_cog(AutoMod(bot))



