import discord
from discord.ext import commands
import os
from groq import Groq 
from dotenv import load_dotenv 
import pandas as pd 
import difflib 

load_dotenv() 

DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
GROQ_API_KEY = os.getenv('GROQ_API_KEY')
ADMIN_PWD = os.getenv('ADMIN_PASSWORD')

if DISCORD_TOKEN is None or GROQ_API_KEY is None:
    print("FATAL ERROR: Cannot find .env file or keys are empty!")
    exit()
if DISCORD_TOKEN is None or GROQ_API_KEY is None or ADMIN_PWD is None:
    print("ERROR: Missing info in .env file (Token, API Key or Admin Password)")
    exit()


intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='?', intents=intents)

client_groq = Groq(api_key=GROQ_API_KEY)


CSV_FILE = "Games.csv" 

# --- GLOBAL VARIABLES ---
DATASET_DF = None  
CSV_LOADED = False

def load_csv_data():
    """Load CSV file into a DataFrame """
    global DATASET_DF, CSV_LOADED
    if os.path.exists(CSV_FILE):
        try:
            DATASET_DF = pd.read_csv(CSV_FILE)
            CSV_LOADED = True
            print(f"✅ DATA: CSV file loaded ({len(DATASET_DF)} games in memory).")
        except Exception as e:
            print(f"⚠️ Error reading CSV: {e}")
            CSV_LOADED = False
    else:
        print("⚠️ Games.csv file not found!")
        CSV_LOADED = False


def get_csv_context_for_query(query_text, force=False):
    """
    function: Only returns CSV data if explicitly requested.
    By default, CSV is NOT injected unless force=True.
    
    Args:
        query_text: The user's message
        force: If True, always return CSV (used for verdict phase)
    """
    if not CSV_LOADED or DATASET_DF is None:
        return ""
    
    # If force=True (verdict phase), always return CSV
    if force:
        return f"\n\n[DATASET REFERENCE - {len(DATASET_DF)} games available]\n" + DATASET_DF.to_string(index=False, max_rows=50)
    
    # For specific commands that explicitly request data
    query_lower = query_text.lower()
    
    # Only trigger for EXPLICIT data requests (very specific keywords)
    explicit_data_keywords = [
        'searchdata', 'predict', 'csv data', 'dataset', 'show me data',
        'from the csv', 'in the dataset', 'according to data'
    ]
    
    needs_csv = any(keyword in query_lower for keyword in explicit_data_keywords)
    
    if needs_csv:
        return f"\n\n[DATASET REFERENCE - {len(DATASET_DF)} games available]\n" + DATASET_DF.to_string(index=False, max_rows=50)
    
    return ""


# ---  PROMPTS  ---
CONSULTANT_SYSTEM_PROMPT = (
    "You are DataNexus, an AI Game Strategy Consultant. "
    "Your goal is to help developers adapt their games for the future market. "
    "Be professional, friendly, and conversational. "
    "BEHAVIOR: Professional, concise, futuristic. "
    "Use emojis sparingly (💡, ⚠️, 🚀). "
    "If you don't have specific data to reference, provide general industry insights and best practices."
)

# This is ONLY used when CSV is injected
CONSULTANT_WITH_DATA_PROMPT = (
    "You are DataNexus, an AI Game Strategy Consultant. "
    "Your goal is to help developers adapt their games for the future market. "
    "Be professional, friendly, and ALWAYS ACCURATE based on data. "
    "BEHAVIOR: Professional, concise, futuristic. "
    "You have access to a REFERENCE DATASET (CSV) of past successes and failures below. "
    "CRITICAL RULE: ALWAYS cite specific examples from the dataset when making recommendations. "
    "Use emojis sparingly (💡, ⚠️, 🚀). "
)

# --- CREATIVE DIRECTOR PROMPT (3 PHASES) ---
CREATIVE_DIRECTOR_PROMPT = (
    "You are 'The Architect', a specialized Game Design AI. "
    "Your process has THREE PHASES:\n"
    "PHASE 1: INTERVIEW - Ask exactly 10 multiple-choice questions to understand the user's vision.\n"
    "PHASE 2: THE VERDICT - Switch to 'Analyst Mode':\n"
    "   - CRITICAL: You MUST select ONE SPECIFIC GAME from the CSV dataset that best matches the user's idea.\n"
    "   - You can also reference popular games not in the CSV, but PRIORITIZE CSV data when there's a close match.\n"
    "   - Say: 'Based on data, your game is the next [Game Name]...'\n"
    "PHASE 3: DEEP DIVE - After the verdict, do NOT end the session. Wait for these commands:\n"
    "   - ?roadmap: Create a development roadmap based on successful 'Key_Factors' from the CSV\n"
    "   - ?budget: Provide precise financial estimation in USD (using Budget_Tier from CSV)\n"
    "   - ?risks: Analyze potential failure points based on FLOPS in the CSV\n"
    "Always use the CSV columns (Budget_Tier, Key_Factor, Outcome) to support your answers.\n"
    "?end : if the user wabts to end the process"
)


