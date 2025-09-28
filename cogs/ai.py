import os
import re
import asyncio
import discord
import time
import random
from discord import app_commands
from discord.ext import commands
from google import genai
from google.genai import types
from typing import Optional, Dict, List, Union
from functools import lru_cache
import logging
from dotenv import load_dotenv

load_dotenv('google.env')


class AICog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
        # Configuration constants
        self.MAX_HISTORY = 30
        self.MAX_MESSAGE_LENGTH = 2000
        self.MAX_RESPONSE_LENGTH = 1500
        self.REQUEST_TIMEOUT = 30
        
        # Rate limiting (per user)
        self.user_cooldowns: Dict[int, float] = {}
        self.COOLDOWN_SECONDS = 3
        
        # Initialize Google AI client
        self._initialize_client()
        
        # Optimized generation config - simplified for compatibility
        self.text_generation_config = types.GenerateContentConfig(
            temperature=0.7,
            top_p=0.9,
            top_k=40,
            max_output_tokens=500
        )

    def _initialize_client(self):
        """Initialize Google AI client with proper error handling"""
        try:
            api_key = str(os.getenv("key"))  # read 'key' from environment variables
            
            if not api_key or api_key == "None":
                raise ValueError("API key is empty or not found in environment variables")
            
            # Initialize client with proper error checking
            self.client = genai.Client(api_key=api_key)
            
            # Test the client by checking if it's properly initialized
            if not hasattr(self.client, 'models'):
                raise AttributeError("Client initialization failed - models attribute missing")
            
            print("Google AI client initialized successfully")
            
        except ValueError as e:
            print(f"ERROR: Invalid API key - {e}")
            self.client = None
        except Exception as e:
            print(f"ERROR: Failed to initialize Google AI client: {e}")
            self.client = None

    @staticmethod
    @lru_cache(maxsize=100)
    def clean_discord_message(message: str) -> str:
        """Clean Discord message formatting with caching"""
        if not message:
            return ""
        
        # Remove Discord formatting
        patterns = [
            (re.compile(r'<@!?\d+>'), '@user'),      # User mentions
            (re.compile(r'<@&\d+>'), '@role'),       # Role mentions  
            (re.compile(r'<#\d+>'), '#channel'),     # Channel mentions
            (re.compile(r'<a?:\w+:\d+>'), ':emoji:'), # Custom emojis
            (re.compile(r'<[^>]+>'), ''),             # Other Discord markup
        ]
        
        cleaned = message
        for pattern, replacement in patterns:
            cleaned = pattern.sub(replacement, cleaned)
        
        # Trim whitespace and limit length
        cleaned = cleaned.strip()
        return cleaned[:2000] if len(cleaned) > 2000 else cleaned

    def _check_rate_limit(self, user_id: int) -> bool:
        """Check if user is rate limited"""
        now = time.time()
        
        if user_id in self.user_cooldowns:
            if now - self.user_cooldowns[user_id] < self.COOLDOWN_SECONDS:
                return False
        
        self.user_cooldowns[user_id] = now
        return True

    async def _generate_response_with_timeout(self, prompt: str) -> str:
        """Generate AI response with timeout and error handling"""
        if not self.client:
            return "❌ AI service is not available. Please contact an administrator."
        
        try:
            # Use asyncio.wait_for for timeout protection
            response = await asyncio.wait_for(
                self._generate_response_async(prompt),
                timeout=self.REQUEST_TIMEOUT
            )
            return response
            
        except asyncio.TimeoutError:
            return "⏰ Request timed out. Please try again with a shorter question."
        except Exception as e:
            logging.error(f"AI generation error: {e}")
            return f"❌ Sorry, I encountered an error: {str(e)[:100]}..."

    async def _generate_response_async(self, prompt: str) -> str:
        """Async wrapper for AI generation"""
        try:
            # Run the synchronous API call in an executor
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None, 
                self._generate_sync, 
                prompt
            )
            return response
            
        except Exception as e:
            raise e

    def _generate_sync(self, prompt: str) -> str:
        """Synchronous AI generation"""
        try:
            if not self.client:
                raise Exception("AI client is not initialized")
            
            # Updated API call for newer Google Gemini client
            response = self.client.models.generate_content(
                model="gemini-2.0-flash-exp",
                contents=[prompt],
                config=self.text_generation_config
            )
            
            if not response or not response.text:
                return "🤔 I couldn't generate a response. Please try rephrasing your question."
            
            # Limit response length for Discord
            text = response.text.strip()
            if len(text) > self.MAX_RESPONSE_LENGTH:
                text = text[:self.MAX_RESPONSE_LENGTH] + "..."
            
            return text
            
        except Exception as e:
            raise e

    def _create_embed(self, title: str, description: str, color: discord.Color) -> discord.Embed:
        """Create standardized embed with footer"""
        embed = discord.Embed(
            title=title,
            description=description,
            color=color
        )
        embed.set_footer(text="Powered by Google AI")
        return embed

    async def _safe_response_hybrid(self, ctx_or_interaction: Union[commands.Context, discord.Interaction], embed: discord.Embed):
        """Safe response handling for both contexts and interactions"""
        try:
            if isinstance(ctx_or_interaction, commands.Context):
                # Context (prefix command)
                await ctx_or_interaction.send(embed=embed)
            else:
                # Interaction (slash command)
                if ctx_or_interaction.response.is_done():
                    await ctx_or_interaction.followup.send(embed=embed)
                else:
                    await ctx_or_interaction.response.send_message(embed=embed)
        except discord.HTTPException:
            # Fallback to plain text if embed fails
            try:
                content = f"**{embed.title}**\n{embed.description}"
                if isinstance(ctx_or_interaction, commands.Context):
                    await ctx_or_interaction.send(content[:2000])
                else:
                    if ctx_or_interaction.response.is_done():
                        await ctx_or_interaction.followup.send(content[:2000])
                    else:
                        await ctx_or_interaction.response.send_message(content[:2000])
            except Exception:
                pass

    async def _send_ephemeral_or_reply(self, ctx_or_interaction: Union[commands.Context, discord.Interaction], embed: discord.Embed):
        """Send ephemeral for slash commands or regular reply for prefix commands"""
        try:
            if isinstance(ctx_or_interaction, commands.Context):
                await ctx_or_interaction.send(embed=embed)
            else:
                await ctx_or_interaction.response.send_message(embed=embed, ephemeral=True)
        except discord.HTTPException:
            content = f"**{embed.title}**\n{embed.description}"
            if isinstance(ctx_or_interaction, commands.Context):
                await ctx_or_interaction.send(content[:2000])
            else:
                await ctx_or_interaction.response.send_message(content[:2000], ephemeral=True)

    @commands.hybrid_command(name="ask", description="Ask a question to the AI")
    @app_commands.describe(question="Your question for the AI")
    async def ask_command(self, ctx: commands.Context, *, question: str):
        """Ask the AI a question"""
        # Rate limiting check
        if not self._check_rate_limit(ctx.author.id):
            embed = discord.Embed(
                title="⏱️ Slow down!",
                description=f"Please wait {self.COOLDOWN_SECONDS} seconds between requests.",
                color=discord.Color.orange()
            )
            return await self._send_ephemeral_or_reply(ctx, embed)
        
        # Input validation
        if len(question.strip()) < 3:
            embed = discord.Embed(
                title="❓ Invalid Question",
                description="Please ask a more detailed question (at least 3 characters).",
                color=discord.Color.red()
            )
            return await self._send_ephemeral_or_reply(ctx, embed)
        
        # Handle defer differently for context vs interaction
        if isinstance(ctx, commands.Context):
            async with ctx.typing():
                # Clean and process the question
                cleaned_question = self.clean_discord_message(question)
                
                # Add context for better responses
                enhanced_prompt = f"User question: {cleaned_question}\n\nPlease provide a helpful, accurate response."
                
                # Generate response
                response_text = await self._generate_response_with_timeout(enhanced_prompt)
                
                # Create and send embed
                embed = self._create_embed(
                    "🤖 AI Response",
                    response_text,
                    discord.Color.blue()
                )
                
                await self._safe_response_hybrid(ctx, embed)
        else:
            await ctx.defer()
            
            # Clean and process the question
            cleaned_question = self.clean_discord_message(question)
            
            # Add context for better responses
            enhanced_prompt = f"User question: {cleaned_question}\n\nPlease provide a helpful, accurate response."
            
            # Generate response
            response_text = await self._generate_response_with_timeout(enhanced_prompt)
            
            # Create and send embed
            embed = self._create_embed(
                "🤖 AI Response",
                response_text,
                discord.Color.blue()
            )
            
            await self._safe_response_hybrid(ctx, embed)

    @commands.hybrid_command(name="joke", description="Get a random joke from the AI")
    async def joke_command(self, ctx: commands.Context):
        """Get a random joke"""
        # Rate limiting check
        if not self._check_rate_limit(ctx.author.id):
            embed = discord.Embed(
                title="⏱️ Slow down!",
                description=f"Please wait {self.COOLDOWN_SECONDS} seconds between requests.",
                color=discord.Color.orange()
            )
            return await self._send_ephemeral_or_reply(ctx, embed)
        
        joke_prompts = [
            "Tell me a clean, funny joke that would be appropriate for a Discord server.",
            "Share a clever pun or wordplay joke.",
            "Give me a light-hearted, family-friendly joke.",
            "Tell me a programming or tech-related joke.",
            "Share a dad joke that will make people groan and laugh."
        ]
        
        selected_prompt = random.choice(joke_prompts)
        
        # Handle defer differently for context vs interaction
        if isinstance(ctx, commands.Context):
            async with ctx.typing():
                response_text = await self._generate_response_with_timeout(selected_prompt)
                
                embed = self._create_embed(
                    "😄 Here's a joke for you!",
                    response_text,
                    discord.Color.purple()
                )
                
                await self._safe_response_hybrid(ctx, embed)
        else:
            await ctx.defer()
            
            response_text = await self._generate_response_with_timeout(selected_prompt)
            
            embed = self._create_embed(
                "😄 Here's a joke for you!",
                response_text,
                discord.Color.purple()
            )
            
            await self._safe_response_hybrid(ctx, embed)

    @commands.hybrid_command(name="ai_commands", description="Get help with AI commands")
    async def ai_commands(self, ctx: commands.Context):
        """Show AI help information"""
        help_text = """
        **Available AI Commands:**
        
        `/ask <question>` or `!ask <question>` - Ask me anything! I'll do my best to help.
        `/joke` or `!joke` - Get a random joke to brighten your day.
        `/ai_commands` or `!ai_commands` - Show this help message.
        
        **Tips:**
        • Be specific with your questions for better answers
        • There's a 3-second cooldown between requests
        • Keep questions under 2000 characters
        • I'm powered by Google's Gemini AI
        • Commands work both as slash commands (/) and prefix commands (!)
        
        **Note:** Please be respectful and follow server rules!
        """
        
        embed = discord.Embed(
            title="🤖 AI Commands Help",
            description=help_text,
            color=discord.Color.green()
        )
        
        await self._send_ephemeral_or_reply(ctx, embed)

    @commands.hybrid_command(name='ai_status', description="Check AI service status")
    @commands.has_permissions(administrator=True)
    async def ai_status(self, ctx: commands.Context):
        """Check AI service status (Admin only)"""
        status = "🟢 Online" if self.client else "🔴 Offline"
        cooldown_count = len([t for t in self.user_cooldowns.values() 
                             if (time.time() - t) < self.COOLDOWN_SECONDS])
        
        embed = discord.Embed(
            title="🔧 AI Service Status",
            color=discord.Color.green() if self.client else discord.Color.red()
        )
        embed.add_field(name="Service Status", value=status, inline=True)
        embed.add_field(name="Active Cooldowns", value=str(cooldown_count), inline=True)
        embed.add_field(name="Model", value="gemini-2.0-flash-exp", inline=True)
        
        await self._safe_response_hybrid(ctx, embed)


async def setup(bot):
    await bot.add_cog(AICog(bot))




