from openai import AzureOpenAI
from config import *

client = AzureOpenAI(
    api_key=AZURE_OPENAI_API_KEY,
    api_version=AZURE_OPENAI_API_VERSION,
    azure_endpoint=AZURE_OPENAI_ENDPOINT
)

result = client.embeddings.create(
    input="This is a test sentence.",
    model=EMBED_MODEL
)

print(len(result.data[0].embedding))  # should print 1536 or 3072 depending on model


