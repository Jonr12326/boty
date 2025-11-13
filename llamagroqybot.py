import discord
from groq import Groq, APIError, AuthenticationError 
import sys
import os

# --- Configuration (Keys are HARDCODED) ---
# Discord Bot Token
DISCORD_TOKEN = "MTQzODE0MjM3NzQ1NzA5NDgzNw.G7YZKd.PbxKMCL606Okgakse10R485zDMxJwcqlMBNjN8"
# Groq API Key
GROQ_API_KEY = "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" 

# Groq Configuration
GROQ_MODEL = "llama-3.1-8b-instant" 

ALLOWED_CHANNELS = [1432339343506145391, 1432343408302882908]

# Context Management Settings
MAX_HISTORY_TURNS = 10 

# --- Groq Client Setup ---
groq_client = None
try:
    # Use the hardcoded key directly
    groq_client = Groq(api_key=GROQ_API_KEY)
except Exception as e:
    print(f"ERROR: Failed to initialize Groq client: {e}")

# --- Discord Bot Setup ---
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# Dictionary to store conversation history (OpenAI/Groq format)
chat_history = {}

# --- Helper Functions ---
def trim_history(history_list):
    """Trims the conversation history to maintain a maximum number of turns."""
    if len(history_list) > MAX_HISTORY_TURNS * 2:
        return history_list[-(MAX_HISTORY_TURNS * 2):]
    return history_list

def split_message(text, limit=2000):
    """Splits a long message into Discord-safe chunks."""
    lines = text.split('\n')
    chunks = []
    current = ""
    for line in lines:
        if len(current) + len(line) + 1 > limit and current:
            chunks.append(current.strip())
            current = line + '\n'
        elif len(current) + len(line) + 1 > limit and not current:
            chunks.append(line[:limit])
            current = line[limit:] + '\n'
        else:
            current += line + '\n'
    if current:
        chunks.append(current.strip())
    return [chunk for chunk in chunks if chunk]


# --- Discord Events ---

@client.event
async def on_ready():
    print(f"✅ Logged in as {client.user} (ID: {client.user.id})")
    if not groq_client:
        print("❌ Groq client is NOT initialized. Bot will not function.")
    print("Bot is ready.")

@client.event
async def on_message(message):
    if message.author == client.user or not groq_client:
        return

    if message.channel.id not in ALLOWED_CHANNELS:
        return
    
    clean_content = message.content.strip()
    
    if not clean_content:
        return

    channel_id = message.channel.id
    
    if channel_id not in chat_history:
        chat_history[channel_id] = []

    print(f"📨 Message received: {clean_content}")

    # --- 1. Prepare Payload with History ---
    user_message_object = {
        "role": "user",
        "content": clean_content
    }
    chat_history[channel_id].append(user_message_object)

    current_history = trim_history(chat_history[channel_id])

    # --- 2. API Call and Response Handling ---
    try:
        # Show typing indicator for better UX
        async with message.channel.typing():
            
            completion = groq_client.chat.completions.create(
                model=GROQ_MODEL,
                messages=current_history,
                temperature=0.6,
                top_p=0.7,
                max_tokens=4096,
                stream=False 
            )
        
        print("🤖 Groq response received.")

        # Check for response and safety blocks
        if not completion.choices or completion.choices[0].finish_reason != 'stop':
            finish_reason = completion.choices[0].choices[0].finish_reason if completion.choices and completion.choices[0] else "NO_RESPONSE"
            
            reply = f"⚠️ The model stopped prematurely (Reason: `{finish_reason}`). Try rephrasing your prompt."
            
            # Rollback history since no valid response was generated
            chat_history[channel_id].pop() 
            
            await message.channel.send(reply)
            return

        reply = completion.choices[0].message.content

        # --- 3. Update History with Successful Bot Response ---
        chat_history[channel_id].append({
            "role": "assistant", 
            "content": reply
        })
        chat_history[channel_id] = trim_history(chat_history[channel_id])


        # --- 4. Send Reply ---
        for chunk in split_message(reply):
            await message.channel.send(chunk)

    except AuthenticationError as e:
        error_msg = "❌ Authentication Error: Your GROQ API key is invalid or expired. Please replace it."
        chat_history[channel_id].pop()
        await message.channel.send(error_msg)
        print(f"❌ AUTHENTICATION ERROR: {e}")
        
    except APIError as e:
        error_msg = f"❌ GROQ API Error: The request failed ({e.status_code}). This is often a **QUOTA** issue on the free tier."
        chat_history[channel_id].pop() 
        await message.channel.send(error_msg)
        print(f"❌ API ERROR: {e}")

    except Exception as e:
        error_msg = "⚠️ An unexpected error occurred."
        chat_history[channel_id].pop()
        await message.channel.send(error_msg)
        print(f"❌ GENERAL ERROR: {e}")


# --- CRITICAL CHANGE TO KEEP WINDOW OPEN ---
try:
    print("Attempting to start Discord client...")
    client.run(DISCORD_TOKEN)
except Exception as e:
    print("==================================================================")
    print("CRITICAL BOT STARTUP ERROR: The bot failed to start!")
    print(f"Error Details: {e}")
    print("==================================================================")

if sys.platform.startswith('win'):
    print("\n--- PROGRAM ENDED ---")
    input("Press ENTER to close this window...")