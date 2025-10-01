import sqlite3
import discord
from discord.ext import commands
from typing import Optional, Set, Dict
import re
from functools import lru_cache
import ast
import os

class AutoMod(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        # Initialize blacklist
        self._blacklist: Set[str] = set()
        self._pattern: Optional[re.Pattern] = None
        self._load_blacklist()
        self._compile_blacklist_patterns()

        # Database & warnings
        self.db_file = "warnings.db"
        self.MAX_WARNINGS = 10
        self._init_database()
        self.fallback_warnings: Dict[int, int] = {}

    # ---------------- Blacklist loading ----------------
    def _load_blacklist(self):
        """Load blacklist from cogs/words.py (variable: blat)"""
        words_file = "cogs/words.py"
        if not os.path.exists(words_file):
            print("[AutoMod] Warning: words.py not found, blacklist empty.")
            self._blacklist = set()
            return

        try:
            with open(words_file, "r", encoding="utf-8") as f:
                content = f.read()
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name) and target.id == "blat":
                            if isinstance(node.value, ast.List):
                                self._blacklist = set(
                                    ast.literal_eval(elem) 
                                    for elem in node.value.elts
                                    if isinstance(elem, ast.Constant) and isinstance(elem.value, str)
                                )
            print(f"[AutoMod] Loaded {len(self._blacklist)} blacklist words.")
        except Exception as e:
            print(f"[AutoMod] Error loading blacklist: {e}")
            self._blacklist = set()

    def _compile_blacklist_patterns(self):
        """Compile regex pattern for fast blacklist detection"""
        if not self._blacklist:
            self._pattern = None
            return
        try:
            escaped = [re.escape(word) for word in self._blacklist]
            pattern = r"\b(?:{})(?:\b|$)".format("|".join(escaped))
            self._pattern = re.compile(pattern, re.IGNORECASE)
        except re.error as e:
            print(f"[AutoMod] Regex compile error: {e}")
            self._pattern = None

    def reload_blacklist(self) -> Set[str]:
        """Reload blacklist manually"""
        self._load_blacklist()
        self._compile_blacklist_patterns()
        self._is_staff_cached.cache_clear()
        return self._blacklist

    # ---------------- Database & warnings ----------------
    def _init_database(self):
        if not self.db_file:
            return
        try:
            with sqlite3.connect(self.db_file) as conn:
                conn.execute(
                    """CREATE TABLE IF NOT EXISTS warnings (
                        user_id INTEGER PRIMARY KEY,
                        warning_count INTEGER NOT NULL DEFAULT 0,
                        last_warning TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )"""
                )
                conn.commit()
            print(f"[AutoMod] Database initialized: {self.db_file}")
        except sqlite3.Error as e:
            print(f"[AutoMod] Database init error: {e}")
            self.db_file = None

    def _db_execute(self, query: str, params: tuple = (), fetch: bool = False):
        if not self.db_file:
            return None
        try:
            with sqlite3.connect(self.db_file) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(query, params)
                if fetch:
                    result = cursor.fetchone()
                    return dict(result) if result else None
                conn.commit()
                return True
        except sqlite3.Error as e:
            print(f"[AutoMod] Database error: {e}")
            self.db_file = None
            return None

    def get_warning_count(self, user_id: int) -> int:
        if self.db_file:
            res = self._db_execute(
                "SELECT warning_count FROM warnings WHERE user_id = ?", (user_id,), fetch=True
            )
            if res:
                return res.get("warning_count", 0) # type: ignore
        return self.fallback_warnings.get(user_id, 0)

    def increment_warning(self, user_id: int) -> int:
        current = self.get_warning_count(user_id)
        new_count = current + 1
        if self.db_file:
            self._db_execute(
                "INSERT OR REPLACE INTO warnings (user_id, warning_count) VALUES (?, ?)",
                (user_id, new_count)
            )
        else:
            self.fallback_warnings[user_id] = new_count
        return new_count

    def reset_warnings(self, user_id: int):
        if self.db_file:
            self._db_execute(
                "UPDATE warnings SET warning_count = 0 WHERE user_id = ?", (user_id,)
            )
        else:
            self.fallback_warnings.pop(user_id, None)

    # ---------------- Staff check ----------------
    @lru_cache(maxsize=1000)
    def _is_staff_cached(self, user_id: int, guild_id: int) -> bool:
        guild = self.bot.get_guild(guild_id)
        if not guild:
            return False
        member = guild.get_member(user_id)
        if not member:
            return False
        return member.guild_permissions.manage_messages or member.guild_permissions.administrator or member.id == guild.owner_id

    # ---------------- Blacklist check ----------------
    def _contains_blacklisted_word(self, text: str) -> bool:
        if not self._blacklist:
            return False
        if self._pattern:
            return bool(self._pattern.search(text))
        text_lower = text.lower()
        return any(word in text_lower for word in self._blacklist)

    # ---------------- On message listener ----------------
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild or not message.content.strip():
            return

        # Staff bypass
        if self._is_staff_cached(message.author.id, message.guild.id):
            return

        # Check blacklist
        if self._contains_blacklisted_word(message.content):
            try:
                await message.delete()
                user_id = message.author.id
                warnings = self.increment_warning(user_id)

                if warnings >= self.MAX_WARNINGS:
                    await self._handle_max_warnings(message, user_id)
                else:
                    await self._send_warning(message, warnings)
            except discord.NotFound:
                pass
            except discord.Forbidden:
                await self._send_warning(message, self.get_warning_count(message.author.id))
            except Exception as e:
                print(f"[AutoMod] Error: {e}")

        # Allow commands to work even with on_message listener
        await self.bot.process_commands(message)

    async def _handle_max_warnings(self, message: discord.Message, user_id: int):
        member = message.guild.get_member(user_id) # type: ignore
        if not member:
            try:
                member = await message.guild.fetch_member(user_id) # type: ignore
            except discord.NotFound:
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
                description=(f"{member.mention} reached max warnings but cannot be kicked."),
                color=0xFF6600
            )
            await message.channel.send(embed=embed, delete_after=20)
        except Exception as e:
            print(f"[AutoMod] Error handling max warnings: {e}")

    async def _send_warning(self, message: discord.Message, warning_count: int):
        embed = discord.Embed(
            title="⚠️ Message Removed",
            description=(f"{message.author.mention}, your message contained banned content "
                         f"and was removed.\n**Warnings:** {warning_count}/{self.MAX_WARNINGS}"),
            color=0xFFAA00
        )
        if warning_count >= self.MAX_WARNINGS - 1:
            embed.add_field(name="Final Warning", value="Next violation will result in a kick!", inline=False)
        try:
            warning_msg = await message.channel.send(embed=embed)
            await warning_msg.delete(delay=10)
        except Exception as e:
            print(f"[AutoMod] Error sending warning: {e}")

    # ---------------- Commands ----------------
    @commands.hybrid_command(name="automod_reload", hidden=True)
    @commands.has_permissions(administrator=True)
    async def reload_blacklist_command(self, ctx: commands.Context):
        try:
            reloaded = self.reload_blacklist()
            await ctx.send(f"✅ Blacklist reloaded: {len(reloaded)} words.", delete_after=10)
        except Exception as e:
            await ctx.send(f"❌ Error reloading blacklist: {e}", delete_after=10)

    @commands.hybrid_command(name="warnings", hidden=True)
    @commands.has_permissions(manage_messages=True)
    async def check_warnings(self, ctx: commands.Context, member: Optional[discord.Member] = None):
        target = member or ctx.author
        count = self.get_warning_count(target.id)
        embed = discord.Embed(
            title=f"⚠️ Warnings for {target.display_name}",
            description=f"Current warnings: **{count}/{self.MAX_WARNINGS}**",
            color=0x00AA00 if count < self.MAX_WARNINGS else 0xFF0000
        )
        await ctx.send(embed=embed, delete_after=15)

    @commands.hybrid_command(
        name="reset_warnings",
        description="Reset the warning count for a member"
    )
    @commands.has_permissions(manage_messages=True)
    async def reset_warnings_command(self, ctx: commands.Context, member: Optional[discord.Member] = None):
        """
        Hybrid command to reset warnings for a user.
        """
        target = member or ctx.author
        # Call the internal helper method
        self.reset_warnings(target.id)
        await ctx.send(
            f"✅ Warnings for {target.mention} have been reset.",
            delete_after=10
        )



    

# ---------------- Setup ----------------
async def setup(bot: commands.Bot):
    await bot.add_cog(AutoMod(bot))



