import os
from azure.cosmos import CosmosClient, ContainerProxy
from dotenv import load_dotenv

load_dotenv()

COSMOS_URI = os.getenv("COSMOS_URI")
COSMOS_KEY = os.getenv("COSMOS_KEY")
DATABASE_NAME = os.getenv("COSMOS_DATABASE_NAME", "studieassistent")
CONTAINER_NAME = os.getenv("COSMOS_CONTAINER_NAME", "chunk")


def get_container() -> ContainerProxy:
    if not COSMOS_URI or not COSMOS_KEY:
        raise ValueError("COSMOS_URI or COSMOS_KEY missing in .env-file.")

    client = CosmosClient(COSMOS_URI, credential=COSMOS_KEY)
    database = client.get_database_client(DATABASE_NAME)
    container = database.get_container_client(CONTAINER_NAME)
    return container