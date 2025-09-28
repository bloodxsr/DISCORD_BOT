# blacklist.py
# discord.py 2.x
# Persists blacklist to words.py (variable: blat)
# Provides add/remove/list commands and a paginated viewer.

import os
import ast
import importlib.util
from typing import List, Set

import discord
from discord.ext import commands

WORDS_FILE = "cogs/words.py"  # adjust path if needed
DEFAULT_TIMEOUT: float = 300.0
MONO_MAX = 1990  # safety margin under 2000 chars


# ---------- storage helpers ----------
def load_blacklist_from_file(path: str = WORDS_FILE) -> List[str]:
    """Read 'blat' from words.py quickly (AST first, import fallback)."""
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        # Fast path: AST parse
        try:
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign) and any(
                    isinstance(t, ast.Name) and t.id == "blat" for t in node.targets
                ):
                    if isinstance(node.value, ast.List):
                        return [
                            ast.literal_eval(el)
                            for el in node.value.elts
                            if isinstance(el, ast.Constant) and isinstance(el.value, str)
                        ]
        except (SyntaxError, ValueError):
            pass

        # Fallback: dynamic import
        spec = importlib.util.spec_from_file_location("words_module", path)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)  # type: ignore[attr-defined]
            return list(getattr(module, "blat", []))
    except Exception as e:
        print(f"[Blacklist] Error loading file: {e}")
    return []


def save_blacklist_to_file(words: Set[str], path: str = WORDS_FILE) -> None:
    """Write back to words.py as blat = [...]."""
    try:
        payload = sorted(list(words))
        content = f"blat = {payload!r}\n"
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
    except IOError as e:
        print(f"[Blacklist] Error saving file: {e}")


# ---------- formatting helpers ----------
def chunk_words(words: List[str], per_page: int = 100) -> List[str]:
    """Return comma-joined page strings that stay within message limits."""
    pages: List[str] = []
    page: List[str] = []
    length = 0
    for w in words:
        add_len = (2 if page else 0) + len(w)  # ", " + word (except first)
        if page and (length + add_len) > MONO_MAX:
            pages.append(", ".join(page))
            page, length = [w], len(w)
        else:
            page.append(w)
            length += add_len
        if len(page) >= per_page:
            pages.append(", ".join(page))
            page, length = [], 0
    if page:
        pages.append(", ".join(page))
    return pages


def build_preview_embed(words: List[str]) -> discord.Embed:
    preview = ", ".join(words[:20]) if words else "No words."
    if len(words) > 20:
        preview += f"\n\n({len(words) - 20} more words not shown)"
    return discord.Embed(
        title=f"Blacklist ({len(words)} words)",
        description=preview,  # plain text
        color=discord.Color.orange(),
    )


# ---------- Views ----------
class PreviewView(discord.ui.View):
    """Initial view with a button to show the full list."""

    def __init__(self, words: List[str], *, timeout: float = DEFAULT_TIMEOUT):
        super().__init__(timeout=timeout)
        self.words = words

        self.btn_show = discord.ui.Button(
            label="Show Full List", style=discord.ButtonStyle.primary
        )
        self.btn_close = discord.ui.Button(
            label="❌ Close", style=discord.ButtonStyle.danger
        )

        self.btn_show.callback = self._on_show_full
        self.btn_close.callback = self._on_close

        self.add_item(self.btn_show)
        self.add_item(self.btn_close)

    async def _on_show_full(self, interaction: discord.Interaction):
        paginator = PaginatorView(self.words, page_index=0, timeout=DEFAULT_TIMEOUT)
        await interaction.response.edit_message(
            embed=paginator.current_embed(), view=paginator
        )

    async def _on_close(self, interaction: discord.Interaction):
        await interaction.response.edit_message(view=None)
        self.stop()

    async def on_timeout(self):
        return


