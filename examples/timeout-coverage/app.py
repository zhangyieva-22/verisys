from openai import OpenAI

client = OpenAI()
client.responses.create(input="one", timeout=30)
client.embeddings.create(input="two", timeout=10)
client.responses.create(input="three")
