import gradio as gr
from openai import OpenAI
import os

# --------------------- Yahan apna Groq API key daalo ---------------------
# Pehle https://console.groq.com se free key le lo
GROQ_API_KEY = "gsk_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"   # <--- Yahan change karo

client = OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=GROQ_API_KEY,
)

# Best free model jo speed + quality mein strong hai (multilingual + coding achha)
MODEL = "llama-3.3-70b-versatile"   # ya "mixtral-8x7b-32768" agar zyada fast chahiye

def chat_with_ai(message, history):
    # History ko OpenAI format mein convert karo
    messages = [{"role": "system", "content": "You are a helpful, friendly AI assistant. Respond naturally in Urdu, English, Roman Urdu mix if user uses it. Help with Python coding, explain clearly, be accurate and step-by-step."}]
    
    for user_msg, ai_msg in history:
        messages.append({"role": "user", "content": user_msg})
        if ai_msg:
            messages.append({"role": "assistant", "content": ai_msg})
    
    messages.append({"role": "user", "content": message})
    
    # Streaming response ke liye
    stream = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        temperature=0.7,
        max_tokens=1024,
        stream=True,
    )
    
    response = ""
    for chunk in stream:
        if chunk.choices[0].delta.content is not None:
            response += chunk.choices[0].delta.content
            yield response  # Streaming effect (type karte hue dikhega)

# Gradio Chat UI
demo = gr.ChatInterface(
    fn=chat_with_ai,
    title="Mera Free AI Chat (Groq Powered)",
    description="Urdu, English, Roman mix mein baat karo. Python code paste karo, help lunga! 🚀",
    examples=[
        "Python mein factorial function banao aur Urdu mein samjhao",
        "mera code debug karo: print(hello world)",
        "Aaj Rawalpindi ka mausam kaisa hai? 😄",
    ],
    cache_examples=False,
)

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)