class PaginatorView(discord.ui.View):
    """Full list paginator with Prev/Next and toggle back to preview."""

    def __init__(self, words: List[str], *, page_index: int = 0, timeout: float = DEFAULT_TIMEOUT):
        super().__init__(timeout=timeout)
        self.words = words
        self.pages = chunk_words(words, per_page=100)
        self.page_index = max(0, min(page_index, max(0, len(self.pages) - 1)))

        self.prev_btn = discord.ui.Button(label="◀️ Previous", style=discord.ButtonStyle.secondary)
        self.toggle_btn = discord.ui.Button(label="Hide Full List", style=discord.ButtonStyle.danger)
        self.next_btn = discord.ui.Button(label="▶️ Next", style=discord.ButtonStyle.secondary)
        self.close_btn = discord.ui.Button(label="❌ Close", style=discord.ButtonStyle.danger)

        self.prev_btn.callback = self._on_prev
        self.toggle_btn.callback = self._on_toggle
        self.next_btn.callback = self._on_next
        self.close_btn.callback = self._on_close

        self.add_item(self.prev_btn)
        self.add_item(self.toggle_btn)
        self.add_item(self.next_btn)
        self.add_item(self.close_btn)

        self._sync_buttons()

    def _sync_buttons(self):
        last_idx = max(0, len(self.pages) - 1)
        self.prev_btn.disabled = (self.page_index <= 0)
        self.next_btn.disabled = (self.page_index >= last_idx or last_idx == 0)

    def current_embed(self) -> discord.Embed:
        total = len(self.words)
        total_pages = max(1, len(self.pages))
        text = self.pages[self.page_index] if self.pages else "No words."
        # No code block fences; show raw content to avoid rendering quirks
        e = discord.Embed(
            title=f"Full Blacklist — Page {self.page_index + 1}/{total_pages}",
            description=text,  # was f"``````"
            color=discord.Color.red(),
        )
        start = self.page_index * 100 + 1 if total > 0 else 0
        end = min((self.page_index + 1) * 100, total)
        e.set_footer(text=f"Words {start}-{end} of {total}")
        return e


    async def _on_prev(self, interaction: discord.Interaction):
        if self.page_index > 0:
            self.page_index -= 1
        self._sync_buttons()
        await interaction.response.edit_message(embed=self.current_embed(), view=self)

    async def _on_toggle(self, interaction: discord.Interaction):
        prev = build_preview_embed(self.words)
        view = PreviewView(self.words, timeout=DEFAULT_TIMEOUT)
        await interaction.response.edit_message(embed=prev, view=view)

    async def _on_next(self, interaction: discord.Interaction):
        last = max(0, len(self.pages) - 1)
        if self.page_index < last:
            self.page_index += 1
        self._sync_buttons()
        await interaction.response.edit_message(embed=self.current_embed(), view=self)

    async def _on_close(self, interaction: discord.Interaction):
        await interaction.response.edit_message(view=None)
        self.stop()

    async def on_timeout(self):
        return


# ---------- Cog ----------
class BlacklistCog(commands.Cog):
    """Blacklist management and viewer."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._blacklist_cache: Set[str] = set(load_blacklist_from_file())

    @property
    def blacklist(self) -> Set[str]:
        return self._blacklist_cache

    def _broadcast_update(self):
        """Notify AutoMod if available, without type errors."""
        cog = self.bot.get_cog("AutoMod")
        if not cog:
            return
        # Guarded dynamic call to satisfy Pylance
        method = getattr(cog, "update_blacklist", None)
        if callable(method):
            try:
                method(self._blacklist_cache.copy())
            except Exception as e:
                print(f"[Blacklist] Failed to broadcast update: {e}")


    def _persist_and_broadcast(self):
        save_blacklist_to_file(self._blacklist_cache)
        self._broadcast_update()

    # ---- Add word ----
    @commands.hybrid_command(name="add_bad_word", description="Add a word to the blacklist")
    @commands.has_permissions(administrator=True)
    async def add_bad_word(self, ctx: commands.Context, *, word: str):
        w = word.lower().strip()
        if not w:
            return await ctx.send("Please provide a valid word or phrase.", ephemeral=True if hasattr(ctx, "interaction") else False)
        if w in self._blacklist_cache:
            return await ctx.send(f"`{word}` is already blacklisted.", ephemeral=True if hasattr(ctx, "interaction") else False)

        self._blacklist_cache.add(w)
        self._persist_and_broadcast()
        await ctx.send(f"✅ Added `{word}` to blacklist.", ephemeral=True if hasattr(ctx, "interaction") else False)

    # ---- Remove word ----
    @commands.hybrid_command(name="remove_bad_word", description="Remove a word from the blacklist")
    @commands.has_permissions(administrator=True)
    async def remove_bad_word(self, ctx: commands.Context, *, word: str):
        w = word.lower().strip()
        if not w:
            return await ctx.send("Please provide a valid word or phrase.", ephemeral=True if hasattr(ctx, "interaction") else False)
        if w not in self._blacklist_cache:
            return await ctx.send(f"`{word}` not found in blacklist.", ephemeral=True if hasattr(ctx, "interaction") else False)

        self._blacklist_cache.discard(w)
        self._persist_and_broadcast()
        await ctx.send(f"✅ Removed `{word}` from blacklist.", ephemeral=True if hasattr(ctx, "interaction") else False)

    # ---- List words (preview + buttons) ----
    @commands.hybrid_command(name="list_blacklist", description="Preview and browse the blacklist with buttons")
    @commands.has_permissions(administrator=True)
    async def list_blacklist(self, ctx: commands.Context):
        words = sorted(list(self._blacklist_cache))
        if not words:
            return await ctx.send(
                embed=discord.Embed(
                    title="Empty Blacklist",
                    description="No words are currently blacklisted.",
                    color=discord.Color.green(),
                ),
                ephemeral=True if hasattr(ctx, "interaction") else False,
            )

        embed = build_preview_embed(words)
        view = PreviewView(words, timeout=DEFAULT_TIMEOUT)
        await ctx.send(
            embed=embed,
            view=view,
            ephemeral=True if hasattr(ctx, "interaction") else False,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(BlacklistCog(bot))
