from openai import OpenAI

client = OpenAI()
client.responses.create(input="example", timeout=timeout_value)
