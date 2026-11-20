import os
import httpx
from dotenv import load_dotenv
from groq import Groq

load_dotenv("../.env")

# local_address="0.0.0.0" — faqat IPv4 orqali ulanishni majburlaydi
http_client = httpx.Client(
    transport=httpx.HTTPTransport(local_address="0.0.0.0"),
    timeout=60.0,
)
client = Groq(api_key=os.getenv("GROQ_API_KEY"), http_client=http_client)

ids = sorted(m.id for m in client.models.list().data)
print("Mavjud modellar:")
for i in ids:
    print(" -", i)

print("\nllama-3.3-70b-versatile bormi?", "llama-3.3-70b-versatile" in ids)