# blacklist.py
# discord.py 2.x
# Blacklist manager with UI + event broadcasting

import os
import ast
import importlib.util
from typing import List, Set

import discord
from discord.ext import commands
from discord import ui

WORDS_FILE = "cogs/words.py"
DEFAULT_TIMEOUT: float = 300.0
MONO_MAX = 1990


# ---------- storage helpers ----------
def load_blacklist_from_file(path: str = WORDS_FILE) -> List[str]:
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
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
        spec = importlib.util.spec_from_file_location("words_module", path)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)  # type: ignore
            return list(getattr(module, "blat", []))
    except Exception as e:
        print(f"[Blacklist] Error loading file: {e}")
    return []


def save_blacklist_to_file(words: Set[str], path: str = WORDS_FILE) -> None:
    try:
        payload = sorted(list(words))
        content = f"blat = {payload!r}\n"
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
    except IOError as e:
        print(f"[Blacklist] Error saving file: {e}")


def chunk_words(words: List[str], per_page: int = 100) -> List[str]:
    pages: List[str] = []
    page: List[str] = []
    length = 0
    for w in words:
        add_len = (2 if page else 0) + len(w)
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


# ---------- UI ----------
class SearchModal(ui.Modal, title="Search Blacklist"):
    query = ui.TextInput(label="Enter word", placeholder="Type a word to search...")

    def __init__(self, parent_view: 'BlacklistLayoutView'):
        super().__init__()
        self.parent_view = parent_view

    async def on_submit(self, interaction: discord.Interaction):
        word = self.query.value.lower().strip()
        if not word:
            return await interaction.response.send_message("Please enter a word.", ephemeral=True)

        if word not in self.parent_view.words:
            return await interaction.response.send_message("Word not found in blacklist.", ephemeral=True)

        idx = self.parent_view.words.index(word)
        self.parent_view.page_index = idx // 100
        self.parent_view.show_page()
        await interaction.response.edit_message(view=self.parent_view)


class BlacklistNavButtons(ui.ActionRow):
    def __init__(self, parent_view: 'BlacklistLayoutView') -> None:
        super().__init__()
        self.parent_view = parent_view

    @ui.button(label="Previous", style=discord.ButtonStyle.secondary)
    async def prev(self, interaction: discord.Interaction, button: ui.Button):
        self.parent_view.prev_page()
        await interaction.response.edit_message(view=self.parent_view)

    @ui.button(label="Next", style=discord.ButtonStyle.secondary)
    async def next(self, interaction: discord.Interaction, button: ui.Button):
        self.parent_view.next_page()
        await interaction.response.edit_message(view=self.parent_view)

    @ui.button(label="Search", style=discord.ButtonStyle.primary)
    async def search(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(SearchModal(self.parent_view))

    @ui.button(label="Preview", style=discord.ButtonStyle.secondary)
    async def preview(self, interaction: discord.Interaction, button: ui.Button):
        self.parent_view.show_preview()
        await interaction.response.edit_message(view=self.parent_view)

    @ui.button(label="Close", style=discord.ButtonStyle.danger)
    async def close(self, interaction: discord.Interaction, button: ui.Button):
        # Stop the parent view so buttons are disabled
        self.parent_view.stop()
        # Edit the message to remove the view
        await interaction.message.delete() #type: ignore
        await interaction.response.send_message("Blacklist view closed.", ephemeral=True)



class BlacklistLayoutView(ui.LayoutView):
    def __init__(self, words: List[str]) -> None:
        super().__init__()
        self.words = words
        self.pages = chunk_words(words, per_page=100)
        self.preview_mode = True
        self.page_index = 0

        self.display = ui.TextDisplay(self._get_preview_content())

        container = ui.Container(
            self.display,
            ui.Separator(),
            BlacklistNavButtons(self),
            accent_color=discord.Color.red()
        )
        self.add_item(container)

    def _get_preview_content(self) -> str:
        preview = ", ".join(self.words[:20]) if self.words else "No words."
        if len(self.words) > 20:
            preview += f"\n\n({len(self.words) - 20} more words not shown)"
        return f"📝 **Blacklist Preview** ({len(self.words)} words)\n\n{preview}"

    def _get_page_content(self) -> str:
        if not self.pages:
            return "No words."
        total_pages = max(1, len(self.pages))
        text = self.pages[self.page_index]
        return (
            f"📕 **Blacklist Page {self.page_index + 1}/{total_pages}**\n\n"
            f"{text}\n\n"
            f"Showing words {self.page_index*100+1}-{min((self.page_index+1)*100,len(self.words))} "
            f"of {len(self.words)}"
        )

    def show_preview(self):
        self.preview_mode = True
        self.display.content = self._get_preview_content()

    def show_page(self):
        self.preview_mode = False
        self.display.content = self._get_page_content()

    def prev_page(self):
        if not self.preview_mode and self.page_index > 0:
            self.page_index -= 1
        self.show_page()

    def next_page(self):
        if not self.preview_mode and self.page_index < len(self.pages) - 1:
            self.page_index += 1
        self.show_page()


# ---------- Cog ----------
class BlacklistCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._blacklist_cache: Set[str] = set(load_blacklist_from_file())

    @property
    def blacklist(self) -> Set[str]:
        return self._blacklist_cache

    def _persist_and_broadcast(self):
        save_blacklist_to_file(self._blacklist_cache)
        # 🔥 Event-based broadcast
        self.bot.dispatch("blacklist_update", self._blacklist_cache.copy())

    @commands.hybrid_command(name="add_bad_word", description="Add a word to the blacklist")
    @commands.has_permissions(administrator=True)
    async def add_bad_word(self, ctx: commands.Context, *, word: str):
        w = word.lower().strip()
        if not w:
            return await ctx.send("Please provide a valid word or phrase.")
        if w in self._blacklist_cache:
            return await ctx.send(f"`{word}` is already blacklisted.")
        self._blacklist_cache.add(w)
        self._persist_and_broadcast()
        await ctx.send(f"✅ Added `{word}` to blacklist.")

    @commands.hybrid_command(name="remove_bad_word", description="Remove a word from the blacklist")
    @commands.has_permissions(administrator=True)
    async def remove_bad_word(self, ctx: commands.Context, *, word: str):
        w = word.lower().strip()
        if not w:
            return await ctx.send("Please provide a valid word or phrase.")
        if w not in self._blacklist_cache:
            return await ctx.send(f"`{word}` not found in blacklist.")
        self._blacklist_cache.discard(w)
        self._persist_and_broadcast()
        await ctx.send(f"✅ Removed `{word}` from blacklist.")

    @commands.hybrid_command(name="list_blacklist", description="Preview and browse the blacklist with UI")
    @commands.has_permissions(administrator=True)
    async def list_blacklist(self, ctx: commands.Context):
        words = sorted(list(self._blacklist_cache))
        if not words:
            return await ctx.send("✅ Blacklist is empty.")
        view = BlacklistLayoutView(words)
        await ctx.send(view=view)


async def setup(bot):
    await bot.add_cog(BlacklistCog(bot))
