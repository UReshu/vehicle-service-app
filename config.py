import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production")
    AWS_REGION = os.getenv("AWS_REGION", "ap-south-1")
    AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
    USE_IAM_ROLE = os.getenv("USE_IAM_ROLE", "true").lower() == "true"

    USERS_TABLE = os.getenv("USERS_TABLE", "users")
    VEHICLES_TABLE = os.getenv("VEHICLES_TABLE", "vehicles")
    APPOINTMENTS_TABLE = os.getenv("APPOINTMENTS_TABLE", "appointments")
    MECHANICS_TABLE = os.getenv("MECHANICS_TABLE", "mechanics")
    SERVICE_HISTORY_TABLE = os.getenv("SERVICE_HISTORY_TABLE", "service_history")
    BILLS_TABLE = os.getenv("BILLS_TABLE", "bills")
