from langchain_groq import ChatGroq
from dotenv import load_dotenv
import os
from langchain.messages import HumanMessage, AIMessage, SystemMessage
load_dotenv()

grok_key = os.getenv("GROQ_API_KEY")

model = ChatGroq(
    model="openai/gpt-oss-120b",
    api_key=grok_key
)
conversation = [
    SystemMessage("You are a helpful assistant that translates English to French."),
    HumanMessage("Translate: I love programming."),
    AIMessage("J'adore la programmation."),
    HumanMessage("Translate: I love building applications.")
]
response = model.invoke(conversation)

print(response)