conversations = {}
active_game_modes = {} 

@bot.event
async def on_ready():
    print(f'DataNexus IS ONLINE.')
    load_csv_data() 
    print("---------------------------------------------------")

@bot.command(name='Predict')
async def predict(ctx, *, game_name: str):
    """Analyze a game (real or fictional) and predict its future in 2035"""
    
    # Force CSV loading for Predict command
    csv_context = get_csv_context_for_query(f"predict {game_name}", force=True)
    
    prompt = (
        f"Analyze the game '{game_name}' based on the provided CSV DATASET trends.\n"
        f"{csv_context}\n\n"
        "TASK: Predict the status of this game in the year 2035.\n"
        "1. STATUS: (Dead, Retro Classic, Still Active, or Remade?)\n"
        "2. SURVIVAL PROBABILITY: (0-100%)\n"
        "3. REASONING: Compare it to similar games in the dataset.\n"
        "FORMAT: Use an engaging style with emojis."
    )
    async with ctx.typing():
        completion = client_groq.chat.completions.create(
            messages=[
                {"role": "system", "content": "You are a Futurist Data Scientist specialized in game industry analysis."},
                {"role": "user", "content": prompt}
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.5 
        )
        response = completion.choices[0].message.content
        embed = discord.Embed(title=f"🔮 DataNexus Prediction: {game_name}", description=response, color=0xff00ff)
        embed.set_footer(text="Based on historical dataset analysis")
        await ctx.reply(embed=embed)

@bot.command(name='SearchData')
async def search_data(ctx, *, game_name: str):
    """Search and display CSV data (fuzzy matching supported)"""
    if not CSV_LOADED or DATASET_DF is None:
        await ctx.send("❌ No CSV loaded.")
        return

    all_games = DATASET_DF['Game_Name'].tolist() 

    # Fuzzy search
    matches = difflib.get_close_matches(game_name, all_games, n=1, cutoff=0.4)

    if matches:
        found_name = matches[0] 
        row = DATASET_DF[DATASET_DF['Game_Name'] == found_name].iloc[0]
        
        color_map = {"HIT": 0x00ff00, "FLOP": 0xff0000, "REDEMPTION": 0xffa500, "STABLE": 0x3498db}
        embed_color = color_map.get(row.get('Outcome', 'FLOP'), 0x9b59b6)

        embed = discord.Embed(title=f"📂 CSV Data: {row['Game_Name']}", color=embed_color)
        embed.description = f"*(Search: '{game_name}' → Found: '{found_name}')*" 
        
        embed.add_field(name="Genre", value=row['Genre'], inline=True)
        embed.add_field(name="Outcome", value=f"**{row['Outcome']}**", inline=True)
        embed.add_field(name="Gap (Hype/Reality)", value=f"{row['Hype_vs_Reality_Gap']}/10", inline=True)
        embed.add_field(name="Key Factor", value=f"*{row['Key_Factor']}*", inline=False)
        embed.add_field(name="2035 Forecast", value=row['2035_Forecast'], inline=False)
        embed.set_footer(text="From Games.csv ✅")
        
        await ctx.send(embed=embed)
    else:
        await ctx.send(f"❌ Game '{game_name}' not found in dataset.")

@bot.command(name='Gameidea')
async def game_idea(ctx):
    """Launch interactive game creation mode"""
    user_id = ctx.author.id
    
    # 1. Activate mode for this user
    active_game_modes[user_id] = 0
    
    # 2. Initialize conversation with Creative Director prompt (CSV will be added when needed)
    conversations[user_id] = [
        {"role": "system", "content": CREATIVE_DIRECTOR_PROMPT}
    ]
    
    # 3. Welcome message
    embed = discord.Embed(
        title="🎮 Architect Protocol Activated",
        description="I will ask you **10 questions** (multiple choice) to define your ideal game.\n\nAt the end, I'll generate a complete Design Document validated by DATA.\n\n**Type 'Start' to begin Question 1!**",
        color=0x9b59b6 
    )
    embed.set_footer(text="Type ?end to exit this mode")
    await ctx.send(embed=embed)

@bot.command(name='end')
async def end_game(ctx):
    """Exit game creation mode"""
    user_id = ctx.author.id
    
    if user_id in active_game_modes:
        del active_game_modes[user_id]

        if user_id in conversations:
            del conversations[user_id]
            
        embed = discord.Embed(
            title="💾 Session Ended",
            description="Returning to Consultant mode. Architect session closed.",
            color=0x2ecc71 
        )
        await ctx.send(embed=embed)
    else:
        await ctx.send("You weren't in creation mode! Type `?Gameidea` to start.")

@bot.command(name='HelpNexus')
async def help_nexus(ctx):
    embed = discord.Embed(
        title="📜 DataNexus Manual",
        description="I am Nexus 2035, your strategic and creative assistant. Here are my active modules:",
        color=0x3498db 
    )
    embed.add_field(
        name="🎮 Architect Mode (Game Creation)",
        value=(
            "`?Gameidea` : Launch a **10-question** interview.\n"
            "**After verdict:** Type `?roadmap`, `?budget` or `?risks` to continue analysis.\n"
            "`?end` : Exit game mode."
        ),
        inline=False
    )
    embed.add_field(
        name="🔮 Consultant Mode (Standard)",
        value="Simply ask a question or mention me (@Bot).",
        inline=False
    )
    embed.add_field(
        name="🛡️ Tools",
        value=(
            "`?Predict <Game>` : Predict a game's future (uses CSV).\n"
            "`?SearchData <Game>` : Display CSV entry.\n"
            "`?TokenCheck <password>` : Check API rate limits (Admin only)."
        ),
        inline=False
    )
    embed.set_footer(text="DataNexus v2.1 • Powered by Llama 3 & Python")
    await ctx.send(embed=embed)


@bot.command(name='TokenCheck')
async def token_check(ctx, password: str = None):
    """Check live limits and Token Usage"""
    
    # Admin Security
    if password is None or password.strip() != ADMIN_PWD.strip():
        await ctx.reply("🔒 Password missing or incorrect.")
        return
        
    try:
        await ctx.message.delete()
    except:
        pass 
    
    async with ctx.typing():
        try:
            # Make minimal API call to get headers
            raw_response = client_groq.chat.completions.with_raw_response.create(
                messages=[{"role": "user", "content": "test"}],
                model="llama-3.3-70b-versatile",
                max_tokens=1
            )
            
            headers = raw_response.headers
            
            # Debug: Print all headers to see what's actually available
            print("📋 Available headers:")
            for key, value in headers.items():
                if 'ratelimit' in key.lower() or 'limit' in key.lower():
                    print(f"  {key}: {value}")
            
            # Try different possible header names (Groq uses various formats)
            # Tokens Per Minute (TPM)
            tpm_limit = (headers.get('x-ratelimit-limit-tokens') or 
                        headers.get('x-ratelimit-tokens-limit') or 
                        headers.get('ratelimit-limit-tokens') or 
                        'Unknown')
            
            tpm_remaining = (headers.get('x-ratelimit-remaining-tokens') or 
                           headers.get('x-ratelimit-tokens-remaining') or 
                           headers.get('ratelimit-remaining-tokens') or 
                           'Unknown')
            
            tpm_reset = (headers.get('x-ratelimit-reset-tokens') or 
                        headers.get('x-ratelimit-tokens-reset') or 
                        headers.get('ratelimit-reset-tokens') or 
                        None)
            
            # Requests Per Minute/Day (RPM/RPD)
            rpm_limit = (headers.get('x-ratelimit-limit-requests') or 
                        headers.get('x-ratelimit-requests-limit') or 
                        headers.get('ratelimit-limit-requests') or 
                        'Unknown')
            
            rpm_remaining = (headers.get('x-ratelimit-remaining-requests') or 
                           headers.get('x-ratelimit-requests-remaining') or 
                           headers.get('ratelimit-remaining-requests') or 
                           'Unknown')
            
            rpm_reset = (headers.get('x-ratelimit-reset-requests') or 
                        headers.get('x-ratelimit-requests-reset') or 
                        headers.get('ratelimit-reset-requests') or 
                        None)
            
            # Calculate usage percentages
            try:
                tpm_used = int(tpm_limit) - int(tpm_remaining) if tpm_limit != 'Unknown' and tpm_remaining != 'Unknown' else 'N/A'
                tpm_percent = round((int(tpm_remaining) / int(tpm_limit)) * 100, 1) if tpm_limit != 'Unknown' and tpm_remaining != 'Unknown' else 'N/A'
            except:
                tpm_used = 'N/A'
                tpm_percent = 'N/A'
            
            try:
                rpm_used = int(rpm_limit) - int(rpm_remaining) if rpm_limit != 'Unknown' and rpm_remaining != 'Unknown' else 'N/A'
                rpm_percent = round((int(rpm_remaining) / int(rpm_limit)) * 100, 1) if rpm_limit != 'Unknown' and rpm_remaining != 'Unknown' else 'N/A'
            except:
                rpm_used = 'N/A'
                rpm_percent = 'N/A'
            
            # Format reset times
            def format_reset_time(reset_timestamp):
                if not reset_timestamp:
                    return "Unknown"
                try:
                    import datetime
                    reset_time = datetime.datetime.fromtimestamp(int(reset_timestamp))
                    now = datetime.datetime.now()
                    delta = reset_time - now
                    
                    if delta.total_seconds() < 60:
                        return f"{int(delta.total_seconds())}s"
                    elif delta.total_seconds() < 3600:
                        return f"{int(delta.total_seconds() / 60)}m"
                    else:
                        return f"{int(delta.total_seconds() / 3600)}h {int((delta.total_seconds() % 3600) / 60)}m"
                except:
                    return "Unknown"
            
            tpm_reset_str = format_reset_time(tpm_reset)
            rpm_reset_str = format_reset_time(rpm_reset)
            
            # Create beautiful embed
            embed = discord.Embed(title="⚡ Groq API Rate Limits (Live)", color=0xf39c12)
            embed.description = "Current API quota status:"
            
            # Tokens section
            token_bar = "🟩" * int(tpm_percent / 10) + "⬜" * (10 - int(tpm_percent / 10)) if tpm_percent != 'N/A' else "❓" * 10
            embed.add_field(
                name="🎯 Tokens Per Minute (TPM)", 
                value=(
                    f"**{tpm_remaining}** / {tpm_limit} remaining\n"
                    f"Used: **{tpm_used}** ({100 - tpm_percent if tpm_percent != 'N/A' else 'N/A'}%)\n"
                    f"{token_bar}\n"
                    f"Resets in: **{tpm_reset_str}**"
                ), 
                inline=False
            )
            
            # Requests section
            request_bar = "🟦" * int(rpm_percent / 10) + "⬜" * (10 - int(rpm_percent / 10)) if rpm_percent != 'N/A' else "❓" * 10
            embed.add_field(
                name="📊 Requests Per Minute (RPM)", 
                value=(
                    f"**{rpm_remaining}** / {rpm_limit} remaining\n"
                    f"Used: **{rpm_used}** ({100 - rpm_percent if rpm_percent != 'N/A' else 'N/A'}%)\n"
                    f"{request_bar}\n"
                    f"Resets in: **{rpm_reset_str}**"
                ), 
                inline=False
            )
            
            # Status indicator
            if tpm_percent != 'N/A' and tpm_percent < 20:
                status = "🔴 **CRITICAL** - Almost out of tokens!"
            elif tpm_percent != 'N/A' and tpm_percent < 50:
                status = "🟡 **WARNING** - Token usage is high"
            else:
                status = "🟢 **HEALTHY** - Plenty of quota remaining"
            
            embed.add_field(name="Status", value=status, inline=False)
            
            embed.set_footer(text="Groq API • Free Tier Limits")
            await ctx.send(embed=embed)
            
        except Exception as e:
            # Detailed error message
            import traceback
            error_details = traceback.format_exc()
            
            embed = discord.Embed(title="❌ Error Fetching API Limits", color=0xff0000)
            embed.description = f"**Error:** {str(e)}\n\n**Possible reasons:**\n• Groq API headers changed\n• Network issue\n• Invalid API key"
            embed.add_field(name="Debug Info", value=f"```{error_details[-500:]}```", inline=False)
            await ctx.send(embed=embed)
            
            print(f"🔴 Full error trace:\n{error_details}")


@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    
    ctx = await bot.get_context(message)
    if ctx.valid:
        await bot.process_commands(message)
        return
        
    is_trigger = message.content.startswith('?')
    is_mention = bot.user.mentioned_in(message)
    user_id = message.author.id
    is_in_game_mode = user_id in active_game_modes
    
    if is_trigger or is_mention or is_in_game_mode:
        async with message.channel.typing():
            try:
                user_name = message.author.display_name
                user_text = message.content

                if is_trigger: user_text = user_text[1:]
                user_text = user_text.replace(f'<@!{bot.user.id}>', '').replace(f'<@{bot.user.id}>', '').strip()
                if not user_text: return

                embed_title = "🔮 DataNexus Analysis"
                embed_color = 0x00ffea
                footer_text = f"Response for {user_name}"
                prompt_suffix = ""
                finish_game = False
                
                # 🔧 FIX: Initialize current_step safely
                current_step = active_game_modes.get(user_id, 0) if is_in_game_mode else 0
                
                # Track if this is verdict phase BEFORE modifying current_step
                is_verdict_phase = False
                
                # Track if CSV should be injected (ONLY for verdict or special commands)
                should_inject_csv = False

                if is_in_game_mode:
                    # --- PHASE 3: POST-VERDICT (Step 100) ---
                    if current_step >= 100:
                        lower_text = user_text.lower()
                        
                        # Force CSV injection for post-verdict analysis commands
                        should_inject_csv = True
                        
                        if "roadmap" in lower_text:
                            prompt_suffix = (
                                "\n[SYSTEM]: User wants a ROADMAP.\n"
                                "Create a step-by-step development plan based on the 'Key_Factors' of successful games in the CSV."
                            )
                            embed_title = "🗺️ Strategic Roadmap"
                            embed_color = 0x2ecc71
                        
                        elif "budget" in lower_text:
                            prompt_suffix = (
                                "\n[SYSTEM]: User wants a PRECISE FINANCIAL ESTIMATION (USD).\n"
                                "1. Do NOT just say 'AAA' or 'Indie'. Give a concrete estimated range in MILLIONS of USD (e.g., '$50M - $150M' or '$500k - $2M').\n"
                                "2. Base this calculation on the complexity of the features and the CSV Budget_Tier.\n"
                                "3. Compare with the Budget_Tier of similar games in the CSV."
                            )
                            embed_title = "💰 Budget Estimation"
                            embed_color = 0xf1c40f
                        
                        elif "risk" in lower_text or "risks" in lower_text:
                            prompt_suffix = (
                                "\n[SYSTEM]: User wants a RISK ANALYSIS.\n"
                                "Analyze potential failure points by looking at FLOPS in the CSV.\n"
                                "Identify if the idea has a high 'Gap' between Hype and Reality."
                            )
                            embed_title = "⚠️ Risk Analysis (Failure Points)"
                            embed_color = 0xe74c3c
                        else:
                            prompt_suffix = "\n[SYSTEM]: Continue the design discussion based on the CSV data."

                    # --- PHASE 1 & 2: Q&A AND VERDICT ---
                    else:
                        current_step += 1
                        active_game_modes[user_id] = current_step

                        if current_step < 10:
                            prompt_suffix = f"\n\n[SYSTEM]: This is Question {current_step}/10. Ask the next multiple-choice question."
                            finish_game = False
                            embed_title = f"🎮 Question {current_step}/10"
                            embed_color = 0x9b59b6
                            footer_text = "Choose A, B, C or D..."
                    
                        elif current_step == 10:
                            prompt_suffix = "\n\n[SYSTEM]: This is the LAST question (10/10). Ask one final multiple-choice question. Do NOT give the verdict yet."
                            finish_game = False
                            embed_title = "🎮 Question 10/10 (Final!)"
                            embed_color = 0x9b59b6
                            footer_text = "Last step..."
                            
                        else:
                            # 🔧 FIX: Set flag BEFORE changing current_step
                            is_verdict_phase = True
                            should_inject_csv = True  # ONLY inject CSV at verdict
                            
                            # VERDICT (Step 11) - Now we need CSV data
                            active_game_modes[user_id] = 100 
                            
                            prompt_suffix = (
                                "\n\n🛑 **SYSTEM OVERRIDE: VERDICT TIME** 🛑\n"
                                "Your task is to generate the GRAND FINALE in TWO PARTS separated strictly by '[[SPLIT]]'.\n\n"
                                
                                "--- PART 1: THE RECAP ---\n"
                                "Briefly summarize the user's choices (Genre, Tone, Mechanics, etc.) in a bullet-point list.\n\n"
                                
                                "[[SPLIT]]\n\n"
                                
                                "--- PART 2: THE VERDICT ---\n"
                                "1. Select ONE GAME from the CSV that perfectly matches the user's choices.\n"
                                "2. Generate the detailed game concept and compare it to that CSV game.\n"
                                "3. AT THE END, tell the user: '💡 Type ?roadmap, ?budget or ?risks to dive deeper.'"
                            )
                            finish_game = True

                # --- CONTEXT INJECTION (OPTIMIZED & BUG-FIXED) ---
                if user_id not in conversations:
                    # Start with basic prompt (no CSV mentioned)
                    base_prompt = CONSULTANT_SYSTEM_PROMPT
                    
                    conversations[user_id] = [{
                        "role": "system", 
                        "content": base_prompt
                    }]

                # Build the final user message
                final_user_content = user_text + prompt_suffix
                
                # 🔧 CRITICAL FIX: ONLY inject CSV if should_inject_csv is True
                if should_inject_csv:
                    # Update system prompt to mention dataset when CSV is actually provided
                    conversations[user_id][0]["content"] = CONSULTANT_WITH_DATA_PROMPT
                    
                    csv_context = get_csv_context_for_query(user_text, force=True)
                    final_user_content += f"\n\n{csv_context}"
                    print(f"📊 CSV injected for: {user_name} (verdict/analysis mode)")
                else:
                    # Make sure system prompt doesn't mention dataset
                    if conversations[user_id][0]["content"] != CONSULTANT_SYSTEM_PROMPT:
                        conversations[user_id][0]["content"] = CONSULTANT_SYSTEM_PROMPT
                    print(f"💬 Normal conversation (no CSV): {user_name}")

                conversations[user_id].append({"role": "user", "content": final_user_content})

                # Keep conversation history under control (Max 32 messages)
                if len(conversations[user_id]) > 32:
                    conversations[user_id] = [conversations[user_id][0]] + conversations[user_id][-30:]

                # --- GROQ API CALL ---
                chat_completion = client_groq.chat.completions.create(
                    messages=conversations[user_id], 
                    model="llama-3.3-70b-versatile",
                    temperature=0.7,
                    max_tokens=2000,
                )

                raw_response = chat_completion.choices[0].message.content
                clean_response = raw_response.strip()
                conversations[user_id].append({"role": "assistant", "content": clean_response})
                
                # --- SPLIT DISPLAY FOR VERDICT ---
                if is_in_game_mode and finish_game and "[[SPLIT]]" in clean_response:
                    parts = clean_response.split("[[SPLIT]]")
                    
                    # Part 1: The Recap
                    part_1_recap = parts[0].strip()
                    embed1 = discord.Embed(
                        title="📝 PART 1: SUMMARY",
                        description=part_1_recap,
                        color=0x3498db # Blue
                    )
                    await message.reply(embed=embed1)

                    # Part 2: The Verdict (The main content)
                    part_2_verdict = parts[1].strip() if len(parts) > 1 else "Continued..."
                    embed2 = discord.Embed(
                        title="🏆 PART 2: THE VERDICT & MARKET",
                        description=part_2_verdict,
                        color=0xffd700 # Gold
                    )
                    embed2.set_footer(text="💡 Type now: ?roadmap, ?budget or ?risks")
                    await message.reply(embed=embed2)

                # STANDARD CASE: Normal messages (Questions or Chat)
                else:
                    # Handle length (4000 character limit)
                    if len(clean_response) > 4000: 
                        clean_response = clean_response[:3900] + "..."
                    
                    embed = discord.Embed(
                        title=embed_title, 
                        description=clean_response, 
                        color=embed_color
                    )
                    embed.set_footer(text=footer_text)
                    await message.reply(embed=embed)

            except Exception as e:
                print(f"ERROR: {e}")
                await message.reply(embed=discord.Embed(title="⚠️ System Error", description=f"Error: {e}", color=0xff0000))
                
                # Only reset on crash
                if user_id in active_game_modes: del active_game_modes[user_id]
                if user_id in conversations: del conversations[user_id]

    await bot.process_commands(message)

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    raise error

bot.run(DISCORD_TOKEN)